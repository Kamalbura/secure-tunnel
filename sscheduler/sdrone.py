#!/usr/bin/env python3
"""
Simplified Drone Scheduler (CONTROLLER) - sscheduler/sdrone.py

REVERSED CONTROL: Drone is the controller, GCS follows.
- Drone decides suite order, timing, rekey
- Drone sends commands to GCS
- Drone runs echo server (receives traffic from GCS)
- Drone starts its proxy first, then tells GCS to start

Usage:
    python -m sscheduler.sdrone [options]

Environment:
    DRONE_HOST          Drone IP (default: from config)
    GCS_HOST            GCS IP (default: from config)
    GCS_CONTROL_HOST    GCS control server IP (default: GCS_HOST)
"""

import os
import sys
import time
import json
import socket
import signal
import argparse
import threading
import subprocess
import logging
from pathlib import Path
from datetime import datetime, timezone

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import CONFIG
from core.suites import get_suite, list_suites
from tools.mavproxy_manager import MavProxyManager
from sscheduler.policy import LinearLoopPolicy, RandomPolicy, ManualOverridePolicy

# Extract config values (use CONFIG as single source of truth)
DRONE_HOST = str(CONFIG.get("DRONE_HOST"))
GCS_HOST = str(CONFIG.get("GCS_HOST"))
DRONE_PLAIN_RX_PORT = int(CONFIG.get("DRONE_PLAINTEXT_RX", 47004))
DRONE_PLAIN_TX_PORT = int(CONFIG.get("DRONE_PLAINTEXT_TX", 47003))

# Control endpoint for GCS: use configured GCS_HOST and GCS_CONTROL_PORT
GCS_CONTROL_HOST = str(CONFIG.get("GCS_HOST"))
GCS_CONTROL_PORT = int(CONFIG.get("GCS_CONTROL_PORT", 48080))

# Derived internal proxy control port to avoid collisions
PROXY_INTERNAL_CONTROL_PORT = GCS_CONTROL_PORT + 100

DEFAULT_SUITE = "cs-mlkem768-aesgcm-mldsa65"
SECRETS_DIR = Path(__file__).parent.parent / "secrets" / "matrix"

# Traffic settings (for telling GCS how long to run)
DEFAULT_DURATION = 10.0  # seconds per suite
DEFAULT_RATE_MBPS = 110.0
PAYLOAD_SIZE = 1200

# --------------------
# Local editable configuration (edit here, no CLI args needed)
# --------------------
LOCAL_DURATION = None  # override DEFAULT_DURATION if set, e.g. 10.0
LOCAL_RATE_MBPS = None  # override DEFAULT_RATE_MBPS if set, e.g. 110.0
LOCAL_MAX_SUITES = None  # limit suites run, e.g. 2
LOCAL_SUITES = None  # list of suite names to run, or None

# Get all suites (list_suites returns dict, convert to list of dicts)
_suites_dict = list_suites()
SUITES = [{"name": k, **v} for k, v in _suites_dict.items()]

ROOT = Path(__file__).resolve().parents[1]
LOGS_DIR = ROOT / "logs" / "sscheduler" / "drone"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================
# Logging
# ============================================================

def log(msg: str):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"[{ts}] [sdrone-ctrl] {msg}", flush=True)

# ============================================================
# UDP Echo Server (drone receives traffic from GCS)
# ============================================================

class UdpEchoServer:
    """Echoes UDP packets: receives on DRONE_PLAIN_RX, sends back on DRONE_PLAIN_TX"""
    
    def __init__(self):
        self.rx_sock = None
        self.tx_sock = None
        self.running = False
        self.thread = None
        self.rx_count = 0
        self.tx_count = 0
        self.rx_bytes = 0
        self.tx_bytes = 0
        self.lock = threading.Lock()
    
    def start(self):
        if self.running:
            return
        
        self.rx_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.rx_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.rx_sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 * 1024 * 1024)
        self.rx_sock.bind((DRONE_HOST, DRONE_PLAIN_RX_PORT))
        self.rx_sock.settimeout(1.0)
        
        self.tx_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.tx_sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4 * 1024 * 1024)
        
        self.running = True
        self.thread = threading.Thread(target=self._echo_loop, daemon=True)
        self.thread.start()
        
        log(f"Echo server listening on {DRONE_HOST}:{DRONE_PLAIN_RX_PORT}")
    
    def _echo_loop(self):
        while self.running:
            try:
                data, addr = self.rx_sock.recvfrom(65535)
                with self.lock:
                    self.rx_count += 1
                    self.rx_bytes += len(data)
                
                self.tx_sock.sendto(data, (DRONE_HOST, DRONE_PLAIN_TX_PORT))
                with self.lock:
                    self.tx_count += 1
                    self.tx_bytes += len(data)
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    log(f"Echo error: {e}")
    
    def get_stats(self):
        with self.lock:
            return {
                "rx_count": self.rx_count,
                "tx_count": self.tx_count,
                "rx_bytes": self.rx_bytes,
                "tx_bytes": self.tx_bytes,
            }
    
    def reset_stats(self):
        with self.lock:
            self.rx_count = 0
            self.tx_count = 0
            self.rx_bytes = 0
            self.tx_bytes = 0
    
    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)
        if self.rx_sock:
            self.rx_sock.close()
        if self.tx_sock:
            self.tx_sock.close()


