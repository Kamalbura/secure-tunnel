#!/usr/bin/env python3
"""
Drone Scheduler – MAV-to-MAV PQC Tunnel Controller
sscheduler/sdrone.py

REVERSED CONTROL: Drone is the controller, GCS follows.

Data flow (bidirectional MAVLink):
  FC (serial) → MAVProxy → plaintext UDP → PQC Proxy → encrypted UDP → GCS
  FC (serial) ← MAVProxy ← plaintext UDP ← PQC Proxy ← encrypted UDP ← GCS

Two scheduling policies:
  deterministic  – Fixed-interval cycling through filtered suites (benchmark)
  intelligent    – Adaptive selection driven by battery, thermal, link quality,
                   mission criticality, and AEAD / NIST-level constraints (flight)

The drone never generates synthetic traffic.  All data flowing through
the tunnel is real MAVLink produced by MAVProxy ↔ flight-controller.

Usage:
  python -m sscheduler.sdrone --policy intelligent
  python -m sscheduler.sdrone --policy deterministic --duration 10
"""

import os
import sys
import time
import json
import socket
import signal
import argparse
import logging
import subprocess
import threading
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

# Ensure parent on sys.path for core imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import CONFIG
from core.suites import get_suite, list_suites
from core.process import ManagedProcess
from sscheduler.policy import (
    TelemetryAwarePolicyV2,
    PolicyAction,
    PolicyOutput,
    DecisionInput,
)
from sscheduler.benchmark_policy import BenchmarkPolicy, BenchmarkAction
from sscheduler.telemetry_window import TelemetryWindow
from sscheduler.local_mon import LocalMonitor

try:
    from core.clock_sync import ClockSync
except ImportError:
    ClockSync = None  # type: ignore

# ---------------------------------------------------------------------------
# Configuration – single source of truth from core.config
# ---------------------------------------------------------------------------

DRONE_HOST = str(CONFIG["DRONE_HOST"])
GCS_HOST = str(CONFIG["GCS_HOST"])
DRONE_PLAIN_RX = int(CONFIG["DRONE_PLAINTEXT_RX"])
DRONE_PLAIN_TX = int(CONFIG["DRONE_PLAINTEXT_TX"])
GCS_CONTROL_HOST = str(CONFIG.get("GCS_HOST"))
GCS_CONTROL_PORT = int(CONFIG.get("GCS_CONTROL_PORT", 48080))
GCS_TELEMETRY_PORT = int(CONFIG.get("GCS_TELEMETRY_PORT", 52080))

SECRETS_DIR = Path(__file__).parent.parent / "secrets" / "matrix"
ROOT = Path(__file__).resolve().parents[1]
LOGS_DIR = ROOT / "logs" / "sscheduler" / "drone"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Scheduler tick interval (seconds)
EVAL_INTERVAL_S = 1.0
# Cooldown after a suite switch to prevent rapid thrashing
SWITCH_COOLDOWN_S = 5.0

_suites_dict = list_suites()
ALL_SUITES = [{"name": k, **v} for k, v in _suites_dict.items()]


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def log(msg: str):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"[{ts}] [sdrone] {msg}", flush=True)


# ---------------------------------------------------------------------------
# GCS Control Client (TCP JSON-RPC)
# ---------------------------------------------------------------------------

def send_gcs_command(cmd: str, **params) -> dict:
    """Send a JSON command to the GCS control server over TCP."""
    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(30.0)
        sock.connect((GCS_CONTROL_HOST, GCS_CONTROL_PORT))
        request = {"cmd": cmd, **params}
        sock.sendall(json.dumps(request).encode() + b"\n")
        buf = b""
        while b"\n" not in buf:
            chunk = sock.recv(4096)
            if not chunk:
                break
            buf += chunk
        return json.loads(buf.decode().strip())
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        if sock:
            try:
                sock.close()
            except Exception:
                pass


