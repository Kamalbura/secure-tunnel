#!/usr/bin/env python3
"""Simplified GCS Scheduler - Runs all PQC suites with high-throughput traffic.

This scheduler:
1. Starts GCS proxy for each suite sequentially
2. Generates 110 Mbps UDP traffic for 10 seconds per suite
3. Sends rekey commands to drone scheduler for suite transitions
4. Iterates through all available suites automatically

No benchmarking, no power monitoring - just robust PQC tunnel operation.
"""

# --------------------
# Local editable configuration (edit here, no CLI args needed)
# Keep this block within the first ~10 lines of the file for easy editing.
# --------------------
# Set to None to use defaults or auto-detection.
LOCAL_BANDWIDTH_MBPS = 110.0
LOCAL_DURATION_S = 10.0
LOCAL_PAYLOAD_BYTES = 1200
LOCAL_SUITES = None  # e.g. ['cs-mlkem768-aesgcm-mldsa65'] or None to run all
LOCAL_MAX_SUITES = None  # e.g. 2 to limit number of suites


from __future__ import annotations

import sys
from pathlib import Path


def _ensure_core_importable() -> Path:
    """Guarantee the repository root is on sys.path before importing core."""
    root = Path(__file__).resolve().parents[1]
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
    try:
        __import__("core")
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            f"Unable to import 'core'; repo root {root} missing from sys.path."
        ) from exc
    return root


ROOT = _ensure_core_importable()

import argparse
import json
import os
import signal
import socket
import struct
import subprocess
import threading
import time
from dataclasses import dataclass
from typing import Dict, IO, List, Optional, Tuple

from core.config import CONFIG
from core import suites as suites_mod
from core.suites import DEFAULT_SUITE_ID, get_suite, list_suites

# ---------------------------------------------------------------------------
# Configuration from core.config (same as gcs_scheduler.py)
# ---------------------------------------------------------------------------

DRONE_HOST = CONFIG["DRONE_HOST"]
GCS_HOST = CONFIG["GCS_HOST"]

CONTROL_PORT = int(CONFIG.get("DRONE_CONTROL_PORT", 48080))

APP_SEND_HOST = CONFIG.get("GCS_PLAINTEXT_HOST", "127.0.0.1")
APP_SEND_PORT = int(CONFIG.get("GCS_PLAINTEXT_TX", 47001))
APP_RECV_HOST = CONFIG.get("GCS_PLAINTEXT_HOST", "127.0.0.1")
APP_RECV_PORT = int(CONFIG.get("GCS_PLAINTEXT_RX", 47002))

SECRETS_DIR = ROOT / "secrets/matrix"
LOGS_DIR = ROOT / "logs/scheduler/gcs"

# Traffic defaults
DEFAULT_BANDWIDTH_MBPS = 110.0
DEFAULT_DURATION_S = 10.0
DEFAULT_PAYLOAD_BYTES = 1200  # Near MTU for efficiency

# ---------------------------------------------------------------------------
# Utility Functions
# ---------------------------------------------------------------------------

def ts() -> str:
    """Return ISO timestamp."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def log(msg: str) -> None:
    """Print timestamped log message."""
    print(f"[{ts()}] [sgcs] {msg}", flush=True)


def get_available_suites() -> List[str]:
    """Return list of suite IDs that have keys in secrets/matrix/."""
    available = []
    all_suites = list_suites()
    
    for suite_id in sorted(all_suites.keys()):
        suite_dir = SECRETS_DIR / suite_id
        key_file = suite_dir / "gcs_signing.key"
        if key_file.exists():
            available.append(suite_id)
    
    return available


def popen(cmd: List[str], **kwargs) -> subprocess.Popen:
    """Launch subprocess with proper flags."""
    if sys.platform == "win32":
        kwargs.setdefault("creationflags", subprocess.CREATE_NEW_PROCESS_GROUP)
    return subprocess.Popen(cmd, **kwargs)


def killtree(proc: subprocess.Popen) -> None:
    """Terminate process tree."""
    try:
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                capture_output=True,
                timeout=5,
            )
        else:
            import os as _os
            _os.killpg(_os.getpgid(proc.pid), signal.SIGKILL)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Drone Control Client
# ---------------------------------------------------------------------------

def send_control_command(host: str, port: int, cmd: Dict, timeout: float = 30.0) -> Dict:
    """Send command to drone control server and return response."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((host, port))
        sock.sendall(json.dumps(cmd).encode("utf-8"))
        response = sock.recv(65535)
        return json.loads(response.decode("utf-8"))
    finally:
        sock.close()