# MavProxyManager imported from tools.mavproxy_manager

# ============================================================
# GCS Control Client (drone sends commands to GCS)
# ============================================================

def send_gcs_command(cmd: str, **params) -> dict:
    """Send command to GCS control server"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(30.0)
        sock.connect((GCS_CONTROL_HOST, GCS_CONTROL_PORT))
        
        request = {"cmd": cmd, **params}
        sock.sendall(json.dumps(request).encode() + b"\n")
        
        response = b""
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            response += chunk
            if b"\n" in response:
                break
        
        sock.close()
        return json.loads(response.decode().strip())
    except Exception as e:
        return {"status": "error", "message": str(e)}

def wait_for_gcs(timeout: float = 30.0) -> bool:
    """Wait for GCS control server to be ready"""
    start = time.time()
    while time.time() - start < timeout:
        result = send_gcs_command("ping")
        if result.get("status") == "ok":
            return True
        time.sleep(0.5)
    return False

# ============================================================
# Drone Proxy Management
# ============================================================

class DroneProxyManager:
    """Manages drone proxy subprocess"""
    
    def __init__(self):
        self.process = None
        self.current_suite = None
    
    def start(self, suite_name: str) -> bool:
        """Start drone proxy with given suite"""
        if self.process and self.process.poll() is None:
            self.stop()
        
        suite = get_suite(suite_name)
        if not suite:
            log(f"Unknown suite: {suite_name}")
            return False
        
        secret_dir = SECRETS_DIR / suite_name
        peer_pubkey = secret_dir / "gcs_signing.pub"
        
        if not peer_pubkey.exists():
            log(f"Missing key: {peer_pubkey}")
            return False
        
        cmd = [
            sys.executable, "-m", "core.run_proxy", "drone",
            "--suite", suite_name,
            "--peer-pubkey-file", str(peer_pubkey),
            "--quiet"
        ]

        timestamp = time.strftime("%Y%m%d-%H%M%S")
        log_path = LOGS_DIR / f"drone_{suite_name}_{timestamp}.log"
        log(f"Launching: {' '.join(cmd)} (log: {log_path})")
        log_handle = open(log_path, "w", encoding="utf-8")
        self.process = subprocess.Popen(
            cmd,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            bufsize=1,
            universal_newlines=True,
        )
        self._last_log = log_path
        self.current_suite = suite_name
        
        # Wait for proxy to initialize
        time.sleep(3.0)

        if self.process.poll() is not None:
            log(f"Proxy exited early with code {self.process.returncode}")
            # Print tail of log for diagnosis
            try:
                with open(self._last_log, "r", encoding="utf-8") as fh:
                    lines = fh.read().splitlines()[-30:]
                    log("--- proxy log tail ---")
                    for l in lines:
                        log(l)
                    log("--- end log tail ---")
            except Exception:
                pass
            return False
        
        return True
    
    def stop(self):
        """Stop drone proxy"""
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.process = None
            self.current_suite = None
            try:
                # close last log handle if exists by leaving file closed (we opened in start)
                pass
            except Exception:
                pass
    
    def is_running(self) -> bool:
        return self.process is not None and self.process.poll() is None

# ============================================================
# Suite Runner
# ============================================================

def run_suite(proxy: DroneProxyManager, mavproxy, 
              suite_name: str, duration: float, is_first: bool = False) -> dict:
    """Run a single suite test - drone controls the flow.
    
    NOTE: Even though drone is the controller, GCS proxy must start first
    because the TCP handshake requires GCS to listen and drone to connect.
    Drone controls WHEN to start, but GCS proxy goes up first.
    """
    
    result = {
        "suite": suite_name,
        "status": "unknown",
        "echo_rx": 0,
        "echo_tx": 0,
    }
    
    # Ensure mavproxy (application-layer relay) is available
    mav_running = False
    try:
        # Support either the manager object with is_running(), or a subprocess.Popen
        if hasattr(mavproxy, "is_running"):
            mav_running = bool(mavproxy.is_running())
        else:
            # treat mavproxy as subprocess-like
            mav_running = mavproxy is not None and getattr(mavproxy, "poll", lambda: None)() is None
    except Exception:
        mav_running = False
    
    if not is_first:
        # Rekey: tell GCS to prepare (stop its proxy)
        log("Preparing GCS for rekey...")
        resp = send_gcs_command("prepare_rekey")
        if resp.get("status") != "ok":
            log(f"GCS prepare_rekey failed: {resp}")
            result["status"] = "gcs_prepare_failed"
            return result
        
        # Stop our proxy too
        proxy.stop()
        time.sleep(0.5)
    
    # Tell GCS to start its proxy first (GCS listens, drone connects)
    log(f"Telling GCS to start proxy for {suite_name}...")
    resp = send_gcs_command("start_proxy", suite=suite_name)
    log(f"GCS start_proxy response: {resp}")
    if resp.get("status") != "ok":
        log(f"GCS start_proxy failed: {resp}")
        result["status"] = "gcs_start_failed"
        return result

    # Wait for GCS proxy to be ready by polling status
    log("Waiting for GCS proxy to report ready...")
    start_wait = time.time()
    ready = False
    while time.time() - start_wait < 20.0:
        time.sleep(0.5)
        try:
            st = send_gcs_command("status")
            if st.get("proxy_running"):
                ready = True
                break
        except Exception:
            pass

    if not ready:
        log("GCS proxy did not become ready in time")
        result["status"] = "gcs_not_ready"
        return result
    
    # Now start drone proxy (it will connect to GCS)
    log(f"Starting drone proxy for {suite_name}...")
    if not proxy.start(suite_name):
        result["status"] = "proxy_start_failed"
        # include last log path if available
        try:
            tail = getattr(proxy, "_last_log", None)
            if tail:
                result["log"] = str(tail)
        except Exception:
            pass
        return result
    
    # Wait for handshake
    time.sleep(1.0)
    
    # Tell GCS to start traffic
    log("Telling GCS to start traffic...")
    resp = send_gcs_command("start_traffic", duration=duration)
    if resp.get("status") != "ok":
        log(f"GCS start_traffic failed: {resp}")
        result["status"] = "gcs_traffic_failed"
        return result
    
    log("Traffic started, waiting for completion... (mavproxy relaying MAVLink)")
    
    # Wait for GCS to finish traffic generation
    # Poll GCS status
    traffic_done = False
    start_time = time.time()
    max_wait = duration + 30  # Extra buffer
    
    while time.time() - start_time < max_wait:
        time.sleep(2.0)
        
        # Log mavproxy status periodically
        try:
            log(f"mavproxy running: {mavproxy.is_running()}")
        except Exception:
            pass
        
        # Check GCS status
        status = send_gcs_command("status")
        if status.get("traffic_complete"):
            traffic_done = True
            break
        
        # Check if proxy died
        if not proxy.is_running():
            log("Proxy exited unexpectedly")
            result["status"] = "proxy_exited"
            return result
    
    if not traffic_done:
        log("Traffic did not complete in time")
        result["status"] = "timeout"
        return result
    
    # Indicate mavproxy and proxy status in result
    try:
        if hasattr(mavproxy, "is_running"):
            result["mavproxy_running"] = bool(mavproxy.is_running())
        else:
            result["mavproxy_running"] = mavproxy is not None and getattr(mavproxy, "poll", lambda: 1)() is None
    except Exception:
        result["mavproxy_running"] = False
    result["proxy_running"] = bool(proxy.is_running())
    result["status"] = "pass"
    
    return result


# ============================================================
# Scheduler Class
# ============================================================


class DroneScheduler:
    """Manages persistent MAVProxy and per-suite crypto tunnels."""

    def __init__(self, args, suites):
        self.args = args
        self.suites = suites
        self.policy = LinearLoopPolicy(self.suites)
        self.proxy = DroneProxyManager()
        self.mavproxy_proc = None
        self.current_proxy_proc = None
        # Simple GCS client wrapper exposing send_command
        class _GcsClient:
            def send_command(self, cmd, params=None):
                params = params or {}
                try:
                    return send_gcs_command(cmd, **params)
                except Exception as e:
                    return {"status": "error", "message": str(e)}

        self.gcs_client = _GcsClient()

    def wait_for_handshake_completion(self, timeout: float = 10.0) -> bool:
        """Poll for the handshake completion status file."""
        status_file = Path(__file__).resolve().parents[1] / "logs" / "drone_status.json"
        start_time = time.time()
        while time.time() - start_time < timeout:
            if status_file.exists():
                try:
                    with open(status_file, "r") as f:
                        data = json.load(f)
                        if data.get("status") == "handshake_complete":
                            return True
                except Exception:
                    pass
            time.sleep(0.1)
        return False

    def start_persistent_mavproxy(self) -> bool:
        """Start MAVProxy once for the scheduler and keep handle."""
        try:
            python_exe = sys.executable
            master = self.args.mav_master
            out_arg = f"udp:127.0.0.1:{DRONE_PLAIN_TX_PORT}"
            # [FIX] Removed listening port for RX from Proxy to prevent loops; rely on reply-to-sender from proxy
            # rx_master = f"udpin:127.0.0.1:{DRONE_PLAIN_RX_PORT}"
            # Add --daemon to prevent prompt_toolkit issues in background
            # cmd = [
            #     python_exe,
            #     "-m",
            #     "MAVProxy.mavproxy",
            #     f"--master={master}",
            #     f"--master={rx_master}",
            #     f"--out={out_arg}",
            #     "--nowait",
            #     "--daemon",
            # ]

            # Interactive mode requested
            cmd = [
                python_exe,
                "-m",
                "MAVProxy.mavproxy",
                f"--master={master}",
                f"--out={out_arg}",
                "--nowait",
            ]

            if sys.platform.startswith("win"):
                log(f"Starting persistent mavproxy (drone) in NEW CONSOLE: {' '.join(cmd)}")
                creationflags = subprocess.CREATE_NEW_CONSOLE
                self.mavproxy_proc = subprocess.Popen(cmd, creationflags=creationflags)
            else:
                # Linux/Posix: Use daemon mode and log to file to support headless/SSH
                if "--daemon" not in cmd:
                    cmd.append("--daemon")
                
                ts = time.strftime("%Y%m%d-%H%M%S")
                log_dir = LOGS_DIR
                log_dir.mkdir(parents=True, exist_ok=True)
                log_path = log_dir / f"mavproxy_drone_{ts}.log"
                try:
                    fh = open(log_path, "w", encoding="utf-8")
                except Exception:
                    fh = subprocess.DEVNULL  # type: ignore[arg-type]

                log(f"Starting persistent mavproxy (drone): {' '.join(cmd)} (log: {log_path})")
                self.mavproxy_proc = subprocess.Popen(cmd, stdout=fh, stderr=subprocess.STDOUT)
            time.sleep(1.0)
            return self.mavproxy_proc is not None and self.mavproxy_proc.poll() is None
        except Exception as e:
            log(f"start_persistent_mavproxy exception: {e}")
            return False

    def start_tunnel_for_suite(self, suite_name: str) -> bool:
        return self.proxy.start(suite_name)

    def stop_current_tunnel(self):
        self.proxy.stop()

    def cleanup(self):
        logging.info("--- DroneScheduler CLEANUP START ---")
        try:
            # stop crypto proxy
            if self.proxy and self.proxy.is_running():
                logging.info("Stopping crypto proxy")
                self.proxy.stop()
        except Exception:
            pass

        try:
            if self.mavproxy_proc and getattr(self.mavproxy_proc, "poll", lambda: 1)() is None:
                logging.info(f"Terminating MAVProxy PID: {self.mavproxy_proc.pid}")
                self.mavproxy_proc.terminate()
                try:
                    self.mavproxy_proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self.mavproxy_proc.kill()
        except Exception:
            pass

        logging.info("--- DroneScheduler CLEANUP COMPLETE ---")

    def run_scheduler(self):
        def _sigint(sig, frame):
            log("Interrupted; cleaning up and exiting")
            self.cleanup()
            sys.exit(0)

        signal.signal(signal.SIGINT, _sigint)

        # Start MAVProxy once
        ok = self.start_persistent_mavproxy()
        if not ok:
            log("Warning: persistent MAVProxy failed to start; continuing")

        count = 0
        try:
            while True:
                suite_name = self.policy.next_suite()
                duration = self.policy.get_duration()
                log(f"=== Activating Suite: {suite_name} (duration={duration}) ===")

                # Coordinate with GCS: request GCS to start its proxy BEFORE starting local proxy
                try:
                    log(f"Telling GCS to start proxy for {suite_name}...")
                    resp = self.gcs_client.send_command("start_proxy", {"suite": suite_name})
                    if resp.get("status") != "ok":
                        logging.error(f"GCS rejected start_proxy: {resp}")
                        # skip this suite and continue
                        time.sleep(1.0)
                        continue
                    else:
                        log(f"GCS acknowledged start_proxy for {suite_name}")
                except Exception as e:
                    logging.error(f"Failed to command GCS: {e}")
                    time.sleep(1.0)
                    continue

                # Now start local crypto tunnel (drone proxy)
                self.start_tunnel_for_suite(suite_name)
                
                # Wait for handshake to complete before counting duration
                if self.wait_for_handshake_completion(timeout=10.0):
                    log(f"Handshake complete for {suite_name}")
                else:
                    log(f"Warning: Handshake timed out for {suite_name}")

                time.sleep(duration)
                self.stop_current_tunnel()

                count += 1
                if self.args.max_suites and count >= int(self.args.max_suites):
                    break

                time.sleep(2.0)
        except Exception as e:
            logging.error(f"Scheduler crash: {e}")
        finally:
            self.cleanup()


# ============================================================
# Main
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Drone Scheduler (Controller)")
    parser.add_argument("--mav-master", default=str(CONFIG.get("MAV_MASTER", "/dev/ttyACM0")), help="Primary MAVLink master (e.g. /dev/ttyACM0 or tcp:host:port)")
    parser.add_argument("--suite", default=None, help="Single suite to run")
    parser.add_argument("--nist-level", choices=["L1", "L3", "L5"], help="Run suites for NIST level")
    parser.add_argument("--all", action="store_true", help="Run all suites")
    parser.add_argument("--duration", type=float, default=DEFAULT_DURATION, help="Seconds per suite")
    parser.add_argument("--rate", type=float, default=DEFAULT_RATE_MBPS, help="Traffic rate Mbps")
    parser.add_argument("--max-suites", type=int, default=None, help="Max suites to run")
    args = parser.parse_args()
    
    print("=" * 60)
    print("Simplified Drone Scheduler (CONTROLLER) - sscheduler")
    print("=" * 60)
    # Configuration dump for debugging
    cfg = {
        "DRONE_HOST": DRONE_HOST,
        "GCS_HOST": GCS_HOST,
        "GCS_CONTROL": f"{GCS_CONTROL_HOST}:{GCS_CONTROL_PORT}",
        "PROXY_INTERNAL_CONTROL_PORT": PROXY_INTERNAL_CONTROL_PORT,
        "DRONE_PLAINTEXT_RX": DRONE_PLAIN_RX_PORT,
        "DRONE_PLAINTEXT_TX": DRONE_PLAIN_TX_PORT,
    }
    log("Configuration Dump:")
    for k, v in cfg.items():
        log(f"  {k}: {v}")
    log(f"Duration: {args.duration}s per suite, Rate: {args.rate} Mbps")
    
    # Determine suites to run
    if args.suite:
        suites_to_run = [args.suite]
    elif args.nist_level:
        suites_to_run = [s["name"] for s in SUITES if s.get("nist_level") == args.nist_level]
    elif args.all:
        suites_to_run = [s["name"] for s in SUITES]
    else:
        # Default: run all available suites
        suites_to_run = [s["name"] for s in SUITES]

    if args.max_suites:
        suites_to_run = suites_to_run[:args.max_suites]

    # Apply local in-file overrides
    if LOCAL_RATE_MBPS is not None:
        args.rate = float(LOCAL_RATE_MBPS)
    if LOCAL_DURATION is not None:
        args.duration = float(LOCAL_DURATION)
    if LOCAL_SUITES:
        suites_to_run = [s for s in LOCAL_SUITES if s in [x["name"] for x in SUITES]]
    if LOCAL_MAX_SUITES:
        suites_to_run = suites_to_run[: int(LOCAL_MAX_SUITES)]

    log(f"Suites to run: {len(suites_to_run)}")

    # Initialize components
    scheduler = DroneScheduler(args, suites_to_run)
    # configure logging
    logging.basicConfig(level=logging.INFO)
    scheduler.run_scheduler()

    return 0

if __name__ == "__main__":
    sys.exit(main())
