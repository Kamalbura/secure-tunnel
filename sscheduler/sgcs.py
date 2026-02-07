#!/usr/bin/env python3
"""
GCS Scheduler – MAV-to-MAV PQC Tunnel Follower
sscheduler/sgcs.py

REVERSED CONTROL: GCS is the follower; drone is the controller.

Data flow (bidirectional MAVLink):
  FC (serial) → MAVProxy(D) → PQC Proxy(D) ──encrypted──▸ PQC Proxy(G) → MAVProxy(G) → QGC
  FC (serial) ← MAVProxy(D) ← PQC Proxy(D) ◂──encrypted── PQC Proxy(G) ← MAVProxy(G) ← QGC

GCS responsibilities:
  1. Listen for TCP control commands from the drone scheduler.
  2. Start / stop PQC proxy for each suite on command.
  3. Run a persistent MAVProxy (--map --console) for QGC.
  4. Collect receiver-side MAVLink metrics via GcsMetricsCollector.
  5. Batch and forward telemetry snapshots to the drone over UDP.
  6. Serve Chronos clock-sync requests so the drone can align timestamps.

The GCS never initiates suite changes.  All scheduling decisions are made
by the drone's policy engine (deterministic or intelligent).

Usage:
  python -m sscheduler.sgcs
"""

import os
import sys
import time
import json
import socket
import signal
import atexit
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
from core.clock_sync import ClockSync
from sscheduler.gcs_metrics import GcsMetricsCollector

# ---------------------------------------------------------------------------
# Configuration – single source of truth from core.config
# ---------------------------------------------------------------------------

DRONE_HOST = str(CONFIG.get("DRONE_HOST"))
GCS_HOST = str(CONFIG.get("GCS_HOST"))

GCS_PLAIN_TX_PORT = int(CONFIG.get("GCS_PLAINTEXT_TX", 47001))
GCS_PLAIN_RX_PORT = int(CONFIG.get("GCS_PLAINTEXT_RX", 47002))
TCP_CTRL_PORT = int(CONFIG.get("TCP_HANDSHAKE_PORT", 46000))
QGC_PORT = int(CONFIG.get("QGC_PORT", 14550))

# Telemetry sniff port: MAVProxy sends a copy of all MAVLink to this
# local UDP port so GcsMetricsCollector can parse it without interfering.
GCS_TELEMETRY_SNIFF_PORT = 14552

# Control plane
GCS_CONTROL_HOST = str(CONFIG.get("GCS_CONTROL_HOST", "0.0.0.0"))
GCS_CONTROL_PORT = int(CONFIG.get("GCS_CONTROL_PORT", 48080))

# Telemetry plane  (GCS → Drone, UDP)
GCS_TELEMETRY_PORT = int(CONFIG.get("GCS_TELEMETRY_PORT", 52080))

SECRETS_DIR = Path(__file__).parent.parent / "secrets" / "matrix"
ROOT = Path(__file__).resolve().parents[1]
LOGS_DIR = ROOT / "logs" / "sscheduler" / "gcs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Telemetry batching
TELEMETRY_HZ = 5.0           # Snapshot frequency
TELEMETRY_BATCH_SIZE = 5     # Samples per batch envelope
TELEMETRY_BATCH_INTERVAL_S = 1.0  # Max wait before flushing partial batch

_suites_dict = list_suites()
ALL_SUITES = [{"name": k, **v} for k, v in _suites_dict.items()]


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def log(msg: str):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"[{ts}] [sgcs] {msg}", flush=True)