def ping_drone(host: str, port: int) -> bool:
    """Check if drone control server is responding."""
    try:
        response = send_control_command(host, port, {"cmd": "ping"}, timeout=5.0)
        return response.get("status") == "ok"
    except Exception:
        return False


def start_drone_proxy(host: str, port: int, suite: str, timeout: float = 45.0) -> Dict:
    """Send start command to drone to initiate its proxy."""
    return send_control_command(host, port, {"cmd": "start", "suite": suite}, timeout=timeout)


def rekey_drone(host: str, port: int, suite: str, timeout: float = 45.0) -> Dict:
    """Send rekey command to drone."""
    return send_control_command(host, port, {"cmd": "rekey", "suite": suite}, timeout=timeout)


def get_drone_status(host: str, port: int) -> Dict:
    """Get current status from drone."""
    return send_control_command(host, port, {"cmd": "status"}, timeout=10.0)


def stop_drone(host: str, port: int) -> Dict:
    """Send stop command to drone."""
    return send_control_command(host, port, {"cmd": "stop"}, timeout=5.0)


# ---------------------------------------------------------------------------
# Traffic Generator
# ---------------------------------------------------------------------------

@dataclass
class TrafficStats:
    """Traffic statistics."""
    tx_packets: int = 0
    rx_packets: int = 0
    tx_bytes: int = 0
    rx_bytes: int = 0
    start_time: float = 0.0
    end_time: float = 0.0
    
    @property
    def duration_s(self) -> float:
        return self.end_time - self.start_time if self.end_time > self.start_time else 0.0
    
    @property
    def delivery_ratio(self) -> float:
        return self.rx_packets / self.tx_packets if self.tx_packets > 0 else 0.0
    
    @property
    def tx_mbps(self) -> float:
        return (self.tx_bytes * 8 / 1_000_000) / self.duration_s if self.duration_s > 0 else 0.0
    
    @property
    def rx_mbps(self) -> float:
        return (self.rx_bytes * 8 / 1_000_000) / self.duration_s if self.duration_s > 0 else 0.0


