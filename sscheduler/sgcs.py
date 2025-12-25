#!/usr/bin/env python3
"""
Simplified GCS Scheduler (FOLLOWER) - sscheduler/sgcs.py

REVERSED CONTROL: GCS follows drone commands.
- GCS has control server, waits for drone commands
- GCS starts its proxy when drone says "start"
- GCS runs traffic generator when commanded
- Drone controls suite order, timing, rekey

Usage:
    python -m sscheduler.sgcs [options]

Environment:
    DRONE_HOST          Drone IP (default: from config)
    GCS_HOST            GCS IP (default: from config)
    GCS_CONTROL_HOST    GCS control server bind IP (default: GCS_HOST)
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
from sscheduler.telemetry import TelemetryCollector

# Extract config values (single source of truth)
DRONE_HOST = str(CONFIG.get("DRONE_HOST"))
GCS_HOST = str(CONFIG.get("GCS_HOST"))
GCS_PLAIN_TX_PORT = int(CONFIG.get("GCS_PLAINTEXT_TX", 47001))
GCS_PLAIN_RX_PORT = int(CONFIG.get("GCS_PLAINTEXT_RX", 47002))
DRONE_PLAIN_RX_PORT = int(CONFIG.get("DRONE_PLAINTEXT_RX", 47004))
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

ROOT = Path(__file__).resolve().parents[1]
GCS_PROXY_STATUS_FILE = ROOT / "logs" / "gcs_status.json"

# Default traffic settings (can be overridden by drone)
DEFAULT_RATE_MBPS = 110.0
DEFAULT_DURATION = 10.0
PAYLOAD_SIZE = 1200

# --------------------
# Local editable configuration (edit here, no CLI args needed)
# --------------------
LOCAL_RATE_MBPS = None  # e.g. 110.0
LOCAL_DURATION = None  # e.g. 10.0
LOCAL_MAX_SUITES = None
LOCAL_SUITES = None

# Get all suites (list_suites returns dict, convert to list of dicts)
_suites_dict = list_suites()
SUITES = [{"name": k, **v} for k, v in _suites_dict.items()]

# ============================================================
# Logging
# ============================================================

def log(msg: str):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"[{ts}] [sgcs-follow] {msg}", flush=True)

# ============================================================
# Traffic Generator
# ============================================================

class TrafficGenerator:
    """Generates UDP traffic from GCS to drone"""
    
    def __init__(self, rate_mbps: float = DEFAULT_RATE_MBPS):
        self.rate_mbps = rate_mbps
        self.tx_sock = None
        self.rx_sock = None
        self.running = False
        self.tx_count = 0
        self.rx_count = 0
        self.tx_bytes = 0
        self.rx_bytes = 0
        self.lock = threading.Lock()
        self.complete = False
    
    def start(self, duration: float):
        """Start traffic generation in background thread"""
        self.tx_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.tx_sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4 * 1024 * 1024)

        self.rx_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.rx_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.rx_sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 * 1024 * 1024)
        # Bind receive socket on the GCS plaintext RX port so echoes return here
        self.rx_sock.bind((GCS_HOST, GCS_PLAIN_RX_PORT))
        self.rx_sock.settimeout(1.0)
        
        self.running = True
        self.complete = False
        self.tx_count = 0
        self.rx_count = 0
        self.tx_bytes = 0
        self.rx_bytes = 0
        
        # Start receiver thread
        self.rx_thread = threading.Thread(target=self._receive_loop, daemon=True)
        self.rx_thread.start()
        
        # Start sender thread
        self.tx_thread = threading.Thread(target=self._send_loop, args=(duration,), daemon=True)
        self.tx_thread.start()
        
        log(f"Traffic started: {self.rate_mbps} Mbps for {duration}s")
    
    def _send_loop(self, duration: float):
        """Send packets at target rate"""
        payload = b"X" * PAYLOAD_SIZE
        packets_per_sec = (self.rate_mbps * 1_000_000) / (8 * PAYLOAD_SIZE)
        interval = 1.0 / packets_per_sec
        batch_size = max(1, int(packets_per_sec / 100))  # Send in batches
        batch_interval = interval * batch_size
        
        start_time = time.time()
        end_time = start_time + duration
        
        while time.time() < end_time and self.running:
            batch_start = time.time()
            
            for _ in range(batch_size):
                try:
                    # Send traffic to the Drone's plaintext receive port
                    self.tx_sock.sendto(payload, (DRONE_HOST, DRONE_PLAIN_RX_PORT))
                    with self.lock:
                        self.tx_count += 1
                        self.tx_bytes += len(payload)
                except Exception:
                    pass
            
            # Rate limiting
            elapsed = time.time() - batch_start
            if elapsed < batch_interval:
                time.sleep(batch_interval - elapsed)
        
        self.complete = True
        log(f"Traffic complete: TX={self.tx_count}, RX={self.rx_count}")
    
    def _receive_loop(self):
        """Receive echo responses"""
        while self.running:
            try:
                data, addr = self.rx_sock.recvfrom(65535)
                with self.lock:
                    self.rx_count += 1
                    self.rx_bytes += len(data)
            except socket.timeout:
                continue
            except Exception:
                if self.running:
                    pass
    
    def get_stats(self):
        with self.lock:
            return {
                "tx_count": self.tx_count,
                "rx_count": self.rx_count,
                "tx_bytes": self.tx_bytes,
                "rx_bytes": self.rx_bytes,
                "complete": self.complete,
            }
    
    def stop(self):
        self.running = False
        if hasattr(self, 'tx_thread'):
            self.tx_thread.join(timeout=2.0)
        if hasattr(self, 'rx_thread'):
            self.rx_thread.join(timeout=2.0)
        if self.tx_sock:
            self.tx_sock.close()
        if self.rx_sock:
            self.rx_sock.close()
    
    def is_complete(self):
        return self.complete

# ============================================================
# GCS Proxy Management
# ============================================================

class GcsProxyManager:
    """Manages GCS proxy subprocess"""
    
    def __init__(self):
        self.process = None
        self.current_suite = None
    
    def start(self, suite_name: str) -> bool:
        """Start GCS proxy with given suite"""
        if self.process and self.process.poll() is None:
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
        
        cmd = [
            sys.executable, "-m", "core.run_proxy", "gcs",
            "--suite", suite_name,
            "--gcs-secret-file", str(gcs_key),
            "--status-file", str(GCS_PROXY_STATUS_FILE),
            "--quiet"
        ]
        
        log(f"Launching: {' '.join(cmd)}")
        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self.current_suite = suite_name
        
        # Wait for proxy to initialize
        time.sleep(2.0)
        
        if self.process.poll() is not None:
            log(f"Proxy exited early with code {self.process.returncode}")
            return False
        
        return True
    
    def stop(self):
        """Stop GCS proxy"""
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.process = None
            self.current_suite = None
    
    def is_running(self) -> bool:
        return self.process is not None and self.process.poll() is None


# MavProxyManager imported from tools.mavproxy_manager


# ============================================================
# Control Server (GCS listens for drone commands)
# ============================================================

class ControlServer:
    """TCP control server - GCS listens for commands from drone"""
    
    def __init__(self, proxy: GcsProxyManager):
        self.proxy = proxy
        self.traffic = None
        self.mavproxy = MavProxyManager("gcs")
        # Persistent mavproxy subprocess handle (if started here)
        self.mavproxy_proc = None
        self.server_sock = None
        self.running = False
        self.thread = None
        self.rate_mbps = DEFAULT_RATE_MBPS
        self.duration = DEFAULT_DURATION
        self.current_run_id = None
        self.last_drone_metrics = None
        # telemetry collector for link-quality
        try:
            self.telemetry = TelemetryCollector(role="gcs")
        except Exception:
            self.telemetry = None

    def start_persistent_mavproxy(self):
        """Start a persistent mavproxy subprocess for the lifetime of the scheduler.

        Uses `sys.executable -m MAVProxy.mavproxy` where possible so Windows/sudo
        environments resolve correctly.
        """
        try:
            bind_host = str(CONFIG.get("GCS_PLAINTEXT_BIND", "0.0.0.0"))
            listen_port = int(CONFIG.get("GCS_PLAINTEXT_RX", GCS_PLAIN_RX_PORT))
            tunnel_out_port = int(CONFIG.get("GCS_PLAINTEXT_TX", GCS_PLAIN_TX_PORT))
            QGC_PORT = int(CONFIG.get("QGC_PORT", 14550))

            master_str = f"udpin:{bind_host}:{listen_port}"
            out_arg = f"udp:127.0.0.1:{tunnel_out_port}"

            # Prefer module invocation to avoid PATH issues on Windows
            python_exe = sys.executable
            cmd = [python_exe, "-m", "MAVProxy.mavproxy", f"--master={master_str}", f"--out={out_arg}", "--dialect=ardupilotmega", "--nowait", f"--out=udp:127.0.0.1:{QGC_PORT}"]

            log(f"Starting persistent mavproxy: {' '.join(cmd)}")

            if sys.platform.startswith("win"):
                # Open new console on Windows for interactive UI
                creationflags = subprocess.CREATE_NEW_CONSOLE
                self.mavproxy_proc = subprocess.Popen(cmd, stdout=None, stderr=None, creationflags=creationflags)
            else:
                # On POSIX keep logs
                log_dir = Path(__file__).resolve().parents[1] / "logs" / "sscheduler" / "gcs"
                log_dir.mkdir(parents=True, exist_ok=True)
                ts_now = time.strftime("%Y%m%d-%H%M%S")
                log_path = log_dir / f"mavproxy_gcs_{ts_now}.log"
                try:
                    fh = open(log_path, "w", encoding="utf-8")
                except Exception:
                    fh = subprocess.DEVNULL  # type: ignore[arg-type]
                self.mavproxy_proc = subprocess.Popen(cmd, stdout=fh, stderr=subprocess.STDOUT, text=True)

            # give it a moment
            time.sleep(0.5)
            if self.mavproxy_proc and self.mavproxy_proc.poll() is None:
                log("Persistent mavproxy started")
                return True
            else:
                log("Persistent mavproxy failed to start")
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
    
    def _handle_client(self, client: socket.socket, addr):
        try:
            client.settimeout(30.0)
            data = b""
            while b"\n" not in data:
                chunk = client.recv(4096)
                if not chunk:
                    break
                data += chunk
            
            if data:
                request = json.loads(data.decode().strip())
                response = self._handle_command(request)
                client.sendall(json.dumps(response).encode() + b"\n")
        except Exception as e:
            log(f"Client error: {e}")
        finally:
            client.close()
    
    def _handle_command(self, request: dict) -> dict:
        cmd = request.get("cmd", "")
        
        if cmd == "ping":
            return {"status": "ok", "message": "pong", "role": "gcs_follower"}
        
        elif cmd == "status":
            traffic_stats = self.traffic.get_stats() if self.traffic else {}
            gcs_metrics = {}
            try:
                if getattr(self, "telemetry", None):
                    snap = self.telemetry.snapshot()
                    pkt = int(snap.get("packet_count", 0) or 0)
                    lost = int(snap.get("packet_loss", 0) or 0)
                    denom = max(1, pkt + lost)
                    loss_pct = (lost / denom) * 100.0
                    # We approximate latency using the inter-arrival jitter EMA when
                    # true RTT measurement is not available.
                    avg_latency_ms = float(snap.get("jitter_ms", 0.0) or 0.0)
                    gcs_metrics = {
                        "avg_latency_ms": avg_latency_ms,
                        "packet_loss_pct": loss_pct,
                        "cpu_util": float(snap.get("cpu_util", 0.0) or 0.0),
                        "temp_c": float(snap.get("temp_c", 0.0) or 0.0),
                    }
            except Exception:
                gcs_metrics = {}
            return {
                "status": "ok",
                "proxy_running": self.proxy.is_running(),
                "current_suite": self.proxy.current_suite,
                "traffic_complete": traffic_stats.get("complete", False),
                "traffic_stats": traffic_stats,
                "gcs_metrics": gcs_metrics,
                "drone_metrics": self.last_drone_metrics or {},
            }

        elif cmd == "telemetry_report":
            # Drone -> GCS metrics report over the scheduler control TCP channel.
            metrics = request.get("metrics")
            if not isinstance(metrics, dict):
                return {"status": "error", "message": "metrics must be an object"}
            self.last_drone_metrics = {
                "t": time.time(),
                "suite": request.get("suite"),
                "run_id": request.get("run_id"),
                "metrics": metrics,
            }
            return {"status": "ok", "message": "telemetry_received"}
        
        elif cmd == "configure":
            # Drone tells GCS the traffic parameters
            self.rate_mbps = request.get("rate_mbps", DEFAULT_RATE_MBPS)
            self.duration = request.get("duration", DEFAULT_DURATION)
            log(f"Configured: rate={self.rate_mbps} Mbps, duration={self.duration}s")
            return {"status": "ok", "message": "configured"}
        
        elif cmd == "start":
            # Drone tells GCS to start proxy and begin traffic (combined)
            suite = request.get("suite")
            duration = request.get("duration", self.duration)
            
            if not suite:
                return {"status": "error", "message": "missing suite"}
            
            log(f"Start requested for suite: {suite}")
            
            # Start GCS proxy
            if not self.proxy.start(suite):
                return {"status": "error", "message": "proxy_start_failed"}
            
            # Wait a moment for handshake
            time.sleep(1.0)
            
            # Do NOT spawn a new mavproxy here. MAVProxy should be persistent.
            log("Traffic start requested (MAVProxy is already running)")
            # Check persistent mavproxy health
            if not (self.mavproxy_proc and self.mavproxy_proc.poll() is None):
                return {"status": "error", "message": "mavproxy_not_running"}
            return {"status": "ok", "message": "started"}
        
        elif cmd == "start_proxy":
            # Drone tells GCS to start proxy only (no traffic yet)
            suite = request.get("suite")
            run_id = request.get("run_id", None)

            if not suite:
                return {"status": "error", "message": "missing suite"}

            log(f"Start proxy requested for suite: {suite} (run_id={run_id})")

            # Lazy telemetry configuration for this run
            try:
                if run_id and self.current_run_id != run_id:
                    self.current_run_id = run_id
                    try:
                        if getattr(self, 'telemetry', None):
                            self.telemetry.close()
                    except Exception:
                        pass
                    self.telemetry = TelemetryCollector(role="gcs")
                    # configure logging and start sniffer on QGC port
                    qgc_port = int(CONFIG.get("QGC_PORT", 14550))
                    try:
                        self.telemetry.configure_logging("logs", run_id)
                        self.telemetry.start(qgc_port)
                    except Exception as _e:
                        log(f"Telemetry configure/start failed: {_e}")
            except Exception:
                pass

            # Start GCS proxy
            if not self.proxy.start(suite):
                return {"status": "error", "message": "proxy_start_failed"}

            # Persistent MAVProxy should already be running; just acknowledge
            log("Proxy started; persistent MAVProxy assumed running")

            # Immediately write a telemetry snapshot for this suite if configured
            try:
                if getattr(self, 'telemetry', None):
                    self.telemetry.log_snapshot(suite)
            except Exception:
                pass

            return {"status": "ok", "message": "proxy_started"}
        
        elif cmd == "start_traffic":
            # Drone tells GCS to start traffic (proxy already running)
            duration = request.get("duration", self.duration)
            
            if not self.proxy.is_running():
                return {"status": "error", "message": "proxy_not_running"}
            
            log(f"Starting traffic: {self.rate_mbps} Mbps for {duration}s")
            
            # With persistent MAVProxy there is nothing to spawn here.
            log("Traffic start requested (MAVProxy is already running)")
            if not (self.mavproxy_proc and self.mavproxy_proc.poll() is None):
                return {"status": "error", "message": "mavproxy_not_running"}
            return {"status": "ok", "message": "traffic_started"}
            
            return {"status": "ok", "message": "traffic_started"}
        
        elif cmd == "prepare_rekey":
            # Drone tells GCS to prepare for rekey (stop proxy)
            log("Prepare rekey: stopping proxy...")
            # mark rekey event for telemetry
            try:
                if self.telemetry:
                    self.telemetry.mark_rekey_event()
            except Exception:
                pass
            self.proxy.stop()
            # stop mavproxy if running
            if self.mavproxy_proc:
                try:
                    self.mavproxy_proc.terminate()
                except Exception:
                    pass
                self.mavproxy_proc = None

            if self.traffic:
                try:
                    self.traffic.stop()
                except Exception:
                    pass
                self.traffic = None
            
            return {"status": "ok", "message": "ready_for_rekey"}
        
        elif cmd == "stop":
            log("Stop command received")
            # mark rekey/stop event
            try:
                if self.telemetry:
                    self.telemetry.mark_rekey_event()
            except Exception:
                pass
            self.proxy.stop()
            # Stop mavproxy and any traffic generator wrapper
            if self.mavproxy_proc:
                try:
                    self.mavproxy_proc.terminate()
                except Exception:
                    pass
                self.mavproxy_proc = None

            if self.traffic:
                try:
                    self.traffic.stop()
                except Exception:
                    pass
                self.traffic = None
            
            return {"status": "ok", "message": "stopped"}
        
        elif cmd == "get_suites":
            return {
                "status": "ok",
                "suites": [s["name"] for s in SUITES],
                "count": len(SUITES),
            }
        
        else:
            return {"status": "error", "message": f"unknown command: {cmd}"}
    
    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)
        if self.server_sock:
            self.server_sock.close()
        if self.traffic:
            try:
                self.traffic.stop()
            except Exception:
                pass
        if self.mavproxy_proc:
            try:
                self.mavproxy_proc.terminate()
            except Exception:
                pass
            self.mavproxy_proc = None

# ============================================================
# Main
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="GCS Scheduler (Follower)")
    args = parser.parse_args()
    
    print("=" * 60)
    print("Simplified GCS Scheduler (FOLLOWER) - sscheduler")
    print("=" * 60)
    # Configuration dump for debugging
    cfg = {
        "DRONE_HOST": DRONE_HOST,
        "GCS_HOST": GCS_HOST,
        "GCS_CONTROL_BIND": f"{GCS_CONTROL_HOST}:{GCS_CONTROL_PORT}",
        "PROXY_INTERNAL_CONTROL_PORT": PROXY_INTERNAL_CONTROL_PORT,
        "GCS_PLAINTEXT_RX": GCS_PLAIN_RX_PORT,
        "GCS_PLAINTEXT_TX": GCS_PLAIN_TX_PORT,
        "DRONE_PLAINTEXT_RX": DRONE_PLAIN_RX_PORT,
    }
    log("Configuration Dump:")
    for k, v in cfg.items():
        log(f"  {k}: {v}")
    log("GCS scheduler running. Waiting for commands from drone...")
    log("(Drone will send 'start', 'rekey', 'stop' commands)")
    
    # Initialize components
    proxy = GcsProxyManager()
    control = ControlServer(proxy)
    control.start()

    # Start persistent MAVProxy for the scheduler lifetime
    try:
        ok = control.start_persistent_mavproxy()
        if ok:
            log("persistent mavproxy started at scheduler startup")
        else:
            log("persistent mavproxy failed to start at scheduler startup")
    except Exception as _e:
        log(f"persistent mavproxy startup exception: {_e}")

    # Start telemetry sniffer on QGC port if available
    try:
        qgc_port = int(CONFIG.get("QGC_PORT", 14550))
        if getattr(control, "telemetry", None):
            control.telemetry.start(qgc_port)
    except Exception as _e:
        log(f"telemetry.start on GCS failed: {_e}")

    # Apply local in-file overrides for rate/duration if set
    if LOCAL_RATE_MBPS is not None:
        control.rate_mbps = float(LOCAL_RATE_MBPS)
    if LOCAL_DURATION is not None:
        control.duration = float(LOCAL_DURATION)
    
    # Wait for shutdown
    shutdown = threading.Event()
    
    def signal_handler(sig, frame):
        log("Shutdown signal received")
        shutdown.set()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        count = 0
        while not shutdown.is_set():
            shutdown.wait(timeout=1.0)
            count += 1
            # every 10s, log link-quality metrics
            if count % 10 == 0:
                try:
                    if getattr(control, "telemetry", None):
                        stats = control.telemetry.snapshot()
                        logging.info(f"[LINK QUALITY] Loss: {stats['packet_loss']} pkts | Jitter: {stats['jitter_ms']:.2f}ms | Blackout Recovery: {stats['blackout_recovery']:.2f}s")
                        # also persist snapshot to jsonl
                        try:
                            current_suite = control.proxy.current_suite
                            if current_suite:
                                control.telemetry.log_snapshot(current_suite)
                        except Exception:
                            pass
                except Exception as _e:
                    log(f"telemetry snapshot failed: {_e}")
    finally:
        log("Shutting down...")
        control.stop()
        proxy.stop()
    
    log("GCS scheduler stopped")
    return 0

if __name__ == "__main__":
    sys.exit(main())