def wait_for_gcs(timeout: float = 120.0) -> bool:
    """Block until GCS control server responds to ping."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if send_gcs_command("ping").get("status") == "ok":
            return True
        time.sleep(0.5)
    return False


# ---------------------------------------------------------------------------
# Drone Proxy Manager
# ---------------------------------------------------------------------------

class DroneProxyManager:
    """Manages the drone-side PQC proxy subprocess (core.run_proxy drone)."""

    def __init__(self):
        self.proc: Optional[ManagedProcess] = None
        self.current_suite: Optional[str] = None
        self._last_log: Optional[Path] = None

    def start(self, suite_name: str) -> bool:
        if self.proc and self.proc.is_running():
            self.stop()

        suite = get_suite(suite_name)
        if not suite:
            log(f"Unknown suite: {suite_name}")
            return False

        peer_pubkey = SECRETS_DIR / suite_name / "gcs_signing.pub"
        if not peer_pubkey.exists():
            log(f"Missing public key: {peer_pubkey}")
            return False

        cmd = [
            sys.executable, "-m", "core.run_proxy", "drone",
            "--suite", suite_name,
            "--peer-pubkey-file", str(peer_pubkey),
            "--quiet",
            "--status-file", str(LOGS_DIR / "drone_status.json"),
        ]

        ts = time.strftime("%Y%m%d-%H%M%S")
        log_path = LOGS_DIR / f"proxy_{suite_name}_{ts}.log"
        log(f"Starting proxy: {suite_name}")

        try:
            fh = open(log_path, "w", encoding="utf-8")
        except Exception:
            fh = subprocess.DEVNULL

        self.proc = ManagedProcess(
            cmd=cmd,
            name=f"proxy-{suite_name}",
            stdout=fh,
            stderr=subprocess.STDOUT,
        )
        if not self.proc.start():
            return False

        self._last_log = log_path
        self.current_suite = suite_name

        # Wait for proxy startup + handshake
        time.sleep(3.0)
        if not self.proc.is_running():
            log(f"Proxy exited early for {suite_name}")
            self._dump_log_tail()
            return False
        return True

    def stop(self):
        if self.proc:
            self.proc.stop()
            self.proc = None
            self.current_suite = None

    def is_running(self) -> bool:
        return self.proc is not None and self.proc.is_running()

    def _dump_log_tail(self, n: int = 20):
        if not self._last_log or not self._last_log.exists():
            return
        try:
            lines = self._last_log.read_text(encoding="utf-8").splitlines()[-n:]
            for ln in lines:
                log(f"  | {ln}")
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Telemetry Receiver  (GCS → Drone, UDP)
# ---------------------------------------------------------------------------

class TelemetryReceiver:
    """Listens for GCS telemetry packets and feeds them into TelemetryWindow.

    Accepts both individual packets and batched envelopes
    (schema ``uav.pqc.telemetry.batch.v1``).
    """

    def __init__(self, port: int, window: TelemetryWindow):
        self.port = port
        self.window = window
        self._sock: Optional[socket.socket] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self):
        if self._running:
            return
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("0.0.0.0", self.port))
        self._sock.settimeout(1.0)
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        log(f"Telemetry receiver listening on :{self.port}")

    def _loop(self):
        while self._running:
            try:
                data, _ = self._sock.recvfrom(65535)
                packet = json.loads(data.decode("utf-8"))
                now = time.monotonic()

                # Handle batched envelope
                schema = packet.get("schema", "")
                if schema.startswith("uav.pqc.telemetry.batch"):
                    for sample in packet.get("samples", []):
                        self.window.add(now, sample)
                else:
                    # Single-sample packet (legacy / fallback)
                    self.window.add(now, packet)
            except socket.timeout:
                continue
            except Exception:
                pass

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        if self._sock:
            self._sock.close()


# ---------------------------------------------------------------------------
# Telemetry Reporter  (Drone → logfile, periodic status dump)
# ---------------------------------------------------------------------------

class TelemetryReporter:
    """Periodically logs a combined snapshot of local + GCS telemetry
    to a JSONL file for post-flight analysis."""

    def __init__(
        self,
        local_mon: LocalMonitor,
        telem_window: TelemetryWindow,
        log_dir: Path,
    ):
        self._local = local_mon
        self._window = telem_window
        self._log_path = log_dir / "drone_telemetry.jsonl"
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self):
        while self._running:
            try:
                lm = self._local.get_metrics()
                gs = self._window.summarize(time.monotonic())
                record = {
                    "ts_ns": time.time_ns(),
                    "local": {
                        "battery_mv": lm.battery_mv,
                        "battery_roc": round(lm.battery_roc, 2),
                        "temp_c": round(lm.temp_c, 1),
                        "temp_roc": round(lm.temp_roc, 2),
                        "armed": lm.armed,
                        "cpu_pct": round(lm.cpu_pct, 1),
                    },
                    "gcs": {
                        "sample_count": gs["sample_count"],
                        "rx_pps_median": gs["rx_pps_median"],
                        "gap_p95_ms": gs["gap_p95_ms"],
                        "silence_max_ms": gs["silence_max_ms"],
                        "jitter_ms": gs["jitter_ms"],
                        "confidence": gs["confidence"],
                    },
                }
                with open(self._log_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(record) + "\n")
            except Exception:
                pass
            time.sleep(2.0)

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)


# ===========================================================================
# MAV Tunnel Scheduler
# ===========================================================================

class MavTunnelScheduler:
    """Orchestrates a MAV-to-MAV PQC tunnel with policy-driven suite selection.

    Architecture
    ~~~~~~~~~~~~
    * **MAVProxy** (persistent): bridges FC serial ↔ plaintext UDP ports.
    * **PQC Proxy** (per-suite): encrypts plaintext UDP ↔ encrypted UDP.
    * **LocalMonitor**: battery, thermal, armed state from Pixhawk.
    * **TelemetryReceiver**: GCS link-quality metrics via UDP.
    * **Policy Engine**: deterministic (benchmark) *or* intelligent (flight).

    Intelligent Policy Inputs (from settings.json)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    * mission_criticality  – low / medium / high
    * max_nist_level       – L1 / L3 / L5 ceiling
    * allowed_aead         – aesgcm / chacha20poly1305 / ascon128a
    * battery thresholds   – critical_mv, low_mv, warn_mv, rate_warn_mv_per_min
    * thermal thresholds   – critical_c, warn_c, rate_warn_c_per_min
    * link thresholds      – min_pps, max_gap_ms, max_blackout_count
    * rekey limits         – min_stable_s, max_per_window, window_s, blacklist_ttl_s
    * hysteresis timers    – downgrade_s (fast), upgrade_s (slow)

    Decision Flow
    ~~~~~~~~~~~~~
    1. Collect local metrics  (battery_mv, temp_c, armed, rates-of-change)
    2. Collect GCS telemetry  (rx_pps, gap_p95, silence, jitter, blackouts)
    3. Build immutable DecisionInput snapshot
    4. policy.evaluate(inp) → PolicyOutput  (HOLD / UPGRADE / DOWNGRADE /
       REKEY / ROLLBACK)
    5. Execute: coordinate GCS prepare_rekey → stop proxy → start new suite
    """

    def __init__(self, args):
        self.args = args
        self.running = True

        # --- sub-components ---
        self.proxy = DroneProxyManager()
        self.local_mon = LocalMonitor(
            mav_port=int(CONFIG.get("MAV_LOCAL_OUT_PORT_2", 14551)),
        )
        self.telem_window = TelemetryWindow(window_s=5.0)
        self.telem_rx = TelemetryReceiver(GCS_TELEMETRY_PORT, self.telem_window)
        self.reporter = TelemetryReporter(self.local_mon, self.telem_window, LOGS_DIR)
        self.mavproxy_proc: Optional[ManagedProcess] = None
        self.clock_sync = ClockSync() if ClockSync else None

        # --- state ---
        self.current_suite: Optional[str] = None
        self.last_switch_mono: float = 0.0
        self.cooldown_until_mono: float = 0.0
        self.local_epoch: int = 0

        # --- resolve suites ---
        self.suites_to_run = self._resolve_suites()
        if not self.suites_to_run:
            raise RuntimeError("No suites available to run")

        # --- policy ---
        if args.policy == "deterministic":
            self.policy_mode = "deterministic"
            self.bench_policy = BenchmarkPolicy(
                cycle_interval_s=float(args.duration),
                suite_list=self.suites_to_run,
            )
            self.intel_policy = None
        else:
            self.policy_mode = "intelligent"
            self.bench_policy = None
            self.intel_policy = TelemetryAwarePolicyV2()
            # Ensure at least one suite survives the filter
            if not self.intel_policy.filtered_suites:
                raise RuntimeError(
                    "Intelligent policy filtered all suites – check "
                    "settings.json (allowed_aead, max_nist_level)"
                )

        log(f"Policy: {self.policy_mode}  |  suites: {len(self.suites_to_run)}")

    # ------------------------------------------------------------------ #
    # Suite resolution
    # ------------------------------------------------------------------ #

    def _resolve_suites(self) -> List[str]:
        if self.args.suite:
            return [self.args.suite]
        names = [s["name"] for s in ALL_SUITES]
        if self.args.nist_level:
            names = [
                s["name"]
                for s in ALL_SUITES
                if s.get("nist_level") == self.args.nist_level
            ]
        if self.args.max_suites:
            names = names[: self.args.max_suites]
        return names

    # ------------------------------------------------------------------ #
    # MAVProxy (persistent)
    # ------------------------------------------------------------------ #

    def _start_mavproxy(self) -> bool:
        """Start persistent MAVProxy bridging FC serial ↔ plaintext UDP."""
        master = self.args.mav_master
        out_port = DRONE_PLAIN_TX

        cmd = [
            sys.executable, "-m", "MAVProxy.mavproxy",
            f"--master={master}",
            f"--out=udp:127.0.0.1:{out_port}",
            "--dialect=ardupilotmega",
            "--nowait",
            "--daemon",
        ]

        ts_str = time.strftime("%Y%m%d-%H%M%S")
        log_path = LOGS_DIR / f"mavproxy_{ts_str}.log"
        try:
            fh = open(log_path, "w", encoding="utf-8")
        except Exception:
            fh = subprocess.DEVNULL

        log(f"Starting MAVProxy: master={master}  out=127.0.0.1:{out_port}")
        self.mavproxy_proc = ManagedProcess(
            cmd=cmd,
            name="mavproxy-drone",
            stdout=fh,
            stderr=subprocess.STDOUT,
            new_console=False,
        )
        if not self.mavproxy_proc.start():
            return False
        time.sleep(1.0)
        return self.mavproxy_proc.is_running()

    # ------------------------------------------------------------------ #
    # Clock synchronisation (Chronos)
    # ------------------------------------------------------------------ #

    def _sync_clock(self):
        if not self.clock_sync:
            return
        try:
            t1 = time.time()
            resp = send_gcs_command("chronos_sync", t1=t1)
            t4 = time.time()
            if resp.get("status") == "ok":
                offset = self.clock_sync.update_from_rpc(t1, t4, resp)
                log(f"Clock-sync offset (GCS − Drone): {offset:.6f} s")
        except Exception as e:
            log(f"Clock-sync error: {e}")

    # ------------------------------------------------------------------ #
    # Suite life-cycle helpers
    # ------------------------------------------------------------------ #

    def _coordinate_suite_start(self, suite_name: str) -> bool:
        """Tell GCS to start its proxy, then start local proxy.

        GCS proxy must start first because the TCP handshake requires
        GCS to listen and drone to connect.
        """
        log(f"Requesting GCS proxy for {suite_name} …")
        resp = send_gcs_command("start_proxy", suite=suite_name)
        if resp.get("status") != "ok":
            log(f"GCS start_proxy failed: {resp}")
            return False

        # Poll until GCS proxy is ready
        deadline = time.time() + 20.0
        while time.time() < deadline:
            time.sleep(0.5)
            st = send_gcs_command("status")
            if st.get("proxy_running"):
                break
        else:
            log("GCS proxy did not become ready in time")
            return False

        # Start local proxy (connects to GCS)
        if not self.proxy.start(suite_name):
            log(f"Local proxy start failed for {suite_name}")
            return False

        # Handshake settling
        time.sleep(1.0)

        self.current_suite = suite_name
        self.last_switch_mono = time.monotonic()
        self.cooldown_until_mono = self.last_switch_mono + SWITCH_COOLDOWN_S
        self.local_epoch += 1
        log(f"Suite ACTIVE: {suite_name}  (epoch {self.local_epoch})")
        return True

    def _switch_suite(self, target_suite: str) -> bool:
        """Full suite switch: stop current → coordinate new."""
        log(f"Suite switch: {self.current_suite} → {target_suite}")

        # 1. Tell GCS to tear down its side
        resp = send_gcs_command("prepare_rekey")
        if resp.get("status") != "ok":
            log(f"GCS prepare_rekey failed: {resp}")
            return False

        # 2. Stop local proxy
        self.proxy.stop()
        time.sleep(0.5)

        # 3. Stand up the new suite
        return self._coordinate_suite_start(target_suite)

    # ------------------------------------------------------------------ #
    # Decision-input builder
    # ------------------------------------------------------------------ #

    def _build_decision_input(self) -> DecisionInput:
        """Assemble a DecisionInput from LocalMonitor + TelemetryWindow."""
        now_s = time.monotonic()
        now_ms = now_s * 1000.0

        lm = self.local_mon.get_metrics()
        gs = self.telem_window.summarize(now_s)
        flight = self.telem_window.get_flight_state()

        telemetry_valid = gs["sample_count"] > 0
        telemetry_age_ms = gs.get("telemetry_age_ms", -1.0)
        if telemetry_age_ms < 0:
            telemetry_valid = False

        synced = 0.0
        if self.clock_sync:
            try:
                synced = self.clock_sync.now()
            except Exception:
                synced = time.time()

        # Derive blackout count from silence duration
        silence_ms = max(gs.get("silence_max_ms", 0.0), 0.0)
        blackout_count = 0
        if silence_ms > 1000.0:
            blackout_count = int(silence_ms / 1000.0)

        return DecisionInput(
            mono_ms=now_ms,
            telemetry_valid=telemetry_valid,
            telemetry_age_ms=max(telemetry_age_ms, 0.0),
            sample_count=gs["sample_count"],
            rx_pps_median=gs["rx_pps_median"],
            gap_p95_ms=gs["gap_p95_ms"],
            silence_max_ms=silence_ms,
            jitter_ms=gs["jitter_ms"],
            blackout_count=blackout_count,
            battery_mv=lm.battery_mv,
            battery_roc=lm.battery_roc,
            temp_c=lm.temp_c,
            temp_roc=lm.temp_roc,
            armed=lm.armed or flight.get("armed", False),
            current_suite=self.current_suite or "",
            local_epoch=self.local_epoch,
            last_switch_mono_ms=self.last_switch_mono * 1000.0,
            cooldown_until_mono_ms=self.cooldown_until_mono * 1000.0,
            synced_time=synced,
        )

    # ------------------------------------------------------------------ #
    # Scheduler loops
    # ------------------------------------------------------------------ #

    def _run_deterministic(self):
        """Fixed-interval cycling through all suites (benchmark mode).

        Uses BenchmarkPolicy which evaluates elapsed time per suite and
        proposes NEXT_SUITE / COMPLETE actions.
        """
        policy = self.bench_policy
        first_suite = policy.start_benchmark(time.monotonic())

        if not self._coordinate_suite_start(first_suite):
            log("Failed to start first suite – aborting deterministic run")
            return

        while self.running:
            now = time.monotonic()
            out = policy.evaluate(now)

            if out.action == BenchmarkAction.NEXT_SUITE:
                target = out.target_suite
                pct = out.progress_pct
                log(
                    f"[deterministic] → {target}  "
                    f"({out.current_index}/{out.total_suites}  {pct:.0f}%)"
                )
                if self._switch_suite(target):
                    policy.confirm_advance(time.monotonic())
                else:
                    log(f"Suite switch to {target} FAILED – skipping")
                    policy.confirm_advance(time.monotonic())

            elif out.action == BenchmarkAction.COMPLETE:
                log("Deterministic benchmark run COMPLETE")
                break

            # Health check
            if self.current_suite and not self.proxy.is_running():
                log("Proxy died – attempting restart on current suite")
                self._coordinate_suite_start(self.current_suite)

            time.sleep(EVAL_INTERVAL_S)

    def _run_intelligent(self):
        """Adaptive suite selection driven by telemetry (flight mode).

        Uses TelemetryAwarePolicyV2 which considers battery, thermal,
        link quality, mission criticality, and hysteresis timers.

        Decision priority (highest → lowest):
          1. Safety gate        – stale telemetry → HOLD
          2. Emergency safety   – battery critical / temp critical → DOWNGRADE
                                  to lightest suite immediately
          3. Link failure       – blackouts after recent switch → ROLLBACK +
                                  blacklist the failing suite
          4. Cooldown gate      – just switched → HOLD
          5. Link degradation   – persistent high gap / low pps → DOWNGRADE
                                  (with hysteresis timer)
          6. Thermal / battery  – rising temp or falling voltage → DOWNGRADE
                                  (with hysteresis timer)
          7. Proactive rekey    – stable for min_stable_s → REKEY same suite
                                  (bounded by max_per_window)
          8. Upgrade            – disarmed, stable, no stress → UPGRADE to
                                  next heavier suite (very conservative)
        """
        policy = self.intel_policy

        # Start with the lightest-tier suite from the filtered pool
        initial = policy.filtered_suites[0]
        if not self._coordinate_suite_start(initial):
            log("Failed to start initial suite – aborting intelligent run")
            return

        while self.running:
            inp = self._build_decision_input()
            out = policy.evaluate(inp)

            if out.action == PolicyAction.HOLD:
                pass  # Nominal – stay on current suite

            elif out.action in (
                PolicyAction.UPGRADE,
                PolicyAction.DOWNGRADE,
                PolicyAction.ROLLBACK,
            ):
                target = out.target_suite
                if target and target != self.current_suite:
                    log(
                        f"[intelligent] {out.action.value} → {target}  "
                        f"(reasons: {', '.join(out.reasons)})"
                    )
                    if self._switch_suite(target):
                        policy.record_rekey(time.monotonic())
                    else:
                        log(f"Suite switch to {target} FAILED")

            elif out.action == PolicyAction.REKEY:
                target = out.target_suite or self.current_suite
                log(
                    f"[intelligent] REKEY → {target}  "
                    f"(reasons: {', '.join(out.reasons)})"
                )
                if self._switch_suite(target):
                    policy.record_rekey(time.monotonic())

            # Health check
            if self.current_suite and not self.proxy.is_running():
                log("Proxy died – restarting current suite")
                self._coordinate_suite_start(self.current_suite)

            time.sleep(EVAL_INTERVAL_S)

    # ------------------------------------------------------------------ #
    # Entrypoint
    # ------------------------------------------------------------------ #

    def start(self) -> int:
        """Initialise all components and run the selected scheduler loop."""

        def _sighandler(sig, frame):
            log("Interrupted – shutting down")
            self.running = False

        signal.signal(signal.SIGINT, _sighandler)
        signal.signal(signal.SIGTERM, _sighandler)

        # 1. Local monitor (battery / thermal / armed)
        self.local_mon.start()
        log("Local monitor started")

        # 2. GCS telemetry receiver
        self.telem_rx.start()

        # 3. Telemetry reporter (JSONL log)
        self.reporter.start()

        # 4. Wait for GCS scheduler
        log("Waiting for GCS scheduler …")
        if not wait_for_gcs(timeout=120.0):
            log("ERROR: GCS scheduler not responding")
            self.cleanup()
            return 1

        # 5. Clock synchronisation
        self._sync_clock()

        # 6. Inform GCS of parameters
        send_gcs_command("configure", duration=self.args.duration)

        # 7. Start persistent MAVProxy (FC serial ↔ plaintext UDP)
        if not self._start_mavproxy():
            log("WARNING: MAVProxy failed to start – tunnel still works "
                "for testing but no MAVLink will flow")

        # 8. Run the chosen policy loop
        try:
            if self.policy_mode == "deterministic":
                self._run_deterministic()
            else:
                self._run_intelligent()
        except Exception as e:
            log(f"Scheduler error: {e}")
        finally:
            self.cleanup()

        return 0

    def cleanup(self):
        log("Cleaning up …")
        self.running = False
        for component in [
            self.proxy,
            self.telem_rx,
            self.reporter,
            self.local_mon,
        ]:
            try:
                component.stop()
            except Exception:
                pass
        try:
            if self.mavproxy_proc:
                self.mavproxy_proc.stop()
        except Exception:
            pass
        try:
            send_gcs_command("stop")
        except Exception:
            pass
        log("Cleanup complete")


# ===========================================================================
# CLI
# ===========================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Drone MAV-to-MAV PQC Tunnel Scheduler",
    )
    parser.add_argument(
        "--policy",
        choices=["deterministic", "intelligent"],
        default="intelligent",
        help="Scheduling policy (default: intelligent)",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=10.0,
        help="Seconds per suite (deterministic mode)",
    )
    parser.add_argument(
        "--mav-master",
        default=str(CONFIG.get("MAV_FC_DEVICE", "/dev/ttyACM0")),
        help="MAVLink master (serial device or tcp:host:port)",
    )
    parser.add_argument("--suite", help="Run a single suite only")
    parser.add_argument(
        "--nist-level",
        choices=["L1", "L3", "L5"],
        help="Filter suites by NIST level",
    )
    parser.add_argument("--max-suites", type=int, help="Limit number of suites")

    args = parser.parse_args()

    print("=" * 60)
    print("  Drone MAV-to-MAV PQC Tunnel Scheduler")
    print(f"  Policy: {args.policy}  |  Duration: {args.duration}s")
    print("=" * 60)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(name)-12s  %(levelname)-7s  %(message)s",
    )

    try:
        scheduler = MavTunnelScheduler(args)
        return scheduler.start()
    except Exception as e:
        log(f"Fatal: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