class TrafficGenerator:
    """High-throughput UDP traffic generator with receiver."""
    
    def __init__(
        self,
        tx_host: str,
        tx_port: int,
        rx_host: str,
        rx_port: int,
        payload_bytes: int = 1200,
        target_mbps: float = 110.0,
    ):
        self.tx_host = tx_host
        self.tx_port = tx_port
        self.rx_host = rx_host
        self.rx_port = rx_port
        self.payload_bytes = payload_bytes
        self.target_mbps = target_mbps
        
        # Calculate packets per second for target bandwidth
        # bandwidth = pps * packet_size * 8
        # pps = bandwidth / (packet_size * 8)
        self.target_pps = int((target_mbps * 1_000_000) / (payload_bytes * 8))
        
        self._stop_event = threading.Event()
        self._stats = TrafficStats()
        self._stats_lock = threading.Lock()
    
    def run(self, duration_s: float) -> TrafficStats:
        """Run traffic for specified duration and return stats."""
        self._stop_event.clear()
        self._stats = TrafficStats()
        
        # Start receiver thread
        rx_thread = threading.Thread(target=self._receiver_loop, daemon=True)
        rx_thread.start()
        
        # Small delay for receiver to bind
        time.sleep(0.1)
        
        # Run transmitter
        self._transmitter_loop(duration_s)
        
        # Wait a bit for final packets
        time.sleep(0.5)
        self._stop_event.set()
        rx_thread.join(timeout=2.0)
        
        with self._stats_lock:
            return TrafficStats(
                tx_packets=self._stats.tx_packets,
                rx_packets=self._stats.rx_packets,
                tx_bytes=self._stats.tx_bytes,
                rx_bytes=self._stats.rx_bytes,
                start_time=self._stats.start_time,
                end_time=self._stats.end_time,
            )
    
    def _transmitter_loop(self, duration_s: float) -> None:
        """Send packets at target rate."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4 * 1024 * 1024)
        except Exception:
            pass
        
        # Pre-generate payload template
        payload_template = bytearray(self.payload_bytes)
        
        interval = 1.0 / self.target_pps if self.target_pps > 0 else 0.001
        batch_size = max(1, self.target_pps // 100)  # Send in batches for efficiency
        batch_interval = interval * batch_size
        
        start_time = time.perf_counter()
        with self._stats_lock:
            self._stats.start_time = time.time()
        
        seq = 0
        next_batch_time = start_time
        
        while True:
            now = time.perf_counter()
            elapsed = now - start_time
            
            if elapsed >= duration_s:
                break
            
            # Send batch
            for _ in range(batch_size):
                # Embed sequence number in payload
                struct.pack_into(">I", payload_template, 0, seq)
                struct.pack_into(">d", payload_template, 4, time.time())
                
                try:
                    sock.sendto(bytes(payload_template), (self.tx_host, self.tx_port))
                    with self._stats_lock:
                        self._stats.tx_packets += 1
                        self._stats.tx_bytes += len(payload_template)
                except Exception:
                    pass
                
                seq += 1
            
            # Rate limiting
            next_batch_time += batch_interval
            sleep_time = next_batch_time - time.perf_counter()
            if sleep_time > 0:
                time.sleep(sleep_time)
        
        with self._stats_lock:
            self._stats.end_time = time.time()
        
        sock.close()
    
    def _receiver_loop(self) -> None:
        """Receive and count packets."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 * 1024 * 1024)
        except Exception:
            pass
        sock.bind((self.rx_host, self.rx_port))
        sock.settimeout(0.1)
        
        while not self._stop_event.is_set():
            try:
                data, addr = sock.recvfrom(65535)
                with self._stats_lock:
                    self._stats.rx_packets += 1
                    self._stats.rx_bytes += len(data)
            except socket.timeout:
                continue
            except Exception:
                if not self._stop_event.is_set():
                    pass
        
        sock.close()


# ---------------------------------------------------------------------------
# Proxy Management
# ---------------------------------------------------------------------------

def start_gcs_proxy(suite: str) -> Tuple[subprocess.Popen, IO[str]]:
    """Start GCS proxy for the given suite."""
    suite_dir = SECRETS_DIR / suite
    key_file = suite_dir / "gcs_signing.key"
    
    if not key_file.exists():
        raise FileNotFoundError(f"Secret key not found: {key_file}")
    
    # Set environment
    env = os.environ.copy()
    env["DRONE_HOST"] = DRONE_HOST
    env["GCS_HOST"] = GCS_HOST
    env["ENABLE_PACKET_TYPE"] = "1" if CONFIG.get("ENABLE_PACKET_TYPE", True) else "0"
    env["STRICT_UDP_PEER_MATCH"] = "1" if CONFIG.get("STRICT_UDP_PEER_MATCH", True) else "0"
    
    root_str = str(ROOT)
    existing_py_path = env.get("PYTHONPATH")
    if existing_py_path:
        if root_str not in existing_py_path.split(os.pathsep):
            env["PYTHONPATH"] = root_str + os.pathsep + existing_py_path
    else:
        env["PYTHONPATH"] = root_str
    
    # Create log directory
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOGS_DIR / f"gcs_{suite}_{time.strftime('%Y%m%d-%H%M%S')}.log"
    log_handle = open(log_path, "w", encoding="utf-8")
    
    cmd = [
        sys.executable,
        "-m", "core.run_proxy",
        "gcs",
        "--suite", suite,
        "--gcs-secret-file", str(key_file),
        "--quiet",
    ]
    
    log(f"Launching: {' '.join(cmd)}")
    
    proc = popen(
        cmd,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
        cwd=str(ROOT),
    )
    
    return proc, log_handle


