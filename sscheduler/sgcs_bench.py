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
import atexit
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import asdict
from typing import Dict, List, Any, Optional, Tuple

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import CONFIG
from core.suites import get_suite, list_suites
from core.process import ManagedProcess
from core.clock_sync import ClockSync
from core.mavlink_collector import MavLinkMetricsCollector, HAS_PYMAVLINK
# GCS system metrics collection (runtime)
from core.metrics_collectors import SystemCollector
# Comprehensive metrics aggregator (GCS side)
from core.metrics_aggregator import MetricsAggregator
# NOTE: GCS system resource metrics removed per POLICY REALIGNMENT
# GCS is non-constrained observer; only validation metrics retained

# Import RobustLogger for aggressive append-mode logging
try:
    from core.robust_logger import RobustLogger, SyncTracker
    HAS_ROBUST_LOGGER = True
except ImportError:
    HAS_ROBUST_LOGGER = False
    RobustLogger = None
    SyncTracker = None

# =============================================================================
# Configuration
# =============================================================================

DRONE_HOST = str(CONFIG.get("DRONE_HOST", "192.168.0.100"))
GCS_HOST = str(CONFIG.get("GCS_HOST", "192.168.0.100"))
GCS_CONTROL_HOST = str(CONFIG.get("GCS_CONTROL_HOST", "0.0.0.0"))
GCS_CONTROL_PORT = int(CONFIG.get("GCS_CONTROL_PORT", 48080))

GCS_PLAIN_TX_PORT = int(CONFIG.get("GCS_PLAINTEXT_TX", 47001))
GCS_PLAIN_RX_PORT = int(CONFIG.get("GCS_PLAINTEXT_RX", 47002))
DRONE_PLAIN_RX_PORT = int(CONFIG.get("DRONE_PLAINTEXT_RX", 47004))

MAVLINK_SNIFF_PORT = 14552  # MAVProxy output for telemetry sniffing
MAVLINK_INPUT_PORT = GCS_PLAIN_RX_PORT  # MAVProxy input from proxy (47002)
QGC_PORT = 14550            # Output for QGC/Local tools

SECRETS_DIR = Path(__file__).parent.parent / "secrets" / "matrix"
ROOT = Path(__file__).parent.parent
# Note: LOGS_DIR is now set dynamically when drone sends run_id
# to ensure consistent log directory between GCS and drone
_LOGS_DIR_BASE = ROOT / "logs" / "benchmarks"
LOGS_DIR: Path = None  # Set dynamically in GcsBenchmarkServer

# =============================================================================
# Mode Resolution (identical logic across schedulers)
# =============================================================================

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

PAYLOAD_SIZE = 1200
DEFAULT_RATE_MBPS = 110.0

# MAVProxy configuration
MAVPROXY_ENABLE_GUI = True  # Enable --map and --console

