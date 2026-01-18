#!/usr/bin/env python3
"""
GCS Benchmark Server - sscheduler/sgcs_bench.py
"Operation Chronos v2": Comprehensive E2E MAVProxy Benchmark

This script runs on the GCS (Windows) machine and:
1. Listens for commands from drone on TCP 48080
2. Starts/stops crypto proxies per suite
3. Generates traffic through the tunnel
4. Collects GCS-side metrics (CPU, memory, MAVLink)
5. Returns metrics to drone for consolidation

Usage:
    python -m sscheduler.sgcs_bench [--port 48080]

Network:
    - LAN: 192.168.0.100 (GCS) <-> 192.168.0.105 (Drone)
    - Control: TCP 48080 (listens)
    - Plaintext: UDP 47001/47002
    - MAVLink: UDP 14550/14552
"""

import os
import sys
import time
import json
import uuid
import socket
import signal
import argparse
import threading
import subprocess
import statistics
import logging
import platform
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import asdict
from typing import Dict, List, Any, Optional, Tuple

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import CONFIG
from core.suites import get_suite, list_suites
from core.process import ManagedProcess
# NOTE: GCS system resource metrics removed per POLICY REALIGNMENT
# GCS is non-constrained observer; only validation metrics retained

# =============================================================================
# Configuration
# =============================================================================

DRONE_HOST = str(CONFIG.get("DRONE_HOST", "192.168.0.105"))
GCS_HOST = str(CONFIG.get("GCS_HOST", "192.168.0.100"))
GCS_CONTROL_HOST = str(CONFIG.get("GCS_CONTROL_BIND_HOST", "0.0.0.0"))
GCS_CONTROL_PORT = int(CONFIG.get("GCS_CONTROL_PORT", 48080))

GCS_PLAIN_TX_PORT = int(CONFIG.get("GCS_PLAINTEXT_TX", 47001))
GCS_PLAIN_RX_PORT = int(CONFIG.get("GCS_PLAINTEXT_RX", 47002))
DRONE_PLAIN_RX_PORT = int(CONFIG.get("DRONE_PLAINTEXT_RX", 47004))

MAVLINK_SNIFF_PORT = 14552  # MAVProxy output for telemetry sniffing
MAVLINK_INPUT_PORT = 14550  # MAVProxy input from proxy

SECRETS_DIR = Path(__file__).parent.parent / "secrets" / "matrix"
ROOT = Path(__file__).parent.parent
LOGS_DIR = ROOT / "logs" / "benchmarks"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

PAYLOAD_SIZE = 1200
DEFAULT_RATE_MBPS = 110.0

# MAVProxy configuration
MAVPROXY_ENABLE_GUI = True  # Enable --map and --console

# =============================================================================
# Logging Setup
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [sgcs-bench] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%dT%H:%M:%SZ'
)
logger = logging.getLogger("sgcs_bench")

def log(msg: str, level: str = "INFO"):
    getattr(logger, level.lower(), logger.info)(msg)

# =============================================================================
# Environment Info
# =============================================================================

def get_kernel_version() -> str:
    """Get kernel/OS version."""
    try:
        return platform.platform()
    except Exception:
        return "unknown"

def get_python_env() -> str:
    """Get Python environment info."""
    return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

# =============================================================================
# MAVProxy Manager (GCS side with GUI)
# =============================================================================