# ---------------------------------------------------------------------------
# Suite Runner
# ---------------------------------------------------------------------------

@dataclass
class SuiteResult:
    """Result from running a single suite."""
    suite_id: str
    success: bool
    stats: Optional[TrafficStats]
    error: Optional[str]
    handshake_time_s: float
    traffic_time_s: float


def run_suite(
    suite_id: str,
    drone_host: str,
    drone_port: int,
    bandwidth_mbps: float,
    duration_s: float,
    payload_bytes: int,
    is_first: bool = False,
) -> SuiteResult:
    """Run a single suite: start proxy, handshake, run traffic."""
    log(f"{'='*60}")
    log(f"Running suite: {suite_id}")
    log(f"{'='*60}")
    
    gcs_proc = None
    gcs_log = None
    handshake_time = 0.0
    traffic_time = 0.0
    
    try:
        # For first suite: start GCS proxy first, then tell drone to start
        # For subsequent suites: stop current, rekey drone, then start new GCS
        
        if is_first:
            # Start GCS proxy first (it listens for handshake)
            log(f"Starting GCS proxy (first suite)...")
            proxy_start = time.time()
            gcs_proc, gcs_log = start_gcs_proxy(suite_id)
            
            # Wait for GCS to be ready
            time.sleep(2)
            
            if gcs_proc.poll() is not None:
                return SuiteResult(suite_id, False, None, f"GCS proxy exited with {gcs_proc.returncode}", 0, 0)
            
            # Now tell drone to start its proxy
            log(f"Sending start command to drone...")
            try:
                response = start_drone_proxy(drone_host, drone_port, suite_id)
                if response.get("status") != "ok":
                    error = response.get("error", "unknown")
                    return SuiteResult(suite_id, False, None, f"Drone start failed: {error}", 0, 0)
            except Exception as e:
                return SuiteResult(suite_id, False, None, f"Drone start error: {e}", 0, 0)
            
            log(f"Drone started")
        else:
            # Rekey sequence:
            # 1. Tell drone to prepare for rekey (stop its proxy)
            # 2. Start new GCS proxy
            # 3. Tell drone to start with new suite
            
            log(f"Preparing for rekey...")
            
            # Tell drone to stop its proxy first
            try:
                response = send_control_command(drone_host, drone_port, {"cmd": "prepare_rekey"}, timeout=15.0)
                # prepare_rekey may not exist, fall back to regular rekey behavior
            except Exception:
                pass
            
            # Start GCS proxy first
            log(f"Starting GCS proxy...")
            proxy_start = time.time()
            gcs_proc, gcs_log = start_gcs_proxy(suite_id)
            
            # Wait for GCS to be ready
            time.sleep(2)
            
            if gcs_proc.poll() is not None:
                return SuiteResult(suite_id, False, None, f"GCS proxy exited with {gcs_proc.returncode}", 0, 0)
            
            # Now tell drone to start with new suite
            log(f"Sending start command to drone for rekey...")
            try:
                response = start_drone_proxy(drone_host, drone_port, suite_id)
                if response.get("status") != "ok":
                    error = response.get("error", "unknown")
                    # If already running, try rekey instead
                    if "already_running" in str(error):
                        response = rekey_drone(drone_host, drone_port, suite_id)
                        if response.get("status") != "ok":
                            return SuiteResult(suite_id, False, None, f"Drone rekey failed: {response.get('error', 'unknown')}", 0, 0)
                    else:
                        return SuiteResult(suite_id, False, None, f"Drone start failed: {error}", 0, 0)
            except Exception as e:
                return SuiteResult(suite_id, False, None, f"Drone start error: {e}", 0, 0)
            
            log(f"Drone started for rekey")
        
        # Wait for handshake
        log(f"Waiting for handshake...")
        handshake_timeout = 30.0
        handshake_start = time.time()
        
        while time.time() - handshake_start < handshake_timeout:
            if gcs_proc.poll() is not None:
                return SuiteResult(suite_id, False, None, f"GCS proxy exited with {gcs_proc.returncode}", 0, 0)
            
            # Check if drone has the same suite
            try:
                status = get_drone_status(drone_host, drone_port)
                if status.get("suite") == suite_id and status.get("proxy_running"):
                    break
            except Exception:
                pass
            
            time.sleep(0.5)
        else:
            return SuiteResult(suite_id, False, None, "Handshake timeout", 0, 0)
        
        handshake_time = time.time() - handshake_start
        log(f"Handshake complete in {handshake_time:.2f}s")
        
        # Small settle time
        time.sleep(1.0)
        
        # Run traffic
        log(f"Starting traffic: {bandwidth_mbps:.1f} Mbps for {duration_s:.1f}s")
        traffic_start = time.time()
        
        generator = TrafficGenerator(
            APP_SEND_HOST, APP_SEND_PORT,
            APP_RECV_HOST, APP_RECV_PORT,
            payload_bytes=payload_bytes,
            target_mbps=bandwidth_mbps,
        )
        
        stats = generator.run(duration_s)
        traffic_time = time.time() - traffic_start
        
        log(f"Traffic complete:")
        log(f"  TX: {stats.tx_packets:,} packets, {stats.tx_bytes:,} bytes, {stats.tx_mbps:.1f} Mbps")
        log(f"  RX: {stats.rx_packets:,} packets, {stats.rx_bytes:,} bytes, {stats.rx_mbps:.1f} Mbps")
        log(f"  Delivery: {stats.delivery_ratio*100:.1f}%")
        
        # Stop GCS proxy
        if gcs_proc and gcs_proc.poll() is None:
            gcs_proc.terminate()
            try:
                gcs_proc.wait(timeout=5)
            except Exception:
                killtree(gcs_proc)
        
        if gcs_log:
            try:
                gcs_log.close()
            except Exception:
                pass
        
        success = stats.delivery_ratio > 0.5  # At least 50% delivery
        
        return SuiteResult(suite_id, success, stats, None, handshake_time, traffic_time)
        
    except Exception as e:
        log(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        
        # Cleanup
        if gcs_proc and gcs_proc.poll() is None:
            try:
                gcs_proc.terminate()
                gcs_proc.wait(timeout=3)
            except Exception:
                killtree(gcs_proc)
        
        if gcs_log:
            try:
                gcs_log.close()
            except Exception:
                pass
        
        return SuiteResult(suite_id, False, None, str(e), handshake_time, traffic_time)


# ---------------------------------------------------------------------------
# Main Entry Point
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Simplified GCS Scheduler - Run all PQC suites with traffic"
    )
    parser.add_argument(
        "--drone-host",
        default=DRONE_HOST,
        help=f"Drone control host (default: {DRONE_HOST})",
    )
    parser.add_argument(
        "--drone-port",
        type=int,
        default=CONTROL_PORT,
        help=f"Drone control port (default: {CONTROL_PORT})",
    )
    parser.add_argument(
        "--bandwidth",
        type=float,
        default=DEFAULT_BANDWIDTH_MBPS,
        help=f"Target bandwidth in Mbps (default: {DEFAULT_BANDWIDTH_MBPS})",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=DEFAULT_DURATION_S,
        help=f"Duration per suite in seconds (default: {DEFAULT_DURATION_S})",
    )
    parser.add_argument(
        "--payload",
        type=int,
        default=DEFAULT_PAYLOAD_BYTES,
        help=f"UDP payload size in bytes (default: {DEFAULT_PAYLOAD_BYTES})",
    )
    parser.add_argument(
        "--suite",
        default=None,
        help="Run only this suite (default: run all)",
    )
    parser.add_argument(
        "--suites",
        default=None,
        help="Comma-separated list of suites to run",
    )
    parser.add_argument(
        "--nist-level",
        default=None,
        help="Filter suites by NIST level (L1, L3, L5)",
    )
    parser.add_argument(
        "--inter-gap",
        type=float,
        default=2.0,
        help="Gap between suites in seconds (default: 2.0)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    
    print("=" * 60)
    print("Simplified GCS Scheduler (sgcs)")
    print("=" * 60)
    log(f"DRONE_HOST={DRONE_HOST}, GCS_HOST={GCS_HOST}")
    log(f"Drone control: {args.drone_host}:{args.drone_port}")
    log(f"Traffic: {args.bandwidth:.1f} Mbps, {args.duration:.1f}s per suite, {args.payload} byte payload")
    
    # Get available suites
    available_suites = get_available_suites()
    if not available_suites:
        log("ERROR: No suites with keys found in secrets/matrix/")
        return 1

    # Apply local in-file configuration overrides (if set)
    if LOCAL_BANDWIDTH_MBPS is not None:
        args.bandwidth = float(LOCAL_BANDWIDTH_MBPS)
    if LOCAL_DURATION_S is not None:
        args.duration = float(LOCAL_DURATION_S)
    if LOCAL_PAYLOAD_BYTES is not None:
        args.payload = int(LOCAL_PAYLOAD_BYTES)

    # If LOCAL_SUITES provided, use it. Otherwise, optionally cap with LOCAL_MAX_SUITES
    if LOCAL_SUITES:
        suites_to_run = [s for s in LOCAL_SUITES if s in available_suites]
        if not suites_to_run:
            log("ERROR: None of the LOCAL_SUITES are available")
            return 1
    else:
        suites_to_run = available_suites
        if LOCAL_MAX_SUITES:
            suites_to_run = suites_to_run[: int(LOCAL_MAX_SUITES)]
    
    log(f"Available suites: {len(available_suites)}")
    
    # NIST-level filtering (CLI still supported)
    if args.nist_level:
        level = args.nist_level.upper()
        if not level.startswith("L"):
            level = f"L{level}"

        filtered = []
        all_suites_info = list_suites()
        for suite_id in suites_to_run:
            suite_info = all_suites_info.get(suite_id, {})
            if suite_info.get("nist_level") == level:
                filtered.append(suite_id)

        if not filtered:
            log(f"ERROR: No suites match NIST level {level}")
            return 1
        suites_to_run = filtered
    
    log(f"Suites to run: {len(suites_to_run)}")
    
    # Wait for drone to be ready
    log("Waiting for drone scheduler...")
    max_wait = 60
    start_wait = time.time()
    
    while time.time() - start_wait < max_wait:
        if ping_drone(args.drone_host, args.drone_port):
            log("Drone scheduler is ready")
            break
        time.sleep(1)
    else:
        log("ERROR: Drone scheduler not responding")
        return 1
    
    # Run suites
    results: List[SuiteResult] = []
    
    for idx, suite_id in enumerate(suites_to_run):
        is_first = (idx == 0)
        
        result = run_suite(
            suite_id,
            args.drone_host,
            args.drone_port,
            args.bandwidth,
            args.duration,
            args.payload,
            is_first=is_first,
        )
        results.append(result)
        
        # Inter-suite gap
        if idx < len(suites_to_run) - 1:
            log(f"Waiting {args.inter_gap:.1f}s before next suite...")
            time.sleep(args.inter_gap)
    
    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for result in results:
        status = "PASS" if result.success else "FAIL"
        if result.success:
            passed += 1
            if result.stats:
                print(f"  [{status}] {result.suite_id}: {result.stats.delivery_ratio*100:.1f}% delivery, "
                      f"{result.stats.tx_mbps:.1f}/{result.stats.rx_mbps:.1f} Mbps TX/RX")
            else:
                print(f"  [{status}] {result.suite_id}")
        else:
            failed += 1
            print(f"  [{status}] {result.suite_id}: {result.error}")
    
    print("-" * 60)
    print(f"Total: {len(results)}, Passed: {passed}, Failed: {failed}")
    print("=" * 60)
    
    # Stop drone
    log("Sending stop command to drone...")
    try:
        stop_drone(args.drone_host, args.drone_port)
    except Exception:
        pass
    
    log("GCS scheduler complete")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