class UdpTrafficGenerator:
    """Best-effort UDP traffic generator for plaintext path."""

    def __init__(self, host: str, port: int, payload_size: int = 256, rate_hz: float = 20.0):
        self.host = host
        self.port = port
        self.payload = b"x" * max(1, int(payload_size))
        self.rate_hz = float(rate_hz)
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._sock: Optional[socket.socket] = None

    def start(self) -> None:
        # TRAFFIC GENERATION DISABLED FOR LIVE MAVLINK
        pass

    def stop(self) -> None:
        # TRAFFIC GENERATION DISABLED FOR LIVE MAVLINK
        pass

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
        self.process: Optional[ManagedProcess] = None
        self._log_handle = None
    
    def start(self) -> bool:
        """Start MAVProxy with map and console if enabled."""
        if self.process and self.process.is_running():  # BUG-08 fix: was poll()
            log("[MAVPROXY] Already running")
            return True
        
        # Build command - use python -m MAVProxy on Windows
        if platform.system() == "Windows":
            cmd = [
                sys.executable, "-m", "MAVProxy.mavproxy",
                f"--master=udpin:127.0.0.1:{MAVLINK_INPUT_PORT}",
                "--dialect=ardupilotmega",
                "--nowait",
                f"--out=udp:127.0.0.1:{MAVLINK_SNIFF_PORT}",
                f"--out=udp:127.0.0.1:{QGC_PORT}",
            ]
        else:
            cmd = [
                "mavproxy.py",
                f"--master=udpin:127.0.0.1:{MAVLINK_INPUT_PORT}",
                "--dialect=ardupilotmega",
                "--nowait",
                f"--out=udp:127.0.0.1:{MAVLINK_SNIFF_PORT}",
                f"--out=udp:127.0.0.1:{QGC_PORT}",
            ]
        
        if self.enable_gui:
            cmd.extend(["--map", "--console"])
            log("[MAVPROXY] Starting with GUI (map + console)")
        else:
            cmd.append("--daemon")
            log("[MAVPROXY] Starting headless (--daemon)")
        
        try:
            # Log file for MAVProxy output (only used in headless mode)
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            log_path = self.logs_dir / f"mavproxy_gcs_{timestamp}.log"
            
            # BUG-09 fix: actually open the log file for headless mode
            if not self.enable_gui:
                try:
                    self._log_handle = open(log_path, "w", encoding="utf-8")
                except Exception:
                    self._log_handle = subprocess.DEVNULL
            
            # Start MAVProxy - always use new_console on Windows
            # because prompt_toolkit requires a Windows console buffer.
            # CRITICAL: stdout/stderr MUST be None when new_console=True,
            # otherwise the file handles override the console screen buffer
            # and prompt_toolkit still fails with NoConsoleScreenBufferError.
            # The --daemon flag suppresses interactive prompts in headless mode.
            self.process = ManagedProcess(
                cmd=cmd,
                name="mavproxy-gcs",
                stdout=None,
                stderr=None,
                new_console=True  # Always needed on Windows for prompt_toolkit
            )
            
            if self.process.start():
                log(f"[MAVPROXY] Started (PID: {self.process.process.pid})")
                return True
            else:
                log("[MAVPROXY] Failed to start ManagedProcess")
                return False
            
        except FileNotFoundError:
            log("[MAVPROXY] mavproxy.py not found in PATH")
            return False
        except Exception as e:
            log(f"[MAVPROXY] Failed to start: {e}")
            return False
    
    def stop(self):
        """Stop MAVProxy."""
        if self.process:
            self.process.stop()
            self.process = None
            log("[MAVPROXY] Stopped")
        
        if self._log_handle:
            self._log_handle.close()
            self._log_handle = None
    
    def is_running(self) -> bool:
        return self.process is not None and self.process.is_running()


# =============================================================================
# GCS System Metrics - REMOVED PER POLICY REALIGNMENT
# =============================================================================
# Justification: GCS is non-constrained. CPU/memory/thread metrics do NOT
# influence policy decisions, suite ranking, or scheduler choices.
# Collecting them adds overhead without policy value.
# =============================================================================

