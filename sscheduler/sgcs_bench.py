#!/usr/bin/env python3
"""
Benchmark GCS Scheduler (FOLLOWER) - sscheduler/sgcs_bench.py

Specialized for "Operation Rapid Fire" Benchmark.
- Prioritizes LATENCY and THROUGHPUT metrics.
- Ignores power/stress (since this is GCS).
- Works in tandem with sdrone_bench.py.

Usage:
    python -m sscheduler.sgcs_bench [options]
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
import atexit
from pathlib import Path
from datetime import datetime, timezone

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import CONFIG
from core.suites import get_suite, list_suites
from core.process import ManagedProcess
from tools.mavproxy_manager import MavProxyManager
from sscheduler.gcs_metrics import GcsMetricsCollector
from sscheduler.control_security import get_drone_psk, create_challenge, verify_response

# Import MetricsAggregator for comprehensive metrics collection
try:
    from core.metrics_aggregator import MetricsAggregator
    HAS_METRICS_AGGREGATOR = True
except ImportError:
    HAS_METRICS_AGGREGATOR = False
    MetricsAggregator = None

# Extract config values (single source of truth)
DRONE_HOST = str(CONFIG.get("DRONE_HOST"))
GCS_HOST = str(CONFIG.get("GCS_HOST"))
GCS_PLAIN_TX_PORT = int(CONFIG.get("GCS_PLAINTEXT_TX", 47001))
GCS_PLAIN_RX_PORT = int(CONFIG.get("GCS_PLAINTEXT_RX", 47002))
DRONE_PLAIN_RX_PORT = int(CONFIG.get("DRONE_PLAINTEXT_RX", 47004))
GCS_TELEMETRY_PORT = int(CONFIG.get("GCS_TELEMETRY_PORT", 52080))
GCS_TELEMETRY_SNIFF_PORT = 14552
TCP_CTRL_PORT = CONFIG.get("TCP_HANDSHAKE_PORT")

# ============================================================
# Configuration (derived from CONFIG)
# ============================================================

# Bind control server to 0.0.0.0 so Drone can connect in diverse networks
GCS_CONTROL_HOST = str(CONFIG.get("GCS_CONTROL_BIND_HOST", "0.0.0.0"))
# Use configured GCS control port (default 48080)
GCS_CONTROL_PORT = int(CONFIG.get("GCS_CONTROL_PORT", 48080))

# Derived internal proxy control port to avoid collision when ports change
PROXY_INTERNAL_CONTROL_PORT = GCS_CONTROL_PORT + 100

SECRETS_DIR = Path(__file__).parent.parent / "secrets" / "matrix"

# Default traffic settings (can be overridden by drone)
DEFAULT_RATE_MBPS = 110.0
DEFAULT_DURATION = 10.0
PAYLOAD_SIZE = 1200

# Get all suites (list_suites returns dict, convert to list of dicts)
_suites_dict = list_suites()
SUITES = [{"name": k, **v} for k, v in _suites_dict.items()]

# ============================================================
# Logging
# ============================================================

def log(msg: str):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"[{ts}] [sgcs-bench] {msg}", flush=True)

def wait_for_tcp_port(port: int, timeout: float = 5.0) -> bool:
    """Wait for a local TCP port to be listening."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return True
        except (ConnectionRefusedError, OSError, socket.timeout):
            time.sleep(0.2)
    return False

# ============================================================
# GCS Proxy Management
# ============================================================

# Status file for GCS proxy (for data plane metrics)
GCS_STATUS_FILE = Path(__file__).parent.parent / "logs" / "gcs_status.json"

