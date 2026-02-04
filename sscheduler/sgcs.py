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
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import CONFIG
from core.suites import get_suite, list_suites

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
# Mode Resolution (identical logic across schedulers)
# ============================================================

def resolve_benchmark_mode(cli_value: Optional[str], default_mode: str) -> str:
    def _norm(value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        text = str(value).strip().upper()
        return text or None

    cli_mode = _norm(cli_value)
    env_mode = _norm(os.getenv("BENCHMARK_MODE"))
    allowed = {"MAVPROXY", "SYNTHETIC"}

    if cli_mode and cli_mode not in allowed:
        raise ValueError(f"Invalid --mode '{cli_mode}', must be MAVPROXY or SYNTHETIC")
    if env_mode and env_mode not in allowed:
        raise ValueError(f"Invalid BENCHMARK_MODE '{env_mode}', must be MAVPROXY or SYNTHETIC")
    if cli_mode and env_mode and cli_mode != env_mode:
        raise RuntimeError(f"BENCHMARK_MODE conflict: cli={cli_mode} env={env_mode}")

    return cli_mode or env_mode or default_mode

# ============================================================
# Logging
# ============================================================

def log(msg: str):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"[{ts}] [sgcs-follow] {msg}", flush=True)

# ============================================================
# MAVProxy (GCS GUI)
# ============================================================

def start_mavproxy_gui() -> subprocess.Popen | None:
    """Start MAVProxy with map+console on the GCS.

    This is for operator visibility (monitor/map), not for traffic generation.
    We bind MAVProxy to the plaintext RX port so it can display MAVLink that
    arrives via the tunnel.
    """
    try:
        bind_host = str(CONFIG.get("GCS_PLAINTEXT_BIND", "0.0.0.0"))
        listen_port = int(CONFIG.get("GCS_PLAINTEXT_RX", GCS_PLAIN_RX_PORT))
        qgc_port = int(CONFIG.get("QGC_PORT", 14550))
        sniff_port = int(CONFIG.get("GCS_TELEMETRY_SNIFF_PORT", 14552))

        master_str = f"udpin:{bind_host}:{listen_port}"
        cmd = [
            sys.executable,
            "-m",
            "MAVProxy.mavproxy",
            f"--master={master_str}",
            "--dialect=ardupilotmega",
            "--nowait",
            "--map",
            "--console",
            f"--out=udp:127.0.0.1:{qgc_port}",
            f"--out=udp:127.0.0.1:{sniff_port}",
        ]

        env = os.environ.copy()
        env["TERM"] = env.get("TERM") or "dumb"

        creationflags = 0
        if sys.platform == "win32":
            creationflags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)

        log(f"Starting MAVProxy GUI: {' '.join(cmd)}")
        return subprocess.Popen(
            cmd,
            stdin=None,
            stdout=None,
            stderr=None,
            env=env,
            creationflags=creationflags,
        )
    except Exception as e:
        log(f"WARN: MAVProxy GUI failed to start: {e}")
        return None

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

# ============================================================
# Control Server (GCS listens for drone commands)
# ============================================================

class ControlServer:
    """TCP control server - GCS listens for commands from drone"""
    
    def __init__(self, proxy: GcsProxyManager, mode: str):
        self.proxy = proxy
        self.mode = mode
        self.traffic = None
        self.server_sock = None
        self.running = False
        self.thread = None
        self.rate_mbps = DEFAULT_RATE_MBPS
        self.duration = DEFAULT_DURATION
    
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
            return {
                "status": "ok",
                "proxy_running": self.proxy.is_running(),
                "current_suite": self.proxy.current_suite,
                "traffic_complete": traffic_stats.get("complete", False),
                "traffic_stats": traffic_stats,
            }
        
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

            if self.mode == "MAVPROXY":
                return {"status": "error", "message": "traffic_generation_disabled"}
            
            # Start GCS proxy
            if not self.proxy.start(suite):
                return {"status": "error", "message": "proxy_start_failed"}
            
            # Wait a moment for handshake
            time.sleep(1.0)
            
            # Start traffic generation
            if self.traffic:
                self.traffic.stop()
            
            self.traffic = TrafficGenerator(self.rate_mbps)
            self.traffic.start(duration)
            
            return {"status": "ok", "message": "started"}
        
        elif cmd == "start_proxy":
            # Drone tells GCS to start proxy only (no traffic yet)
            suite = request.get("suite")
            
            if not suite:
                return {"status": "error", "message": "missing suite"}
            
            log(f"Start proxy requested for suite: {suite}")
            
            # Start GCS proxy
            if not self.proxy.start(suite):
                return {"status": "error", "message": "proxy_start_failed"}
            
            return {"status": "ok", "message": "proxy_started"}
        
        elif cmd == "start_traffic":
            # Drone tells GCS to start traffic (proxy already running)
            duration = request.get("duration", self.duration)

            if self.mode == "MAVPROXY":
                return {"status": "error", "message": "traffic_generation_disabled"}
            
            if not self.proxy.is_running():
                return {"status": "error", "message": "proxy_not_running"}
            
            log(f"Starting traffic: {self.rate_mbps} Mbps for {duration}s")
            
            # Start traffic generation
            if self.traffic:
                self.traffic.stop()
            
            self.traffic = TrafficGenerator(self.rate_mbps)
            self.traffic.start(duration)
            
            return {"status": "ok", "message": "traffic_started"}
        
        elif cmd == "prepare_rekey":
            # Drone tells GCS to prepare for rekey (stop proxy)
            log("Prepare rekey: stopping proxy...")
            self.proxy.stop()
            
            if self.traffic:
                self.traffic.stop()
                self.traffic = None
            
            return {"status": "ok", "message": "ready_for_rekey"}
        
        elif cmd == "stop":
            log("Stop command received")
            self.proxy.stop()
            
            if self.traffic:
                self.traffic.stop()
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
            self.traffic.stop()

# ============================================================
# Main
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="GCS Scheduler (Follower)")
    parser.add_argument("--mode", type=str, help="Benchmark mode: MAVPROXY or SYNTHETIC")
    args = parser.parse_args()

    args.mode_resolved = resolve_benchmark_mode(args.mode, default_mode="MAVPROXY")
    log(f"BENCHMARK_MODE resolved to {args.mode_resolved}")
    
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

    if args.mode_resolved == "MAVPROXY":
        log("ERROR: MAVProxy-only mode is not supported by sgcs.py; use sgcs_mav.py")
        return 2
    
    # Initialize components
    proxy = GcsProxyManager()
    control = ControlServer(proxy, args.mode_resolved)
    control.start()

    # Start MAVProxy GUI (map/console) for operator visibility
    mavproxy_proc = start_mavproxy_gui()

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
        while not shutdown.is_set():
            shutdown.wait(timeout=1.0)
    finally:
        log("Shutting down...")
        if mavproxy_proc:
            try:
                mavproxy_proc.terminate()
            except Exception:
                pass
        control.stop()
        proxy.stop()
    
    log("GCS scheduler stopped")
    return 0

if __name__ == "__main__":
    sys.exit(main())