class GcsSystemMetricsCollector:
    """Collects GCS system metrics during a suite run."""

    def __init__(self, sample_interval_s: float = 0.5):
        self._collector = SystemCollector()
        self._interval = sample_interval_s
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._samples: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._samples = []

        def loop():
            while self._running:
                sample = self._collector.collect()
                with self._lock:
                    self._samples.append(sample)
                time.sleep(self._interval)

        self._thread = threading.Thread(target=loop, daemon=True)
        self._thread.start()

    def stop(self) -> Dict[str, Any]:
        if not self._running:
            return {}
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)

        with self._lock:
            samples = list(self._samples)

        if not samples:
            return {}

        def _numeric(values: List[Any]) -> List[float]:
            return [v for v in values if isinstance(v, (int, float))]

        cpu_vals = _numeric([s.get("cpu_percent") for s in samples])
        last = samples[-1]

        return {
            "cpu_usage_avg_percent": sum(cpu_vals) / len(cpu_vals) if cpu_vals else None,
            "cpu_usage_peak_percent": max(cpu_vals) if cpu_vals else None,
            "cpu_freq_mhz": last.get("cpu_freq_mhz"),
            "memory_rss_mb": last.get("memory_rss_mb"),
            "memory_vms_mb": last.get("memory_vms_mb"),
            "thread_count": last.get("thread_count"),
            "temperature_c": last.get("temperature_c"),
            "uptime_s": last.get("uptime_s"),
            "load_avg_1m": last.get("load_avg_1m"),
            "load_avg_5m": last.get("load_avg_5m"),
            "load_avg_15m": last.get("load_avg_15m"),
        }
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
        
        # Ensure subprocess can find 'core' package
        env = os.environ.copy()
        project_root = str(Path(__file__).parent.parent.absolute())
        existing_pp = env.get("PYTHONPATH", "")
        if project_root not in existing_pp:
            sep = ";" if sys.platform.startswith("win") else ":"
            env["PYTHONPATH"] = f"{project_root}{sep}{existing_pp}" if existing_pp else project_root

        self.managed_proc = ManagedProcess(
            cmd=cmd,
            name=f"gcs-proxy-{suite_name}",
            stdout=self._log_handle,
            stderr=subprocess.STDOUT,
            env=env
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
    
    def __init__(self, logs_dir: Path, run_id: str, enable_gui: bool = True, mode: str = "MAVPROXY"):
        global LOGS_DIR
        
        self.run_id = run_id
        self.mode = mode
        self._active_run_id = run_id  # Track the active run_id from drone
        
        # BUG-16 fix: use consistent LOGS_DIR — the run-specific path takes precedence
        # The logs_dir parameter from main() is already run-specific, but the
        # global LOGS_DIR must also be updated so other code sees the same path.
        LOGS_DIR = _LOGS_DIR_BASE / f"live_run_{run_id}"
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        self.logs_dir = LOGS_DIR
        
        # Components
        self.proxy = GcsProxyManager(self.logs_dir)
        self.mavproxy = GcsMavProxyManager(self.logs_dir, enable_gui=enable_gui)
        self.mavlink_monitor = MavLinkMetricsCollector(role="gcs") if HAS_PYMAVLINK else None
        self.mavlink_available = HAS_PYMAVLINK
        self.clock_sync = ClockSync()
        self.system_metrics = GcsSystemMetricsCollector()
        self.metrics_aggregator = MetricsAggregator(
            role="gcs",
            output_dir=str(LOGS_DIR / "comprehensive")
        )
        self.metrics_aggregator.set_run_id(run_id)
        self.traffic_gen = UdpTrafficGenerator("127.0.0.1", GCS_PLAIN_TX_PORT)
        
        # Initialize sync tracker and robust logger (aggressive append-mode)
        self.sync_tracker = None
        self.robust_logger = None
        if HAS_ROBUST_LOGGER:
            try:
                self.sync_tracker = SyncTracker()
                self.robust_logger = RobustLogger(
                    run_id=run_id,
                    role="gcs",
                    base_dir=_LOGS_DIR_BASE,
                    sync_tracker=self.sync_tracker,
                )
                log("RobustLogger initialized for aggressive append-mode logging")
            except Exception as e:
                log(f"RobustLogger init failed: {e}", "WARN")
        
        # Server state
        self.server_sock: Optional[socket.socket] = None
        self.running = False
        self.thread: Optional[threading.Thread] = None
        
        # Current suite state
        self.current_suite: Optional[str] = None
        self.handshake_start_time = 0.0
        self.suite_log = self.logs_dir / "gcs_suite_metrics.jsonl"

        self._handshake_timeout_s = 45.0
        self._shutdown_reason: Optional[str] = None
        self._shutdown_error: bool = False
        self._cleanup_done: bool = False
    
    def _update_run_id(self, new_run_id: str):
        """Update log directory when drone sends its run_id."""
        global LOGS_DIR
        
        if new_run_id == self._active_run_id:
            return  # No change needed
        
        log(f"Updating run_id from {self._active_run_id} to {new_run_id}")
        self._active_run_id = new_run_id
        
        # Update LOGS_DIR
        LOGS_DIR = _LOGS_DIR_BASE / f"live_run_{new_run_id}"
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        self.logs_dir = LOGS_DIR
        
        # Reinitialize components with new directory
        # BUG-03 fix: stop old proxy before creating a new one
        if self.proxy:
            try:
                self.proxy.stop()
            except Exception:
                pass
        self.proxy = GcsProxyManager(self.logs_dir)
        self.suite_log = self.logs_dir / "gcs_suite_metrics.jsonl"
        
        # Reinitialize metrics aggregator
        self.metrics_aggregator = MetricsAggregator(
            role="gcs",
            output_dir=str(LOGS_DIR / "comprehensive")
        )
        self.metrics_aggregator.set_run_id(new_run_id)
        
        # Reinitialize robust logger
        if HAS_ROBUST_LOGGER:
            try:
                if self.robust_logger:
                    self.robust_logger.stop()
                self.robust_logger = RobustLogger(
                    run_id=new_run_id,
                    role="gcs",
                    base_dir=_LOGS_DIR_BASE,
                    sync_tracker=self.sync_tracker,
                )
            except Exception as e:
                log(f"RobustLogger reinit failed: {e}", "WARN")
    
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
        if self.mode == "MAVPROXY" and not self.mavproxy.is_running():
            self._shutdown_reason = "error: mavproxy_not_running"
            self._shutdown_error = True
            log("MAVProxy-only mode requires MAVProxy to be running; aborting", "ERROR")
            self.shutdown(self._shutdown_reason, error=True)
            return
        
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
            # Stop proxy
            self.proxy.stop()
            self.current_suite = None
            
            return {"status": "ok"}
        
        elif cmd == "start_proxy":
            suite = request.get("suite")
            if not suite:
                return {"status": "error", "message": "missing suite parameter"}
            
            # Check if drone sent a run_id - use it to sync log directories
            drone_run_id = request.get("run_id")
            if drone_run_id and drone_run_id != self._active_run_id:
                self._update_run_id(drone_run_id)
            
            log(f"CMD: start_proxy({suite})")
            
            # Start robust logging for this suite
            if self.robust_logger:
                suite_config = get_suite(suite)
                self.robust_logger.start_suite(suite, suite_config)
                self.robust_logger.log_event("suite_started_from_drone", {
                    "suite": suite,
                    "drone_run_id": drone_run_id,
                })
            
            # Reset MAVLink validation counters per suite by restarting collector
            if self.mavlink_monitor:
                try:
                    self.mavlink_monitor.stop()
                except Exception:
                    pass
            self.mavlink_monitor = MavLinkMetricsCollector(role="gcs") if HAS_PYMAVLINK else None
            if self.mavlink_monitor:
                self.mavlink_monitor.start_sniffing(port=MAVLINK_SNIFF_PORT)

            # Start GCS system sampling
            self.system_metrics.start()
            
            # Record suite start + handshake start (monotonic)
            suite_config = get_suite(suite)
            self.metrics_aggregator.start_suite(suite, suite_config)
            self.metrics_aggregator.record_handshake_start()
            self.metrics_aggregator.record_control_plane_metrics(
                scheduler_action_type=cmd,
                scheduler_action_reason="command",
                policy_name="GcsBenchmarkServer",
                policy_state="ACTIVE",
            )
            self.handshake_start_time = time.time()
            
            # Ensure MAVProxy is running (no restarts in MAVProxy-only mode)
            if not self.mavproxy.is_running():
                if self.mode == "MAVPROXY":
                    return {"status": "error", "message": "mavproxy_not_running"}
                log("[MAVPROXY] Restarting crashed/stopped MAVProxy instance...")
                self.mavproxy.start()
            
            # Start proxy
            if not self.proxy.start(suite):
                return {"status": "error", "message": "proxy_start_failed"}
            
            self.current_suite = suite

            # Record handshake end asynchronously to avoid blocking start_proxy.
            # C4 fix: Capture the current aggregator reference at launch time so
            # that _update_run_id replacing self.metrics_aggregator won't cause
            # the thread to write to a stale or wrong-suite aggregator.
            _launch_aggregator = self.metrics_aggregator
            _launch_suite = suite

            def _await_handshake(agg=_launch_aggregator, s=_launch_suite) -> None:
                if self.current_suite != s:
                    return  # Suite changed; this thread is stale
                if self._wait_for_handshake_ok(timeout_s=self._handshake_timeout_s):
                    if self.current_suite == s:  # Double-check after wait
                        agg.record_handshake_end(success=True)
                else:
                    if self.current_suite == s:
                        agg.record_handshake_end(
                            success=False,
                            failure_reason="handshake_timeout"
                        )

            threading.Thread(target=_await_handshake, daemon=True).start()
            
            return {
                "status": "ok",
                "message": "suite_started",
                "suite": suite,
                "handshake_start_time": self.handshake_start_time,
            }
        
        elif cmd == "start_traffic":
            log("CMD: start_traffic")
            if self.mode == "MAVPROXY":
                return {"status": "error", "message": "traffic_generation_disabled"}
            try:
                self.traffic_gen.start()
            except Exception:
                return {"status": "error", "message": "traffic_start_failed"}
            return {"status": "ok"}

        elif cmd == "stop_traffic":
            log("CMD: stop_traffic")
            if self.mode == "MAVPROXY":
                return {"status": "error", "message": "traffic_generation_disabled"}
            try:
                self.traffic_gen.stop()
            except Exception:
                return {"status": "error", "message": "traffic_stop_failed"}
            return {"status": "ok"}
        
        elif cmd == "stop_suite":
            log("CMD: stop_suite")
            try:
                self.traffic_gen.stop()
            except Exception:
                pass
            # Collect validation-only MAVLink metrics
            mavlink_metrics = None
            if self.mavlink_monitor:
                mavlink_metrics = self.mavlink_monitor.stop()

            # Collect GCS system metrics
            system_gcs = self.system_metrics.stop()

            # Stop proxy
            self.proxy.stop()
            
            # BUG-14 fix: don't restart MavLink monitor between suites.
            # The monitor will be started fresh by start_suite.
            # Starting it here captures irrelevant inter-suite packets.

            proxy_status = self._read_proxy_status()
            mavlink_validation = None
            latency_metrics = None
            if mavlink_metrics:
                mavlink_validation = {
                    "total_msgs_received": mavlink_metrics.get("total_msgs_received"),
                    "seq_gap_count": mavlink_metrics.get("seq_gap_count"),
                }
                latency_metrics = {
                    "one_way_latency_avg_ms": mavlink_metrics.get("one_way_latency_avg_ms"),
                    "one_way_latency_p95_ms": mavlink_metrics.get("one_way_latency_p95_ms"),
                    "jitter_avg_ms": mavlink_metrics.get("jitter_avg_ms"),
                    "jitter_p95_ms": mavlink_metrics.get("jitter_p95_ms"),
                    "latency_sample_count": mavlink_metrics.get("latency_sample_count"),
                    "latency_invalid_reason": mavlink_metrics.get("latency_invalid_reason"),
                    "rtt_avg_ms": mavlink_metrics.get("rtt_avg_ms"),
                    "rtt_p95_ms": mavlink_metrics.get("rtt_p95_ms"),
                    "rtt_sample_count": mavlink_metrics.get("rtt_sample_count"),
                    "rtt_invalid_reason": mavlink_metrics.get("rtt_invalid_reason"),
                }

            gcs_export = self.metrics_aggregator.get_exportable_data()
            payload = {
                "status": "ok",
                "suite": self.current_suite,
                "run_id": self._active_run_id or "",
                "mavlink_validation": mavlink_validation,
                "latency_jitter": latency_metrics,
                "system_gcs": system_gcs,
                "metrics_export": gcs_export,
                "proxy_status": proxy_status,
            }
            
            # Log metrics incrementally using robust logger (AGGRESSIVE LOGGING)
            if self.robust_logger:
                if mavlink_validation:
                    self.robust_logger.log_metrics_incremental("mavlink", mavlink_validation)
                if latency_metrics:
                    self.robust_logger.log_metrics_incremental("latency", latency_metrics)
                if system_gcs:
                    self.robust_logger.log_metrics_incremental("system", system_gcs)
                # End suite in robust logger
                self.robust_logger.end_suite(success=True)

            self.metrics_aggregator.record_control_plane_metrics(
                scheduler_action_type=cmd,
                scheduler_action_reason="command",
                policy_name="GcsBenchmarkServer",
                policy_state="ADVANCE",
            )
            self.metrics_aggregator.finalize_suite()

            # Write to JSONL with retry (AGGRESSIVE LOGGING)
            for attempt in range(3):
                try:
                    with open(self.suite_log, "a", encoding="utf-8") as fh:
                        fh.write(json.dumps(payload) + "\n")
                        fh.flush()
                        os.fsync(fh.fileno())  # BUG-23 fix: use module-level os
                    break
                except Exception as e:
                    if attempt < 2:
                        time.sleep(0.5)
                    else:
                        log(f"Failed to write suite log after 3 attempts: {e}", "WARN")

            return payload
        
        elif cmd == "chronos_sync":
            try:
                resp = self.clock_sync.server_handle_sync(request)
                # Record sync in robust logger
                if self.sync_tracker and self.robust_logger:
                    # Extract offset from response
                    t1 = request.get("t1", 0)
                    t2 = resp.get("t2", 0)
                    t3 = resp.get("t3", 0)
                    if t1 and t2 and t3:
                        # GCS is the server, so we record from its perspective
                        self.robust_logger.log_event("clock_sync_served", {
                            "t1": t1, "t2": t2, "t3": t3,
                        })
                return resp
            except Exception as e:
                return {"status": "error", "message": str(e)}
        
        return {"status": "error", "message": f"unknown_cmd: {cmd}"}
    
    def stop(self):
        """Stop the server."""
        log("Shutting down...")
        self.running = False

        try:
            self.traffic_gen.stop()
        except Exception:
            pass
        
        self.proxy.stop()
        self.mavproxy.stop()
        
        # Stop robust logger (flushes all buffered data)
        if self.robust_logger:
            self.robust_logger.log_event("server_shutdown", {"reason": self._shutdown_reason})
            self.robust_logger.stop()
        
        if self.server_sock:
            self.server_sock.close()
        
        if self.thread:
            self.thread.join(timeout=2.0)
        self._cleanup_done = True

    def shutdown(self, reason: str, *, error: bool) -> None:
        if self._cleanup_done:
            return
        level = "ERROR" if error else "INFO"
        log(f"Shutdown reason: {reason}", level)
        self.stop()

    def _read_proxy_status(self) -> Dict[str, Any]:
        status_path = self.logs_dir / "gcs_status.json"
        if not status_path.exists():
            return {}
        try:
            with open(status_path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            return {}

    def _wait_for_handshake_ok(self, timeout_s: float = 45.0) -> bool:
        """Wait for proxy status to show handshake completion."""
        deadline = time.monotonic() + float(timeout_s)
        while time.monotonic() < deadline:
            status = self._read_proxy_status()
            state = status.get("status") if isinstance(status, dict) else None
            if state in {"handshake_ok", "running"}:
                return True
            time.sleep(0.2)
        return False

# =============================================================================
# Main Entry Point
# =============================================================================

def main():
    global LOGS_DIR
    parser = argparse.ArgumentParser(description="GCS Benchmark Server - Operation Chronos v2")
    parser.add_argument("--port", type=int, default=GCS_CONTROL_PORT,
                        help=f"Control server port (default: {GCS_CONTROL_PORT})")
    parser.add_argument("--run-id", type=str, default=None,
                        help="Run ID (default: auto-generated)")
    parser.add_argument("--no-gui", action="store_true",
                        help="Disable MAVProxy GUI (map + console)")
    parser.add_argument("--log-dir", type=str,
                        help="Override base log directory for this run")
    parser.add_argument("--mode", type=str,
                        help="Benchmark mode: MAVPROXY or SYNTHETIC")
    args = parser.parse_args()

    args.mode_resolved = resolve_benchmark_mode(args.mode, default_mode="MAVPROXY")
    log(f"BENCHMARK_MODE resolved to {args.mode_resolved}")

    if args.log_dir:
        LOGS_DIR = Path(args.log_dir).expanduser().resolve()
    else:
        # Default: use the base logs directory with a timestamped run folder
        LOGS_DIR = _LOGS_DIR_BASE / f"live_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    
    # NOTE: GUI is always enabled for benchmark runs (map + console)
    
    # Generate run ID
    run_id = args.run_id or f"gcs_bench_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    
    # Create logs directory
    run_logs_dir = LOGS_DIR / run_id
    run_logs_dir.mkdir(parents=True, exist_ok=True)
    
    # Start server
    server = GcsBenchmarkServer(
        logs_dir=run_logs_dir,
        run_id=run_id,
        enable_gui=not args.no_gui,
        mode=args.mode_resolved,
    )

    def _atexit_cleanup():
        try:
            server.shutdown("normal: atexit", error=False)
        except Exception:
            pass

    atexit.register(_atexit_cleanup)
    
    # Handle signals
    def signal_handler(sig, frame):
        log("Interrupt received, stopping...")
        server.shutdown("normal: interrupted", error=False)
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
        server.shutdown("normal: interrupted", error=False)

if __name__ == "__main__":
    main()