class GcsMavProxyManager:
    """
    Manages MAVProxy subprocess on GCS side with optional GUI (--map --console).
    
    MAVProxy receives telemetry from the crypto proxy on UDP 14550
    and outputs to UDP 14552 for sniffing/validation.
    """
    
    def __init__(self, logs_dir: Path, enable_gui: bool = MAVPROXY_ENABLE_GUI):
        self.logs_dir = logs_dir
        self.enable_gui = enable_gui
        self.process: Optional[subprocess.Popen] = None
        self._log_handle = None
    
    def start(self) -> bool:
        """Start MAVProxy with map and console if enabled."""
        if self.process and self.process.poll() is None:
            log("[MAVPROXY] Already running")
            return True
        
        # Build command
        cmd = [
            "mavproxy.py",
            f"--master=udp:127.0.0.1:{MAVLINK_INPUT_PORT}",
            f"--out=udp:127.0.0.1:{MAVLINK_SNIFF_PORT}",
        ]
        
        if self.enable_gui:
            cmd.extend(["--map", "--console"])
            log("[MAVPROXY] Starting with GUI (map + console)")
        else:
            log("[MAVPROXY] Starting headless")
        
        try:
            # Log file for MAVProxy output
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            log_path = self.logs_dir / f"mavproxy_gcs_{timestamp}.log"
            self._log_handle = open(log_path, "w", encoding="utf-8")
            
            # Start MAVProxy
            self.process = subprocess.Popen(
                cmd,
                stdout=self._log_handle,
                stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if platform.system() == "Windows" else 0
            )
            
            # Give it time to start
            time.sleep(2.0)
            
            if self.process.poll() is not None:
                log(f"[MAVPROXY] Exited early with code {self.process.returncode}")
                return False
            
            log(f"[MAVPROXY] Started (PID: {self.process.pid})")
            return True
            
        except FileNotFoundError:
            log("[MAVPROXY] mavproxy.py not found in PATH")
            return False
        except Exception as e:
            log(f"[MAVPROXY] Failed to start: {e}")
            return False
    
    def stop(self):
        """Stop MAVProxy."""
        if self.process:
            try:
                if platform.system() == "Windows":
                    self.process.terminate()
                else:
                    self.process.terminate()
                self.process.wait(timeout=5.0)
                log("[MAVPROXY] Stopped")
            except Exception as e:
                log(f"[MAVPROXY] Error stopping: {e}")
                try:
                    self.process.kill()
                except Exception:
                    pass
            self.process = None
        
        if self._log_handle:
            self._log_handle.close()
            self._log_handle = None
    
    def is_running(self) -> bool:
        return self.process is not None and self.process.poll() is None


# =============================================================================
# GCS System Metrics - REMOVED PER POLICY REALIGNMENT
# =============================================================================
# Justification: GCS is non-constrained. CPU/memory/thread metrics do NOT
# influence policy decisions, suite ranking, or scheduler choices.
# Collecting them adds overhead without policy value.
# =============================================================================
# REMOVED METRICS:
#   - cpu_avg_percent
#   - cpu_peak_percent  
#   - memory_rss_mb
#   - thread_count
# =============================================================================

# =============================================================================
# MAVLink Metrics Collector (GCS side)
# =============================================================================