def wait_for_tcp_port(port: int, timeout: float = 5.0) -> bool:
    """Wait until a local TCP port accepts connections."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return True
        except (ConnectionRefusedError, OSError, socket.timeout):
            time.sleep(0.2)
    return False


# ---------------------------------------------------------------------------
# GCS Proxy Manager
# ---------------------------------------------------------------------------

class GcsProxyManager:
    """Manages the GCS-side PQC proxy subprocess (core.run_proxy gcs)."""

    def __init__(self):
        self.managed_proc: Optional[ManagedProcess] = None
        self.current_suite: Optional[str] = None

    def start(self, suite_name: str) -> bool:
        if self.managed_proc and self.managed_proc.is_running():
            self.stop()

        suite = get_suite(suite_name)
        if not suite:
            log(f"Unknown suite: {suite_name}")
            return False

        secret_dir = SECRETS_DIR / suite_name
        gcs_key = secret_dir / "gcs_signing.key"
        if not gcs_key.exists():
            log(f"Missing signing key: {gcs_key}")
            return False

        cmd = [
            sys.executable, "-m", "core.run_proxy", "gcs",
            "--suite", suite_name,
            "--gcs-secret-file", str(gcs_key),
            "--quiet",
        ]

        ts = time.strftime("%Y%m%d-%H%M%S")
        log_path = LOGS_DIR / f"proxy_{suite_name}_{ts}.log"
        log(f"Starting GCS proxy: {suite_name}")

        try:
            fh = open(log_path, "w", encoding="utf-8")
        except Exception:
            fh = subprocess.DEVNULL

        self.managed_proc = ManagedProcess(
            cmd=cmd,
            name=f"proxy-{suite_name}",
            stdout=fh,
            stderr=subprocess.STDOUT,
        )
        if not self.managed_proc.start():
            return False

        self.current_suite = suite_name

        # Let the proxy bind its TCP listener and become ready
        time.sleep(2.0)
        if not self.managed_proc.is_running():
            log(f"GCS proxy exited early for {suite_name}")
            return False
        return True

    def stop(self):
        if self.managed_proc:
            self.managed_proc.stop()
            self.managed_proc = None
            self.current_suite = None

    def is_running(self) -> bool:
        return self.managed_proc is not None and self.managed_proc.is_running()


# ---------------------------------------------------------------------------
# Batched Telemetry Sender  (GCS → Drone, UDP)
# ---------------------------------------------------------------------------

class TelemetrySender:
    """Sends receiver-side telemetry snapshots to the Drone over UDP.

    Individual `GcsMetricsCollector.get_snapshot()` samples are buffered and
    sent as *batch envelopes* (``uav.pqc.telemetry.batch.v1``).  The
    batching strategy reduces per-packet overhead and lets the drone's
    `TelemetryReceiver` ingest multiple timestamped samples at once.

    Batching rules
    ~~~~~~~~~~~~~~
    * A batch is flushed when *TELEMETRY_BATCH_SIZE* samples have
      accumulated **or** when *TELEMETRY_BATCH_INTERVAL_S* elapses since
      the first sample in the current batch – whichever comes first.
    """

    BATCH_SCHEMA = "uav.pqc.telemetry.batch.v1"

    def __init__(self, target_host: str, target_port: int):
        self.target_addr = (target_host, target_port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.seq = 0
        self._lock = threading.Lock()

        # Batch buffer
        self._batch: List[Dict[str, Any]] = []
        self._batch_start: float = 0.0

    # ---- low-level send ------------------------------------------------- #

    def _send_raw(self, payload: dict):
        """Fire-and-forget UDP send."""
        try:
            data = json.dumps(payload).encode("utf-8")
            self.sock.sendto(data, self.target_addr)
        except Exception:
            pass  # Best-effort

    # ---- public API ----------------------------------------------------- #

    def add_sample(self, snapshot: dict):
        """Add a single telemetry snapshot to the batch buffer.

        Automatically flushes when the batch is full or the interval
        expires.
        """
        with self._lock:
            now = time.monotonic()
            if not self._batch:
                self._batch_start = now

            self.seq += 1
            snapshot["batch_seq"] = self.seq
            self._batch.append(snapshot)

            # Flush conditions
            if (len(self._batch) >= TELEMETRY_BATCH_SIZE or
                    now - self._batch_start >= TELEMETRY_BATCH_INTERVAL_S):
                self._flush_locked()

    def flush(self):
        """Force-send whatever is currently buffered."""
        with self._lock:
            self._flush_locked()

    def _flush_locked(self):
        """Internal flush (caller holds self._lock)."""
        if not self._batch:
            return
        envelope = {
            "schema": self.BATCH_SCHEMA,
            "batch_wall_ns": time.time_ns(),
            "count": len(self._batch),
            "samples": self._batch,
        }
        self._send_raw(envelope)
        self._batch = []
        self._batch_start = 0.0

    def close(self):
        self.flush()
        try:
            self.sock.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Control Server  (TCP – GCS listens, Drone sends commands)
# ---------------------------------------------------------------------------

class ControlServer:
    """TCP JSON-RPC server that accepts commands from the drone scheduler.

    Supported commands
    ~~~~~~~~~~~~~~~~~~
    ping           – liveness check
    status         – proxy and MAVProxy health
    configure      – accept scheduling parameters from drone
    start_proxy    – start GCS PQC proxy for a given suite
    prepare_rekey  – tear down current proxy (drone about to switch suite)
    stop           – full shutdown
    get_suites     – return available suite names
    chronos_sync   – serve an NTP-lite clock synchronisation round
    """

    def __init__(self, proxy: GcsProxyManager):
        self.proxy = proxy
        self.clock_sync = ClockSync()

        # Persistent MAVProxy subprocess handle
        self.mavproxy_proc: Optional[ManagedProcess] = None

        # Telemetry subsystem
        self.telemetry = TelemetrySender(DRONE_HOST, GCS_TELEMETRY_PORT)
        self.metrics_collector = GcsMetricsCollector(
            mavlink_host="127.0.0.1",
            mavlink_port=GCS_TELEMETRY_SNIFF_PORT,
            proxy_manager=self.proxy,
            log_dir=LOGS_DIR / "telemetry",
        )

        # Server state
        self.server_sock: Optional[socket.socket] = None
        self.running = False
        self._server_thread: Optional[threading.Thread] = None
        self._telemetry_thread: Optional[threading.Thread] = None

        # Parameters pushed by drone (informational)
        self.configured_duration: float = 10.0

    # ------------------------------------------------------------------ #
    # Persistent MAVProxy  (GCS side)
    # ------------------------------------------------------------------ #

    def start_persistent_mavproxy(self) -> bool:
        """Start a long-lived MAVProxy for QGC and telemetry sniffing.

        Data path
        ~~~~~~~~~
        PQC Proxy → (GCS_PLAIN_RX_PORT) → MAVProxy →
            ├── udp:127.0.0.1:QGC_PORT        (QGroundControl)
            └── udp:127.0.0.1:SNIFF_PORT      (GcsMetricsCollector)
        """
        bind_host = str(CONFIG.get("GCS_PLAINTEXT_BIND", "0.0.0.0"))
        master_str = f"udpin:{bind_host}:{GCS_PLAIN_RX_PORT}"

        cmd = [
            sys.executable, "-m", "MAVProxy.mavproxy",
            f"--master={master_str}",
            "--dialect=ardupilotmega",
            "--nowait",
            "--map",
            "--console",
            f"--out=udp:127.0.0.1:{QGC_PORT}",
            f"--out=udp:127.0.0.1:{GCS_TELEMETRY_SNIFF_PORT}",
        ]

        log(f"Starting persistent MAVProxy: {' '.join(cmd)}")

        ts_str = time.strftime("%Y%m%d-%H%M%S")
        log_path = LOGS_DIR / f"mavproxy_gcs_{ts_str}.log"

        try:
            fh = open(log_path, "w", encoding="utf-8")
        except Exception:
            fh = subprocess.DEVNULL

        # Platform-specific I/O handles
        stdout_arg = fh
        stderr_arg = subprocess.STDOUT
        stdin_arg = subprocess.DEVNULL
        if sys.platform == "win32":
            # On Windows prompt_toolkit needs a real console; suppress
            # stdout/stderr to avoid crash while still capturing to log.
            stdout_arg = None
            stderr_arg = None
            stdin_arg = None

        env = os.environ.copy()
        env["TERM"] = "dumb"  # Prevent prompt_toolkit escape issues

        self.mavproxy_proc = ManagedProcess(
            cmd=cmd,
            name="mavproxy-gcs",
            stdout=stdout_arg,
            stderr=stderr_arg,
            stdin=stdin_arg,
            new_console=True,
            env=env,
        )

        if not self.mavproxy_proc.start():
            log("MAVProxy failed to start")
            return False

        # Update metrics collector with the process handle
        self.metrics_collector.mavproxy_proc = self.mavproxy_proc

        # Wait for TCP handshake port or process to settle
        if wait_for_tcp_port(TCP_CTRL_PORT, timeout=5.0):
            log("Persistent MAVProxy started (TCP port open)")
            return True
        if self.mavproxy_proc.is_running():
            log("Persistent MAVProxy started (process alive, port not yet ready)")
            return True

        log("Persistent MAVProxy failed to start")
        return False

    # ------------------------------------------------------------------ #
    # TCP control server lifecycle
    # ------------------------------------------------------------------ #

    def start(self):
        """Bind TCP listener and start the telemetry loop."""
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_sock.bind((GCS_CONTROL_HOST, GCS_CONTROL_PORT))
        self.server_sock.listen(5)
        self.server_sock.settimeout(1.0)

        self.running = True

        self._server_thread = threading.Thread(
            target=self._server_loop, daemon=True, name="ctrl-server"
        )
        self._server_thread.start()

        # Start GCS metrics collector
        self.metrics_collector.start()

        # Start telemetry loop (sends batched snapshots to drone)
        self._telemetry_thread = threading.Thread(
            target=self._telemetry_loop, daemon=True, name="telem-sender"
        )
        self._telemetry_thread.start()

        log(f"Control server listening on {GCS_CONTROL_HOST}:{GCS_CONTROL_PORT}")

    def stop(self):
        """Graceful shutdown of all server components."""
        self.running = False

        if self._server_thread:
            self._server_thread.join(timeout=2.0)
        if self._telemetry_thread:
            self._telemetry_thread.join(timeout=2.0)
        if self.metrics_collector:
            self.metrics_collector.stop()
        if self.telemetry:
            self.telemetry.close()
        if self.server_sock:
            try:
                self.server_sock.close()
            except Exception:
                pass
        if self.mavproxy_proc:
            try:
                self.mavproxy_proc.stop()
            except Exception:
                pass
            self.mavproxy_proc = None

    # ------------------------------------------------------------------ #
    # Telemetry loop  (5 Hz → batched at ~1 Hz to drone)
    # ------------------------------------------------------------------ #

    def _telemetry_loop(self):
        """Collect GcsMetricsCollector snapshots and feed into batcher."""
        interval_s = 1.0 / TELEMETRY_HZ
        while self.running:
            try:
                snapshot = self.metrics_collector.get_snapshot()
                self.telemetry.add_sample(snapshot)
            except Exception:
                pass
            time.sleep(interval_s)

        # Final flush on shutdown
        try:
            self.telemetry.flush()
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    # TCP server loop + client handling
    # ------------------------------------------------------------------ #

    def _server_loop(self):
        while self.running:
            try:
                client, addr = self.server_sock.accept()
                threading.Thread(
                    target=self._handle_client,
                    args=(client, addr),
                    daemon=True,
                ).start()
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    log(f"Server accept error: {e}")

    def _handle_client(self, client: socket.socket, addr):
        try:
            client.settimeout(10.0)
            buf = b""
            while True:
                chunk = client.recv(4096)
                if not chunk:
                    break
                buf += chunk
                if b"\n" in buf:
                    break
                # Heuristic: complete JSON object received
                stripped = buf.strip()
                if stripped.endswith(b"}"):
                    break

            if buf:
                try:
                    request = json.loads(buf.decode("utf-8").strip())
                    response = self._handle_command(request)
                    client.sendall(json.dumps(response).encode("utf-8") + b"\n")
                except json.JSONDecodeError:
                    err = {"status": "error", "message": "invalid json"}
                    client.sendall(json.dumps(err).encode("utf-8") + b"\n")
        except Exception as e:
            log(f"Client handler error ({addr}): {e}")
        finally:
            try:
                client.close()
            except Exception:
                pass

    # ------------------------------------------------------------------ #
    # Command dispatch
    # ------------------------------------------------------------------ #

    def _handle_command(self, request: dict) -> dict:
        cmd = request.get("cmd", "")

        # ----- ping ----- #
        if cmd == "ping":
            return {
                "status": "ok",
                "message": "pong",
                "role": "gcs_follower",
            }

        # ----- status ----- #
        if cmd == "status":
            return {
                "status": "ok",
                "proxy_running": self.proxy.is_running(),
                "current_suite": self.proxy.current_suite,
                "mavproxy_running": bool(
                    self.mavproxy_proc and self.mavproxy_proc.is_running()
                ),
            }

        # ----- configure ----- #
        if cmd == "configure":
            self.configured_duration = request.get("duration", 10.0)
            log(f"Configured: duration={self.configured_duration}s")
            return {"status": "ok", "message": "configured"}

        # ----- start_proxy ----- #
        if cmd == "start_proxy":
            suite = request.get("suite")
            if not suite:
                return {"status": "error", "message": "missing suite"}

            log(f"start_proxy requested: {suite}")
            if not self.proxy.start(suite):
                return {"status": "error", "message": "proxy_start_failed"}

            # Verify persistent MAVProxy is still alive
            if not (self.mavproxy_proc and self.mavproxy_proc.is_running()):
                log("WARNING: persistent MAVProxy is not running")
                return {"status": "error", "message": "mavproxy_not_running"}

            return {"status": "ok", "message": "proxy_started"}

        # ----- prepare_rekey ----- #
        if cmd == "prepare_rekey":
            log("prepare_rekey: stopping GCS proxy …")
            self.proxy.stop()
            # Persistent MAVProxy stays alive across rekeys.
            return {"status": "ok", "message": "ready_for_rekey"}

        # ----- stop ----- #
        if cmd == "stop":
            log("stop command received – tearing down")
            self.proxy.stop()
            if self.mavproxy_proc:
                try:
                    self.mavproxy_proc.stop()
                except Exception:
                    pass
                self.mavproxy_proc = None
            return {"status": "ok", "message": "stopped"}

        # ----- get_suites ----- #
        if cmd == "get_suites":
            return {
                "status": "ok",
                "suites": [s["name"] for s in ALL_SUITES],
            }

        # ----- chronos_sync ----- #
        if cmd == "chronos_sync":
            try:
                return self.clock_sync.server_handle_sync(request)
            except Exception as e:
                return {"status": "error", "message": str(e)}

        return {"status": "error", "message": f"unknown command: {cmd}"}


# ---------------------------------------------------------------------------
# Process cleanup
# ---------------------------------------------------------------------------

def cleanup_stale_processes():
    """Best-effort cleanup of orphaned mavproxy / proxy processes."""
    my_pid = os.getpid()
    targets = ["mavproxy", "core.run_proxy"]

    if sys.platform.startswith("win"):
        for t in targets:
            query = (
                f"name='python.exe' and commandline like '%{t}%' "
                f"and ProcessId!={my_pid}"
            )
            cmd = f'wmic process where "{query}" call terminate'
            try:
                subprocess.run(
                    cmd, shell=True,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
            except Exception:
                pass
    else:
        for t in targets:
            subprocess.run(
                ["pkill", "-f", t],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
    time.sleep(1.0)


# ===========================================================================
# Main
# ===========================================================================

def main() -> int:
    parser = argparse.ArgumentParser(
        description="GCS MAV-to-MAV PQC Tunnel Follower",
    )
    parser.add_argument(
        "--no-mavproxy",
        action="store_true",
        help="Skip starting persistent MAVProxy (for testing without FC)",
    )
    parser.add_argument(
        "--no-cleanup",
        action="store_true",
        help="Skip stale-process cleanup on startup",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(name)-12s  %(levelname)-7s  %(message)s",
    )

    print("=" * 60)
    print("  GCS MAV-to-MAV PQC Tunnel Follower")
    print("=" * 60)

    # Dump configuration for debugging
    cfg_dump = {
        "DRONE_HOST": DRONE_HOST,
        "GCS_HOST": GCS_HOST,
        "GCS_CONTROL_BIND": f"{GCS_CONTROL_HOST}:{GCS_CONTROL_PORT}",
        "GCS_PLAINTEXT_RX": GCS_PLAIN_RX_PORT,
        "GCS_PLAINTEXT_TX": GCS_PLAIN_TX_PORT,
        "QGC_PORT": QGC_PORT,
        "SNIFF_PORT": GCS_TELEMETRY_SNIFF_PORT,
        "TELEMETRY_TARGET": f"{DRONE_HOST}:{GCS_TELEMETRY_PORT}",
    }
    log("Configuration:")
    for k, v in cfg_dump.items():
        log(f"  {k}: {v}")

    # Cleanup stale processes
    if not args.no_cleanup:
        cleanup_stale_processes()

    atexit.register(cleanup_stale_processes)

    # Initialise components
    proxy = GcsProxyManager()
    control = ControlServer(proxy)

    # Start persistent MAVProxy
    if not args.no_mavproxy:
        ok = control.start_persistent_mavproxy()
        if ok:
            log("Persistent MAVProxy started")
        else:
            log("ERROR: persistent MAVProxy failed – aborting")
            return 2
    else:
        log("Persistent MAVProxy skipped (--no-mavproxy)")

    # Start control server + telemetry loop
    control.start()

    log("GCS follower running.  Waiting for commands from drone …")

    # Block until interrupted
    shutdown = threading.Event()

    def _sighandler(sig, frame):
        log("Interrupted – shutting down")
        shutdown.set()

    signal.signal(signal.SIGINT, _sighandler)
    signal.signal(signal.SIGTERM, _sighandler)

    try:
        while not shutdown.is_set():
            shutdown.wait(timeout=1.0)
    finally:
        log("Shutting down …")
        control.stop()
        proxy.stop()

    log("GCS follower stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