class GcsProxyManager:
    """Manages GCS proxy subprocess"""
    
    def __init__(self):
        self.managed_proc = None
        self.current_suite = None
    
    def start(self, suite_name: str) -> bool:
        """Start GCS proxy with given suite"""
        if self.managed_proc and self.managed_proc.is_running():
            self.stop()
        
        suite = get_suite(suite_name)
        if not suite:
            log(f"Unknown suite: {suite_name}")
            return False
        
        secret_dir = SECRETS_DIR / suite_name
        gcs_key = secret_dir / "gcs_signing.key"
        
        if not gcs_key.exists():
            log(f"Missing key: {gcs_key}")
            return False
        
        # Clear old status file before starting proxy
        try:
            if GCS_STATUS_FILE.exists():
                GCS_STATUS_FILE.unlink()
        except Exception:
            pass
        
        cmd = [
            sys.executable, "-m", "core.run_proxy", "gcs",
            "--suite", suite_name,
            "--gcs-secret-file", str(gcs_key),
            "--status-file", str(GCS_STATUS_FILE),
            "--quiet"
        ]
        
        log(f"Launching: {' '.join(cmd)}")
        self.managed_proc = ManagedProcess(
            cmd=cmd,
            name=f"proxy-{suite_name}",
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        
        if self.managed_proc.start():
            self.current_suite = suite_name
            time.sleep(2.0)
            if not self.managed_proc.is_running():
                log(f"Proxy exited early")
                return False
            return True
        return False
    
    def stop(self):
        """Stop GCS proxy"""
        if self.managed_proc:
            self.managed_proc.stop()
            self.managed_proc = None
            self.current_suite = None
    
    def is_running(self) -> bool:
        return self.managed_proc is not None and self.managed_proc.is_running()


# ============================================================
# Telemetry Sender
# ============================================================

class TelemetrySender:
    """Sends telemetry updates to the Drone via UDP (Fire-and-Forget)"""
    def __init__(self, target_host: str, target_port: int):
        self.target_addr = (target_host, target_port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.seq = 0
        self.lock = threading.Lock()

    def send(self, packet: dict):
        """Send a telemetry packet (Schema v1)"""
        with self.lock:
            self.seq += 1
            packet["seq"] = self.seq
        
        try:
            payload = json.dumps(packet).encode('utf-8')
            self.sock.sendto(payload, self.target_addr)
        except Exception:
            # Fire and forget
            pass

    def close(self):
        self.sock.close()

# ============================================================
# Control Server (GCS listens for drone commands)
# ============================================================

class ControlServer:
    """TCP control server - GCS listens for commands from drone"""
    
    def __init__(self, proxy: GcsProxyManager):
        self.proxy = proxy
        self.mavproxy = MavProxyManager("gcs")
        self.mavproxy_proc = None
        self.server_sock = None
        self.running = False
        self.thread = None
        
        # Telemetry
        self.telemetry = TelemetrySender(DRONE_HOST, GCS_TELEMETRY_PORT)
        self.telemetry_thread = None
        
        # Metrics Collector
        self.metrics_collector = GcsMetricsCollector(
            mavlink_host="127.0.0.1",
            mavlink_port=GCS_TELEMETRY_SNIFF_PORT,
            proxy_manager=self.proxy,
            log_dir=Path(__file__).parent.parent / "logs" / "gcs_telemetry"
        )
        
        # Comprehensive Metrics Aggregator (GCS side)
        self.metrics_aggregator = None
        if HAS_METRICS_AGGREGATOR:
            try:
                self.metrics_aggregator = MetricsAggregator(
                    role="gcs",
                    output_dir=str(Path(__file__).parent.parent / "logs" / "benchmarks" / "comprehensive")
                )
                log("MetricsAggregator initialized for comprehensive metrics")
            except Exception as e:
                log(f"MetricsAggregator init failed: {e}")
        
        # Track current suite for metrics
        self.current_suite = None

    def start_persistent_mavproxy(self):
        """Start a persistent mavproxy subprocess for the lifetime of the scheduler."""
        try:
            bind_host = str(CONFIG.get("GCS_PLAINTEXT_BIND", "0.0.0.0"))
            listen_port = int(CONFIG.get("GCS_PLAINTEXT_RX", GCS_PLAIN_RX_PORT))
            tunnel_out_port = int(CONFIG.get("GCS_PLAINTEXT_TX", GCS_PLAIN_TX_PORT))
            QGC_PORT = int(CONFIG.get("QGC_PORT", 14550))

            master_str = f"udpin:{bind_host}:{listen_port}"
            python_exe = sys.executable
            
            cmd = [
                python_exe, "-m", "MAVProxy.mavproxy", 
                f"--master={master_str}", 
                "--dialect=ardupilotmega", 
                "--nowait", 
                "--map", 
                "--console", 
                f"--out=udp:127.0.0.1:{QGC_PORT}",
                f"--out=udp:127.0.0.1:{GCS_TELEMETRY_SNIFF_PORT}"
            ]

            log(f"Starting persistent mavproxy: {' '.join(cmd)}")

            log_dir = Path(__file__).resolve().parents[1] / "logs" / "sscheduler" / "gcs"
            log_dir.mkdir(parents=True, exist_ok=True)
            ts_now = time.strftime("%Y%m%d-%H%M%S")
            log_path = log_dir / f"mavproxy_gcs_{ts_now}.log"
            try:
                fh = open(log_path, "w", encoding="utf-8")
            except Exception:
                fh = subprocess.DEVNULL

            stdout_arg = fh
            stderr_arg = subprocess.STDOUT
            
            if sys.platform == "win32":
                stdout_arg = None
                stderr_arg = None
            
            env = os.environ.copy()
            env["TERM"] = "dumb"

            stdin_arg = subprocess.DEVNULL
            if sys.platform == "win32":
                stdin_arg = None 

            self.mavproxy_proc = ManagedProcess(
                cmd=cmd,
                name="mavproxy-gcs",
                stdout=stdout_arg,
                stderr=stderr_arg,
                stdin=stdin_arg,
                new_console=True, 
                env=env
            )
            
            if self.mavproxy_proc.start():
                self.metrics_collector.mavproxy_proc = self.mavproxy_proc
                if wait_for_tcp_port(TCP_CTRL_PORT, timeout=5.0):
                    log("Persistent mavproxy started (port open)")
                    return True
                elif self.mavproxy_proc.is_running():
                    log("Persistent mavproxy started (process running)")
                    return True
                else:
                    log("Persistent mavproxy failed to start")
                    return False
            return False
        except Exception as e:
            log(f"start_persistent_mavproxy exception: {e}")
            return False

    def start(self):
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_sock.bind((GCS_CONTROL_HOST, GCS_CONTROL_PORT))
        self.server_sock.listen(5)
        self.server_sock.settimeout(1.0)
        
        self.running = True
        self.thread = threading.Thread(target=self._server_loop, daemon=True)
        self.thread.start()
        
        # Start metrics collector
        self.metrics_collector.start()
        
        # Start telemetry loop
        self.telemetry_thread = threading.Thread(target=self._telemetry_loop, daemon=True)
        self.telemetry_thread.start()
        
        log(f"Control server listening on {GCS_CONTROL_HOST}:{GCS_CONTROL_PORT}")
    
    def _server_loop(self):
        while self.running:
            try:
                client, addr = self.server_sock.accept()
                threading.Thread(target=self._handle_client, args=(client, addr), daemon=True).start()
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    log(f"Server error: {e}")

    def _telemetry_loop(self):
        """Periodically send status to drone"""
        while self.running:
            try:
                # Get latest metrics snapshot
                snapshot = self.metrics_collector.get_snapshot()
                self.telemetry.send(snapshot)
            except Exception:
                pass
            
            time.sleep(0.2)

    def _handle_client(self, client, addr):
        try:
            # 1. Authentication Handshake
            psk = get_drone_psk()
            challenge = create_challenge()
            client.sendall(challenge.hex().encode() + b"\n")
            
            response_data = b""
            start_time = time.time()
            while time.time() - start_time < 5.0:
                chunk = client.recv(4096)
                if not chunk: break
                response_data += chunk
                if b"\n" in response_data: break

            client_response = response_data.decode().strip()

            if not verify_response(challenge, client_response, psk):
                log(f"Authentication failed for {addr}")
                client.close()
                return

            # 2. Command Processing
            data = b""
            while True:
                chunk = client.recv(4096)
                if not chunk: break
                data += chunk
                if len(data) > 0 and (data.strip().endswith(b"}") or b"\n" in data): break
            
            if data:
                try:
                    request = json.loads(data.decode().strip())
                    response = self._handle_command(request)
                    client.sendall(json.dumps(response).encode() + b"\n")
                except json.JSONDecodeError:
                    pass
        except Exception as e:
            log(f"Client error: {e}")
        finally:
            client.close()
    
    def _handle_command(self, request: dict) -> dict:
        cmd = request.get("cmd", "")
        
        if cmd == "ping":
            return {"status": "ok", "message": "pong", "role": "gcs_bench"}
        
        elif cmd == "start_proxy":
            suite = request.get("suite")
            run_id = request.get("run_id")
            
            if not suite:
                return {"status": "error", "message": "missing suite"}
            
            log(f"Start proxy requested for suite: {suite}")

            if run_id and self.metrics_aggregator:
                try:
                    self.metrics_aggregator.set_run_id(str(run_id))
                except Exception:
                    pass
            
            if self.metrics_aggregator and self.current_suite:
                try:
                    self.metrics_aggregator.finalize_suite()
                except Exception:
                    pass
            
            suite_config = get_suite(suite) or {}
            if self.metrics_aggregator:
                try:
                    self.metrics_aggregator.start_suite(suite, suite_config)
                    self.metrics_aggregator.record_handshake_start()
                except Exception as e:
                    log(f"Metrics start failed: {e}")
            
            if not self.proxy.start(suite):
                if self.metrics_aggregator:
                    try:
                        self.metrics_aggregator.record_handshake_end(success=False, failure_reason="proxy_start_failed")
                        self.metrics_aggregator.finalize_suite()
                    except Exception:
                        pass
                return {"status": "error", "message": "proxy_start_failed"}

            self.current_suite = suite
            
            if self.metrics_aggregator:
                try:
                    self.metrics_aggregator.record_handshake_end(success=True)
                except Exception:
                    pass
            
            log("Proxy started")
            return {"status": "ok", "message": "proxy_started"}
        
        elif cmd == "prepare_rekey":
            log("Prepare rekey: stopping proxy...")
            if self.metrics_aggregator and self.current_suite:
                try:
                    counters = {}
                    if GCS_STATUS_FILE.exists():
                        for _ in range(3):
                            try:
                                with open(GCS_STATUS_FILE, "r") as f:
                                    status_data = json.load(f)
                                candidate = status_data.get("counters", {})
                                counters = candidate or counters
                                if candidate: break
                            except Exception: pass
                            time.sleep(1.0)
                        if counters:
                            self.metrics_aggregator.record_data_plane_metrics(counters)
                            log("  Data plane: enc_in=%s, ptx_out=%s" % (counters.get("enc_in", 0), counters.get("ptx_out", 0)))
                    
                    comprehensive = self.metrics_aggregator.finalize_suite()
                    if comprehensive:
                        output_path = self.metrics_aggregator.save_suite_metrics(comprehensive)
                        if output_path:
                            log(f"Comprehensive metrics saved: {output_path}")
                except Exception as e:
                    log(f"Metrics finalize failed: {e}")
            
            self.proxy.stop()
            self.current_suite = None
            return {"status": "ok", "message": "ready_for_rekey"}
        
        elif cmd == "stop":
            log("Stop command received")
            self.proxy.stop()
            if self.mavproxy_proc:
                try:
                    self.mavproxy_proc.terminate()
                except Exception:
                    pass
                self.mavproxy_proc = None
            return {"status": "ok", "message": "stopped"}
        
        return {"status": "error", "message": f"unknown command: {cmd}"}
    
    def stop(self):
        self.running = False
        if self.thread: self.thread.join(timeout=2.0)
        if self.telemetry_thread: self.telemetry_thread.join(timeout=2.0)
        if self.metrics_collector: self.metrics_collector.stop()
        if self.telemetry: self.telemetry.close()
        if self.server_sock: self.server_sock.close()
        if self.mavproxy_proc:
            try:
                self.mavproxy_proc.stop()
            except Exception:
                pass
            self.mavproxy_proc = None

# ============================================================
# Main
# ============================================================

def cleanup_environment():
    """Force kill any stale instances."""
    log("Cleaning up stale processes...")
    my_pid = os.getpid()
    targets = ["mavproxy", "core.run_proxy"]
    if sys.platform.startswith("win"):
        for t in targets:
            query = f"name='python.exe' and commandline like '%{t}%' and ProcessId!={my_pid}"
            cmd = f'wmic process where "{query}" call terminate'
            try:
                subprocess.run(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass
    else:
        for t in targets:
             subprocess.run(["pkill", "-f", t], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.0)

atexit.register(cleanup_environment)

def main():
    print("=" * 60)
    print("Benchmark GCS Scheduler (FOLLOWER) - sscheduler")
    print("Mode: LATENCY & THROUGHPUT Optimized")
    print("=" * 60)
    
    cfg = {
        "DRONE_HOST": DRONE_HOST,
        "GCS_HOST": GCS_HOST,
        "GCS_CONTROL_BIND": f"{GCS_CONTROL_HOST}:{GCS_CONTROL_PORT}",
        "PROXY_INTERNAL_CONTROL_PORT": PROXY_INTERNAL_CONTROL_PORT,
    }
    log("Configuration Dump:")
    for k, v in cfg.items():
        log(f"  {k}: {v}")
    
    log("GCS benchmark scheduler running. Waiting for commands from drone...")
    cleanup_environment()

    proxy = GcsProxyManager()
    control = ControlServer(proxy)
    control.start()

    try:
        ok = control.start_persistent_mavproxy()
        log(f"Persistent mavproxy started: {ok}")
    except Exception as _e:
        log(f"persistent mavproxy startup exception: {_e}")

    shutdown = threading.Event()
    
    def signal_handler(sig, frame):
        log("Shutdown signal received")
        shutdown.set()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        while not shutdown.is_set():
            shutdown.wait(timeout=1.0)
    finally:
        log("Shutting down...")
        control.stop()
        proxy.stop()
    
    log("GCS scheduler stopped")
    return 0

if __name__ == "__main__":
    sys.exit(main())