class GcsMavLinkCollector:
    """
    Collects MAVLink validation metrics on GCS side via pymavlink.
    
    POLICY REALIGNMENT: Only validation-critical metrics retained:
      - total_msgs_received: Cross-side correlation
      - seq_gap_count: MAVLink integrity validation
    
    REMOVED (non-essential):
      - msg_type_counts histogram
      - heartbeat_interval_ms statistics
    """
    
    def __init__(self, listen_port: int = MAVLINK_SNIFF_PORT):
        self.listen_port = listen_port
        self._conn = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        
        # VALIDATION-ONLY counters
        self._total_rx = 0
        self._seq_gaps = 0
        self._last_seq: Dict[int, int] = {}
        
        self._mavutil = None
        try:
            from pymavlink import mavutil
            self._mavutil = mavutil
        except ImportError:
            log("[MAVLINK] pymavlink not available")
    
    def start(self):
        """Start listening for MAVLink messages."""
        if not self._mavutil:
            return False
        
        try:
            self._conn = self._mavutil.mavlink_connection(
                f"udpin:0.0.0.0:{self.listen_port}",
                source_system=255
            )
            self._running = True
            self._thread = threading.Thread(target=self._listen_loop, daemon=True)
            self._thread.start()
            log(f"[MAVLINK] Listening on UDP {self.listen_port}")
            return True
        except Exception as e:
            log(f"[MAVLINK] Failed to start: {e}")
            return False
    
    def _listen_loop(self):
        while self._running:
            try:
                msg = self._conn.recv_match(blocking=True, timeout=1.0)
                if msg:
                    self._process_message(msg)
            except Exception:
                if self._running:
                    pass
    
    def _process_message(self, msg):
        """Process MAVLink message - validation metrics only."""
        with self._lock:
            self._total_rx += 1
            
            # Sequence gap detection for integrity validation
            if hasattr(msg, '_header'):
                sysid = msg._header.srcSystem
                seq = msg._header.seq
                if sysid in self._last_seq:
                    expected = (self._last_seq[sysid] + 1) % 256
                    if seq != expected:
                        self._seq_gaps += 1
                self._last_seq[sysid] = seq
    
    def stop(self) -> Dict[str, Any]:
        """Stop and return validation metrics only."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        
        with self._lock:
            # VALIDATION-ONLY output
            return {
                "total_msgs_received": self._total_rx,
                "seq_gap_count": self._seq_gaps,
            }
    
    def reset(self):
        """Reset counters for new suite."""
        with self._lock:
            self._total_rx = 0
            self._seq_gaps = 0
            self._last_seq = {}

# =============================================================================
# Traffic Generator
# =============================================================================

class TrafficGenerator:
    """Generates UDP traffic from GCS to drone through the tunnel."""
    
    def __init__(self, rate_mbps: float = DEFAULT_RATE_MBPS):
        self.rate_mbps = rate_mbps
        self.tx_sock: Optional[socket.socket] = None
        self.rx_sock: Optional[socket.socket] = None
        self.running = False
        self.complete = False
        
        self._lock = threading.Lock()
        self._tx_count = 0
        self._rx_count = 0
        self._tx_bytes = 0
        self._rx_bytes = 0
        self._latencies: List[float] = []
    
    def start(self, duration: float):
        """Start traffic generation in background."""
        self.tx_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.tx_sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4 * 1024 * 1024)
        
        self.rx_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.rx_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.rx_sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 * 1024 * 1024)
        self.rx_sock.bind((GCS_HOST, GCS_PLAIN_RX_PORT))
        self.rx_sock.settimeout(1.0)
        
        self.running = True
        self.complete = False
        self._tx_count = 0
        self._rx_count = 0
        self._tx_bytes = 0
        self._rx_bytes = 0
        self._latencies = []
        
        # Start receiver thread
        self.rx_thread = threading.Thread(target=self._receive_loop, daemon=True)
        self.rx_thread.start()
        
        # Start sender thread
        self.tx_thread = threading.Thread(target=self._send_loop, args=(duration,), daemon=True)
        self.tx_thread.start()
        
        log(f"Traffic started: {self.rate_mbps} Mbps for {duration}s")
    
    def _send_loop(self, duration: float):
        """Send packets at target rate with embedded timestamps."""
        packets_per_sec = (self.rate_mbps * 1_000_000) / (8 * PAYLOAD_SIZE)
        interval = 1.0 / packets_per_sec
        batch_size = max(1, int(packets_per_sec / 100))
        batch_interval = interval * batch_size
        
        start_time = time.time()
        end_time = start_time + duration
        seq = 0
        
        while time.time() < end_time and self.running:
            batch_start = time.time()
            
            for _ in range(batch_size):
                try:
                    # Build packet with timestamp
                    ts_ns = time.time_ns()
                    packet = {
                        "ts_ns": ts_ns,
                        "seq": seq,
                        "pad": "X" * (PAYLOAD_SIZE - 100),
                    }
                    data = json.dumps(packet).encode()
                    
                    # Send to drone's plaintext RX port
                    self.tx_sock.sendto(data, (DRONE_HOST, DRONE_PLAIN_RX_PORT))
                    
                    with self._lock:
                        self._tx_count += 1
                        self._tx_bytes += len(data)
                    
                    seq += 1
                except Exception:
                    pass
            
            # Rate limiting
            elapsed = time.time() - batch_start
            if elapsed < batch_interval:
                time.sleep(batch_interval - elapsed)
        
        self.complete = True
        log(f"Traffic complete: TX={self._tx_count}, RX={self._rx_count}")
    
    def _receive_loop(self):
        """Receive echo responses."""
        while self.running:
            try:
                data, addr = self.rx_sock.recvfrom(65535)
                recv_ts = time.time_ns()
                
                with self._lock:
                    self._rx_count += 1
                    self._rx_bytes += len(data)
                
                # Extract send timestamp for latency
                try:
                    pkt = json.loads(data.decode("utf-8"))
                    if "ts_ns" in pkt:
                        rtt_ms = (recv_ts - pkt["ts_ns"]) / 1_000_000
                        with self._lock:
                            self._latencies.append(rtt_ms)
                except Exception:
                    pass
                    
            except socket.timeout:
                continue
            except Exception:
                if self.running:
                    pass
    
    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "tx_count": self._tx_count,
                "rx_count": self._rx_count,
                "tx_bytes": self._tx_bytes,
                "rx_bytes": self._rx_bytes,
                "latencies": self._latencies.copy(),
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
    
    def is_complete(self) -> bool:
        return self.complete

# =============================================================================
# GCS Proxy Manager
# =============================================================================

class GcsProxyManager:
    """Manages GCS proxy subprocess."""
    
    def __init__(self, logs_dir: Path):
        self.logs_dir = logs_dir
        self.managed_proc: Optional[ManagedProcess] = None
        self.current_suite: Optional[str] = None
        self._log_handle = None
    
    def start(self, suite_name: str) -> bool:
        """Start proxy with given suite."""
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
        
        cmd = [
            sys.executable, "-m", "core.run_proxy", "gcs",
            "--suite", suite_name,
            "--gcs-secret-file", str(gcs_key),
            "--quiet",
            "--status-file", str(self.logs_dir / "gcs_status.json")
        ]
        
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        log_path = self.logs_dir / f"gcs_proxy_{suite_name}_{timestamp}.log"
        self._log_handle = open(log_path, "w", encoding="utf-8")
        
        self.managed_proc = ManagedProcess(
            cmd=cmd,
            name=f"gcs-proxy-{suite_name}",
            stdout=self._log_handle,
            stderr=subprocess.STDOUT
        )
        
        if self.managed_proc.start():
            self.current_suite = suite_name
            time.sleep(2.0)
            if not self.managed_proc.is_running():
                log(f"Proxy exited early for {suite_name}")
                return False
            log(f"GCS proxy started for {suite_name}")
            return True
        return False
    
    def stop(self):
        """Stop proxy."""
        if self.managed_proc:
            self.managed_proc.stop()
            self.managed_proc = None
            self.current_suite = None
        if self._log_handle:
            self._log_handle.close()
            self._log_handle = None
    
    def is_running(self) -> bool:
        return self.managed_proc is not None and self.managed_proc.is_running()

# =============================================================================
# Control Server
# =============================================================================

class GcsBenchmarkServer:
    """
    GCS benchmark server - listens for drone commands.
    
    Commands:
        ping: Check if server is ready
        get_info: Return GCS environment info
        prepare_rekey: Stop current proxy
        start_proxy: Start proxy for suite
        start_traffic: Start traffic generation
        stop_suite: Stop suite and return metrics
        shutdown: Graceful shutdown
    """
    
    def __init__(self, logs_dir: Path, run_id: str):
        self.logs_dir = logs_dir
        self.run_id = run_id
        
        # Components
        self.proxy = GcsProxyManager(logs_dir)
        self.mavproxy = GcsMavProxyManager(logs_dir, enable_gui=MAVPROXY_ENABLE_GUI)
        self.traffic: Optional[TrafficGenerator] = None
        # NOTE: GcsSystemMetricsCollector REMOVED - GCS resources not policy-relevant
        self.mavlink_monitor = GcsMavLinkCollector()
        
        # Server state
        self.server_sock: Optional[socket.socket] = None
        self.running = False
        self.thread: Optional[threading.Thread] = None
        
        # Current suite state
        self.current_suite: Optional[str] = None
        self.handshake_start_time = 0.0
    
    def start(self):
        """Start the benchmark server."""
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_sock.bind((GCS_CONTROL_HOST, GCS_CONTROL_PORT))
        self.server_sock.listen(5)
        self.server_sock.settimeout(1.0)
        
        self.running = True
        self.thread = threading.Thread(target=self._server_loop, daemon=True)
        self.thread.start()
        
        # Start MAVProxy with GUI
        if not self.mavproxy.start():
            log("[WARNING] MAVProxy failed to start - continuing without it")
        
        # Start MAVLink monitor
        self.mavlink_monitor.start()
        
        log(f"GCS Benchmark Server listening on {GCS_CONTROL_HOST}:{GCS_CONTROL_PORT}")
        log(f"Run ID: {self.run_id}")
    
    def _server_loop(self):
        while self.running:
            try:
                client, addr = self.server_sock.accept()
                log(f"Connection from {addr}")
                self._handle_client(client)
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    log(f"Server error: {e}")
    
    def _handle_client(self, client: socket.socket):
        try:
            data = b""
            client.settimeout(30.0)
            while True:
                chunk = client.recv(4096)
                if not chunk:
                    break
                data += chunk
                if b"\n" in data:
                    break
            
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
            return {
                "status": "ok",
                "message": "pong",
                "role": "gcs_benchmark",
                "run_id": self.run_id,
            }
        
        elif cmd == "get_info":
            return {
                "status": "ok",
                "hostname": socket.gethostname(),
                "ip": GCS_HOST,
                "kernel_version": get_kernel_version(),
                "python_env": get_python_env(),
            }
        
        elif cmd == "prepare_rekey":
            log("CMD: prepare_rekey")
            
            # Stop traffic if running
            if self.traffic:
                self.traffic.stop()
                self.traffic = None
            
            # Stop proxy
            self.proxy.stop()
            self.current_suite = None
            
            return {"status": "ok"}
        
        elif cmd == "start_proxy":
            suite = request.get("suite")
            if not suite:
                return {"status": "error", "message": "missing suite parameter"}
            
            log(f"CMD: start_proxy({suite})")
            
            # Reset MAVLink validation counters
            self.mavlink_monitor.reset()
            
            # Record handshake start
            self.handshake_start_time = time.time()
            
            # Start proxy
            if not self.proxy.start(suite):
                return {"status": "error", "message": "proxy_start_failed"}
            
            self.current_suite = suite
            
            return {
                "status": "ok",
                "message": "suite_started",
                "suite": suite,
                "handshake_start_time": self.handshake_start_time,
            }
        
        elif cmd == "start_traffic":
            duration = request.get("duration", 10.0)
            rate_mbps = request.get("rate_mbps", DEFAULT_RATE_MBPS)
            
            log(f"CMD: start_traffic(duration={duration}, rate={rate_mbps})")
            
            # Start traffic generator
            self.traffic = TrafficGenerator(rate_mbps=rate_mbps)
            self.traffic.start(duration)
            
            return {"status": "ok", "message": "traffic_started"}
        
        elif cmd == "stop_suite":
            log("CMD: stop_suite")
            
            # Stop traffic
            traffic_stats = {}
            if self.traffic:
                traffic_stats = self.traffic.get_stats()
                self.traffic.stop()
                self.traffic = None
            
            # Collect validation-only MAVLink metrics
            mavlink_metrics = self.mavlink_monitor.stop()
            
            # Stop proxy
            self.proxy.stop()
            
            # Restart MAVLink monitor for next suite
            self.mavlink_monitor = GcsMavLinkCollector()
            self.mavlink_monitor.start()
            
            # POLICY REALIGNMENT: GCS system metrics removed
            # Only traffic validation + MAVLink integrity returned
            return {
                "status": "ok",
                "suite": self.current_suite,
                "traffic_stats": traffic_stats,
                "mavlink_validation": mavlink_metrics,
            }
        
        elif cmd == "shutdown":
            log("CMD: shutdown")
            self.stop()
            return {"status": "ok", "message": "shutting_down"}
        
        return {"status": "error", "message": f"unknown_cmd: {cmd}"}
    
    def stop(self):
        """Stop the server."""
        log("Shutting down...")
        self.running = False
        
        if self.traffic:
            self.traffic.stop()
        
        self.proxy.stop()
        self.mavproxy.stop()
        
        if self.server_sock:
            self.server_sock.close()
        
        if self.thread:
            self.thread.join(timeout=2.0)

# =============================================================================
# Main Entry Point
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="GCS Benchmark Server - Operation Chronos v2")
    parser.add_argument("--port", type=int, default=GCS_CONTROL_PORT,
                        help=f"Control server port (default: {GCS_CONTROL_PORT})")
    parser.add_argument("--run-id", type=str, default=None,
                        help="Run ID (default: auto-generated)")
    parser.add_argument("--no-gui", action="store_true",
                        help="Disable MAVProxy GUI (map + console)")
    args = parser.parse_args()
    
    # Override GUI setting if --no-gui specified
    global MAVPROXY_ENABLE_GUI
    if args.no_gui:
        MAVPROXY_ENABLE_GUI = False
    
    # Generate run ID
    run_id = args.run_id or f"gcs_bench_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    
    # Create logs directory
    run_logs_dir = LOGS_DIR / run_id
    run_logs_dir.mkdir(parents=True, exist_ok=True)
    
    # Start server
    server = GcsBenchmarkServer(
        logs_dir=run_logs_dir,
        run_id=run_id,
    )
    
    # Handle signals
    def signal_handler(sig, frame):
        log("Interrupt received, stopping...")
        server.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    log("=" * 60)
    log("OPERATION CHRONOS v2: GCS Benchmark Server")
    log("=" * 60)
    log(f"Listening for drone commands...")
    log(f"Press Ctrl+C to stop")
    
    server.start()
    
    # Keep main thread alive
    try:
        while server.running:
            time.sleep(1.0)
    except KeyboardInterrupt:
        log("Stopping...")
        server.stop()

if __name__ == "__main__":
    main()
