#!/usr/bin/env python3
"""
Drone Benchmark Scheduler - sscheduler/sdrone_bench.py
"Operation Chronos v2": Comprehensive E2E MAVProxy Benchmark

This script runs on the RPi Drone (controller) and:
1. Cycles through ALL cipher suites deterministically (10s each)
2. Collects Categories A-R metrics (drone-side)
3. Coordinates with GCS via TCP control channel
4. Uses MAVProxy + pymavlink for application-layer metrics
5. Records power/energy via INA219 if available
6. Outputs comprehensive JSONL for post-analysis

Usage:
    python -m sscheduler.sdrone_bench [--cycle-time 10] [--max-suites N]

Network:
    - LAN: 192.168.0.105 (drone) <-> 192.168.0.100 (GCS)
    - GCS Control: TCP 48080
    - Plaintext: UDP 47003/47004
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
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import asdict
from typing import Dict, List, Any, Optional, Tuple

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import CONFIG
from core.suites import get_suite, list_suites
from core.process import ManagedProcess
from core.metrics_schema import (
    ComprehensiveSuiteMetrics,
    RunContextMetrics,
    SuiteCryptoIdentity,
    SuiteLifecycleTimeline,
    HandshakeMetrics,
    CryptoPrimitiveBreakdown,
    RekeyMetrics,
    DataPlaneMetrics,
    LatencyJitterMetrics,
    MavProxyDroneMetrics,
    MavLinkIntegrityMetrics,
    FlightControllerTelemetry,
    ControlPlaneMetrics,
    SystemResourcesDrone,
    PowerEnergyMetrics,
    ObservabilityMetrics,
    ValidationMetrics,
)

# =============================================================================
# Configuration
# =============================================================================

DRONE_HOST = str(CONFIG.get("DRONE_HOST", "192.168.0.105"))
GCS_HOST = str(CONFIG.get("GCS_HOST", "192.168.0.100"))
GCS_CONTROL_PORT = int(CONFIG.get("GCS_CONTROL_PORT", 48080))

DRONE_PLAIN_TX_PORT = int(CONFIG.get("DRONE_PLAINTEXT_TX", 47003))
DRONE_PLAIN_RX_PORT = int(CONFIG.get("DRONE_PLAINTEXT_RX", 47004))

MAVLINK_LISTEN_PORT = 14552  # MAVProxy output for telemetry sniffing
MAVLINK_MASTER_PORT = 14550  # SITL/FC connection

SECRETS_DIR = Path(__file__).parent.parent / "secrets" / "matrix"
ROOT = Path(__file__).parent.parent
LOGS_DIR = ROOT / "logs" / "benchmarks"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_CYCLE_TIME = 10.0  # seconds per suite

# =============================================================================
# Logging Setup
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [sdrone-bench] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%dT%H:%M:%SZ'
)
logger = logging.getLogger("sdrone_bench")

def log(msg: str, level: str = "INFO"):
    getattr(logger, level.lower(), logger.info)(msg)

# =============================================================================
# Environment Info Collection
# =============================================================================

def get_git_info() -> Tuple[str, bool]:
    """Get git commit hash and dirty flag."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=5, cwd=ROOT
        )
        commit = result.stdout.strip()[:12] if result.returncode == 0 else "unknown"
        
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, timeout=5, cwd=ROOT
        )
        dirty = result.returncode != 0 or bool(result.stdout.strip())
        return commit, dirty
    except Exception:
        return "unknown", True

def get_liboqs_version() -> str:
    """Get liboqs version."""
    try:
        import oqs
        return oqs.oqs_version()
    except Exception:
        return "unknown"

def get_kernel_version() -> str:
    """Get kernel version."""
    try:
        import platform
        return platform.release()
    except Exception:
        return "unknown"

def get_python_env() -> str:
    """Get Python environment info."""
    return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

# =============================================================================
# Power Monitor Wrapper
# =============================================================================

class DronePowerMonitor:
    """Wrapper for drone-side power monitoring (INA219 or RPi5)."""
    
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self._monitor = None
        self._available = False
        self._sensor_type = "none"
        self._samples: List[Dict[str, float]] = []
        self._sampling = False
        self._sample_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        
        # Try INA219 first, then RPi5 backends
        try:
            from core.power_monitor import create_power_monitor
            self._monitor = create_power_monitor(output_dir=output_dir)
            self._available = True
            self._sensor_type = "ina219"  # or detect actual type
            log(f"[POWER] Monitor initialized: {self._sensor_type}")
        except Exception as e:
            log(f"[POWER] Not available: {e}")
    
    @property
    def available(self) -> bool:
        return self._available
    
    @property
    def sensor_type(self) -> str:
        return self._sensor_type
    
    def start_sampling(self):
        """Start background power sampling."""
        if not self._available:
            return
        
        self._samples = []
        self._stop_event.clear()
        self._sampling = True
        
        self._sample_thread = threading.Thread(target=self._sample_loop, daemon=True)
        self._sample_thread.start()
    
    def _sample_loop(self):
        """Background sampling at ~100Hz."""
        while self._sampling and not self._stop_event.is_set():
            try:
                if self._monitor and hasattr(self._monitor, 'read_metrics'):
                    reading = self._monitor.read_metrics()
                    if reading:
                        self._samples.append({
                            "ts": time.time_ns(),
                            "voltage_v": reading.get("bus_v", 0),
                            "current_a": reading.get("current_mA", 0) / 1000.0,
                            "power_w": reading.get("power_mW", 0) / 1000.0,
                        })
            except Exception:
                pass
            time.sleep(0.01)  # 100Hz
    
    def stop_sampling(self) -> List[Dict[str, float]]:
        """Stop sampling and return samples."""
        self._sampling = False
        self._stop_event.set()
        if self._sample_thread:
            self._sample_thread.join(timeout=2.0)
        return self._samples.copy()
    
    def compute_stats(self, samples: List[Dict], duration_s: float) -> Dict[str, float]:
        """Compute power statistics."""
        if not samples or duration_s <= 0:
            return {
                "voltage_avg_v": 0, "current_avg_a": 0,
                "power_avg_w": 0, "power_peak_w": 0,
                "energy_total_j": 0, "sample_hz": 0
            }
        
        voltages = [s.get("voltage_v", 0) for s in samples]
        currents = [s.get("current_a", 0) for s in samples]
        powers = [s.get("power_w", 0) for s in samples]
        
        avg_power = statistics.mean(powers) if powers else 0
        return {
            "voltage_avg_v": statistics.mean(voltages) if voltages else 0,
            "current_avg_a": statistics.mean(currents) if currents else 0,
            "power_avg_w": avg_power,
            "power_peak_w": max(powers) if powers else 0,
            "energy_total_j": avg_power * duration_s,
            "sample_hz": len(samples) / duration_s if duration_s > 0 else 0,
        }

# =============================================================================
# System Metrics Collector
# =============================================================================

class SystemMetricsCollector:
    """Collects system metrics (CPU, memory, temperature, load)."""
    
    def __init__(self):
        self._psutil = None
        self._cpu_samples: List[float] = []
        self._sampling = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        
        try:
            import psutil
            self._psutil = psutil
        except ImportError:
            log("[SYSTEM] psutil not available")
    
    def start_sampling(self):
        """Start CPU sampling."""
        self._cpu_samples = []
        self._stop_event.clear()
        self._sampling = True
        
        if self._psutil:
            self._thread = threading.Thread(target=self._sample_loop, daemon=True)
            self._thread.start()
    
    def _sample_loop(self):
        while self._sampling and not self._stop_event.is_set():
            if self._psutil:
                cpu = self._psutil.cpu_percent(interval=0.5)
                self._cpu_samples.append(cpu)
    
    def stop_sampling(self) -> SystemResourcesDrone:
        """Stop sampling and return metrics."""
        self._sampling = False
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)
        
        metrics = SystemResourcesDrone()
        
        # CPU stats
        if self._cpu_samples:
            metrics.cpu_usage_avg_percent = statistics.mean(self._cpu_samples)
            metrics.cpu_usage_peak_percent = max(self._cpu_samples)
        
        # Memory
        if self._psutil:
            proc = self._psutil.Process()
            mem = proc.memory_info()
            metrics.memory_rss_mb = mem.rss / (1024 * 1024)
            metrics.memory_vms_mb = mem.vms / (1024 * 1024)
            metrics.thread_count = proc.num_threads()
        
        # Temperature (RPi specific)
        try:
            thermal_path = "/sys/class/thermal/thermal_zone0/temp"
            if os.path.exists(thermal_path):
                with open(thermal_path) as f:
                    metrics.temperature_c = int(f.read().strip()) / 1000.0
        except Exception:
            pass
        
        # Load average (Linux)
        try:
            load = os.getloadavg()
            metrics.load_avg_1m = load[0]
            metrics.load_avg_5m = load[1]
            metrics.load_avg_15m = load[2]
        except (OSError, AttributeError):
            pass
        
        return metrics

# =============================================================================
# MAVLink Metrics Collector (pymavlink)
# =============================================================================

class MavLinkMetricsCollector:
    """Collects MAVLink application-layer metrics via pymavlink."""
    
    def __init__(self, listen_port: int = MAVLINK_LISTEN_PORT):
        self.listen_port = listen_port
        self._conn = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        
        # Counters
        self._msg_counts: Dict[str, int] = {}
        self._total_rx = 0
        self._total_tx = 0
        self._seq_gaps = 0
        self._last_seq: Dict[int, int] = {}  # sysid -> last_seq
        self._heartbeat_times: List[float] = []
        self._last_heartbeat = 0.0
        self._latencies: List[float] = []
        
        # FC telemetry
        self._fc_mode = ""
        self._fc_armed = False
        self._fc_battery_v = 0.0
        self._fc_battery_a = 0.0
        self._fc_battery_pct = 0.0
        
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
        msg_type = msg.get_type()
        
        with self._lock:
            self._total_rx += 1
            self._msg_counts[msg_type] = self._msg_counts.get(msg_type, 0) + 1
            
            # Check sequence gaps
            if hasattr(msg, '_header'):
                sysid = msg._header.srcSystem
                seq = msg._header.seq
                if sysid in self._last_seq:
                    expected = (self._last_seq[sysid] + 1) % 256
                    if seq != expected:
                        self._seq_gaps += 1
                self._last_seq[sysid] = seq
            
            # Heartbeat tracking
            if msg_type == "HEARTBEAT":
                now = time.time()
                if self._last_heartbeat > 0:
                    interval = (now - self._last_heartbeat) * 1000
                    self._heartbeat_times.append(interval)
                self._last_heartbeat = now
                
                # Decode mode/armed
                if hasattr(msg, 'custom_mode'):
                    self._fc_mode = str(msg.custom_mode)
                if hasattr(msg, 'base_mode'):
                    self._fc_armed = bool(msg.base_mode & 0x80)
            
            # Battery info
            if msg_type == "SYS_STATUS":
                if hasattr(msg, 'voltage_battery'):
                    self._fc_battery_v = msg.voltage_battery / 1000.0
                if hasattr(msg, 'current_battery'):
                    self._fc_battery_a = msg.current_battery / 100.0
                if hasattr(msg, 'battery_remaining'):
                    self._fc_battery_pct = msg.battery_remaining
    
    def stop(self) -> Tuple[MavProxyDroneMetrics, MavLinkIntegrityMetrics, FlightControllerTelemetry]:
        """Stop and return collected metrics."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        
        with self._lock:
            mav_metrics = MavProxyDroneMetrics()
            mav_metrics.mavproxy_drone_total_msgs_received = self._total_rx
            mav_metrics.mavproxy_drone_msg_type_counts = self._msg_counts.copy()
            mav_metrics.mavproxy_drone_seq_gap_count = self._seq_gaps
            
            if self._heartbeat_times:
                mav_metrics.mavproxy_drone_heartbeat_interval_ms = statistics.mean(self._heartbeat_times)
            
            integrity = MavLinkIntegrityMetrics()
            integrity.mavlink_out_of_order_count = self._seq_gaps
            
            fc = FlightControllerTelemetry()
            fc.fc_mode = self._fc_mode
            fc.fc_armed_state = self._fc_armed
            fc.fc_battery_voltage_v = self._fc_battery_v
            fc.fc_battery_current_a = self._fc_battery_a
            fc.fc_battery_remaining_percent = self._fc_battery_pct
            
            return mav_metrics, integrity, fc

# =============================================================================
# UDP Echo Server
# =============================================================================

class UdpEchoServer:
    """Echoes UDP packets back through the tunnel."""
    
    def __init__(self, bind_host: str, rx_port: int, tx_port: int):
        self.bind_host = bind_host
        self.rx_port = rx_port
        self.tx_port = tx_port
        self.rx_sock: Optional[socket.socket] = None
        self.tx_sock: Optional[socket.socket] = None
        self.running = False
        self.thread: Optional[threading.Thread] = None
        
        self._lock = threading.Lock()
        self._rx_count = 0
        self._tx_count = 0
        self._rx_bytes = 0
        self._tx_bytes = 0
        self._latencies: List[float] = []
    
    def start(self):
        if self.running:
            return
        
        self.rx_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.rx_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.rx_sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 * 1024 * 1024)
        self.rx_sock.bind((self.bind_host, self.rx_port))
        self.rx_sock.settimeout(1.0)
        
        self.tx_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.tx_sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4 * 1024 * 1024)
        
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()
        log(f"Echo server on {self.bind_host}:{self.rx_port}")
    
    def _loop(self):
        while self.running:
            try:
                data, addr = self.rx_sock.recvfrom(65535)
                recv_ts = time.time_ns()
                
                with self._lock:
                    self._rx_count += 1
                    self._rx_bytes += len(data)
                
                # Try to extract timestamp for latency
                try:
                    pkt = json.loads(data.decode("utf-8"))
                    if "ts_ns" in pkt:
                        latency_ms = (recv_ts - pkt["ts_ns"]) / 1_000_000
                        with self._lock:
                            self._latencies.append(latency_ms)
                except Exception:
                    pass
                
                # Echo back
                self.tx_sock.sendto(data, (self.bind_host, self.tx_port))
                with self._lock:
                    self._tx_count += 1
                    self._tx_bytes += len(data)
                    
            except socket.timeout:
                continue
            except Exception:
                if self.running:
                    pass
    
    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "rx_count": self._rx_count,
                "tx_count": self._tx_count,
                "rx_bytes": self._rx_bytes,
                "tx_bytes": self._tx_bytes,
                "latencies": self._latencies.copy(),
            }
    
    def reset_stats(self):
        with self._lock:
            self._rx_count = 0
            self._tx_count = 0
            self._rx_bytes = 0
            self._tx_bytes = 0
            self._latencies = []
    
    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)
        if self.rx_sock:
            self.rx_sock.close()
        if self.tx_sock:
            self.tx_sock.close()

# =============================================================================
# GCS Control Client
# =============================================================================

def send_gcs_command(cmd: str, timeout: float = 30.0, **params) -> dict:
    """Send command to GCS benchmark server."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((GCS_HOST, GCS_CONTROL_PORT))
        
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

def wait_for_gcs(timeout: float = 60.0) -> bool:
    """Wait for GCS control server to be ready."""
    start = time.time()
    while time.time() - start < timeout:
        result = send_gcs_command("ping", timeout=5.0)
        if result.get("status") == "ok":
            return True
        time.sleep(1.0)
    return False

# =============================================================================
# Drone Proxy Manager
# =============================================================================

class DroneProxyManager:
    """Manages drone proxy subprocess."""
    
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
        peer_pubkey = secret_dir / "gcs_signing.pub"
        
        if not peer_pubkey.exists():
            log(f"Missing key: {peer_pubkey}")
            return False
        
        cmd = [
            sys.executable, "-m", "core.run_proxy", "drone",
            "--suite", suite_name,
            "--peer-pubkey-file", str(peer_pubkey),
            "--quiet",
            "--status-file", str(self.logs_dir / "drone_status.json")
        ]
        
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        log_path = self.logs_dir / f"drone_proxy_{suite_name}_{timestamp}.log"
        self._log_handle = open(log_path, "w", encoding="utf-8")
        
        self.managed_proc = ManagedProcess(
            cmd=cmd,
            name=f"drone-proxy-{suite_name}",
            stdout=self._log_handle,
            stderr=subprocess.STDOUT
        )
        
        if self.managed_proc.start():
            self.current_suite = suite_name
            time.sleep(2.0)
            if not self.managed_proc.is_running():
                log(f"Proxy exited early for {suite_name}")
                return False
            log(f"Drone proxy started for {suite_name}")
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
    
    def read_status(self) -> Dict[str, Any]:
        """Read proxy status file for metrics."""
        status_file = self.logs_dir / "drone_status.json"
        try:
            if status_file.exists():
                with open(status_file) as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

# =============================================================================
# Suite Discovery
# =============================================================================

def get_available_suites() -> List[Dict[str, Any]]:
    """Get all suites that have keys available."""
    all_suites = list_suites()
    available = []
    
    for name, config in sorted(all_suites.items()):
        suite_dir = SECRETS_DIR / name
        gcs_pub = suite_dir / "gcs_signing.pub"
        
        if gcs_pub.exists():
            available.append({"name": name, **config})
    
    return available

# =============================================================================
# Benchmark Controller
# =============================================================================

class DroneBenchmarkController:
    """Main benchmark controller - cycles through all suites."""
    
    def __init__(self, logs_dir: Path, run_id: str, cycle_time: float = DEFAULT_CYCLE_TIME, max_suites: int = 0):
        self.logs_dir = logs_dir
        self.run_id = run_id
        self.cycle_time = cycle_time
        self.max_suites = max_suites
        
        # Components
        self.proxy = DroneProxyManager(logs_dir)
        self.echo_server = UdpEchoServer("127.0.0.1", DRONE_PLAIN_RX_PORT, DRONE_PLAIN_TX_PORT)
        self.power_monitor = DronePowerMonitor(logs_dir)
        self.system_monitor = SystemMetricsCollector()
        self.mavlink_monitor = MavLinkMetricsCollector()
        
        # Results
        self.results: List[ComprehensiveSuiteMetrics] = []
        self.output_file = logs_dir / f"benchmark_{run_id}.jsonl"
        
        # Environment
        self.git_commit, self.git_dirty = get_git_info()
        self.liboqs_version = get_liboqs_version()
        self.kernel_version = get_kernel_version()
        
        self.running = True
    
    def run(self):
        """Run the complete benchmark."""
        log("=" * 60)
        log("OPERATION CHRONOS v2: Comprehensive E2E Benchmark")
        log("=" * 60)
        
        # 1. Wait for GCS
        log("Waiting for GCS control server...")
        if not wait_for_gcs(timeout=120.0):
            log("ERROR: GCS not available")
            return
        log("GCS ready!")
        
        # 2. Get GCS info
        gcs_info = send_gcs_command("get_info")
        gcs_hostname = gcs_info.get("hostname", "unknown")
        gcs_ip = gcs_info.get("ip", GCS_HOST)
        gcs_kernel = gcs_info.get("kernel_version", "unknown")
        gcs_python = gcs_info.get("python_env", "unknown")
        
        # 3. Discover suites
        suites = get_available_suites()
        if self.max_suites > 0:
            suites = suites[:self.max_suites]
        
        log(f"Suites to benchmark: {len(suites)}")
        log(f"Cycle time: {self.cycle_time}s")
        log(f"Output: {self.output_file}")
        
        # 4. Start echo server
        self.echo_server.start()
        
        # 5. Start MAVLink monitor
        self.mavlink_monitor.start()
        
        # 6. Benchmark loop
        run_start_wall = datetime.now(timezone.utc).isoformat()
        run_start_mono = time.monotonic()
        
        for idx, suite_info in enumerate(suites):
            if not self.running:
                break
            
            suite_name = suite_info["name"]
            log(f"\n[{idx+1}/{len(suites)}] Benchmarking: {suite_name}")
            
            try:
                result = self._benchmark_suite(
                    suite_info=suite_info,
                    suite_index=idx,
                    gcs_hostname=gcs_hostname,
                    gcs_ip=gcs_ip,
                    gcs_kernel=gcs_kernel,
                    gcs_python=gcs_python,
                    run_start_wall=run_start_wall,
                )
                self.results.append(result)
                
                # Write to JSONL immediately
                with open(self.output_file, "a") as f:
                    f.write(result.to_json() + "\n")
                
            except Exception as e:
                log(f"ERROR benchmarking {suite_name}: {e}")
                import traceback
                traceback.print_exc()
            
            # Inter-suite delay
            if idx < len(suites) - 1:
                log("Inter-suite delay (2s)...")
                time.sleep(2.0)
        
        run_end_wall = datetime.now(timezone.utc).isoformat()
        run_end_mono = time.monotonic()
        
        # 7. Cleanup
        self.echo_server.stop()
        self.proxy.stop()
        
        # 8. Final summary
        log("\n" + "=" * 60)
        log("BENCHMARK COMPLETE")
        log(f"Suites tested: {len(self.results)}")
        log(f"Duration: {run_end_mono - run_start_mono:.1f}s")
        log(f"Output: {self.output_file}")
        log("=" * 60)
    
    def _benchmark_suite(
        self,
        suite_info: Dict[str, Any],
        suite_index: int,
        gcs_hostname: str,
        gcs_ip: str,
        gcs_kernel: str,
        gcs_python: str,
        run_start_wall: str,
    ) -> ComprehensiveSuiteMetrics:
        """Benchmark a single suite."""
        
        suite_name = suite_info["name"]
        metrics = ComprehensiveSuiteMetrics()
        
        # ========== A. Run & Context ==========
        metrics.run_context.run_id = self.run_id
        metrics.run_context.suite_id = suite_name
        metrics.run_context.suite_index = suite_index
        metrics.run_context.git_commit_hash = self.git_commit
        metrics.run_context.git_dirty_flag = self.git_dirty
        metrics.run_context.drone_hostname = socket.gethostname()
        metrics.run_context.gcs_hostname = gcs_hostname
        metrics.run_context.drone_ip = DRONE_HOST
        metrics.run_context.gcs_ip = gcs_ip
        metrics.run_context.python_env_drone = get_python_env()
        metrics.run_context.python_env_gcs = gcs_python
        metrics.run_context.liboqs_version = self.liboqs_version
        metrics.run_context.kernel_version_drone = self.kernel_version
        metrics.run_context.kernel_version_gcs = gcs_kernel
        metrics.run_context.run_start_time_wall = run_start_wall
        
        # ========== B. Suite Crypto Identity ==========
        metrics.crypto_identity.kem_algorithm = suite_info.get("kem_name", "")
        metrics.crypto_identity.sig_algorithm = suite_info.get("sig_name", "")
        metrics.crypto_identity.aead_algorithm = suite_info.get("aead", "")
        metrics.crypto_identity.suite_security_level = suite_info.get("nist_level", "")
        metrics.crypto_identity.suite_order_index = suite_index
        
        # Parse KEM/SIG families
        kem_name = suite_info.get("kem_name", "")
        if "ML-KEM" in kem_name:
            metrics.crypto_identity.kem_family = "ML-KEM"
        elif "Classic-McEliece" in kem_name:
            metrics.crypto_identity.kem_family = "Classic-McEliece"
        elif "HQC" in kem_name:
            metrics.crypto_identity.kem_family = "HQC"
        
        sig_name = suite_info.get("sig_name", "")
        if "ML-DSA" in sig_name:
            metrics.crypto_identity.sig_family = "ML-DSA"
        elif "Falcon" in sig_name:
            metrics.crypto_identity.sig_family = "Falcon"
        elif "SPHINCS" in sig_name:
            metrics.crypto_identity.sig_family = "SPHINCS+"
        
        # ========== C. Suite Lifecycle Timeline ==========
        suite_selected_time = time.time()
        metrics.lifecycle.suite_selected_time = suite_selected_time
        
        # Start power monitoring
        self.power_monitor.start_sampling()
        self.system_monitor.start_sampling()
        self.echo_server.reset_stats()
        
        # ========== D. Handshake ==========
        handshake_start_drone = time.time()
        metrics.handshake.handshake_start_time_drone = handshake_start_drone
        
        # Tell GCS to prepare and start
        resp = send_gcs_command("prepare_rekey")
        if resp.get("status") != "ok":
            log(f"WARN: GCS prepare_rekey failed: {resp}")
        
        resp = send_gcs_command("start_proxy", suite=suite_name)
        if resp.get("status") != "ok":
            log(f"ERROR: GCS start_proxy failed: {resp}")
            metrics.handshake.handshake_success = False
            metrics.handshake.handshake_failure_reason = str(resp.get("message", "gcs_start_failed"))
            self.power_monitor.stop_sampling()
            self.system_monitor.stop_sampling()
            return metrics
        
        metrics.handshake.handshake_start_time_gcs = resp.get("handshake_start_time", 0)
        
        # Start local proxy
        if not self.proxy.start(suite_name):
            log(f"ERROR: Local proxy start failed for {suite_name}")
            metrics.handshake.handshake_success = False
            metrics.handshake.handshake_failure_reason = "drone_proxy_start_failed"
            self.power_monitor.stop_sampling()
            self.system_monitor.stop_sampling()
            return metrics
        
        handshake_end_drone = time.time()
        metrics.handshake.handshake_end_time_drone = handshake_end_drone
        metrics.handshake.handshake_total_duration_ms = (handshake_end_drone - handshake_start_drone) * 1000
        metrics.handshake.handshake_success = True
        
        metrics.lifecycle.suite_activated_time = handshake_end_drone
        
        # ========== Traffic Phase ==========
        traffic_start = time.time()
        metrics.lifecycle.suite_traffic_start_time = traffic_start
        
        # Tell GCS to start traffic
        resp = send_gcs_command("start_traffic", duration=self.cycle_time)
        
        # Wait for traffic duration
        time.sleep(self.cycle_time)
        
        traffic_end = time.time()
        metrics.lifecycle.suite_traffic_end_time = traffic_end
        
        # ========== E. Crypto Primitive Breakdown (from proxy status) ==========
        proxy_status = self.proxy.read_status()
        handshake_metrics = proxy_status.get("handshake_metrics", {})
        
        metrics.crypto_primitives.kem_keygen_time_ms = handshake_metrics.get("kem_keygen_avg_ms", 0)
        metrics.crypto_primitives.kem_encapsulation_time_ms = handshake_metrics.get("kem_encaps_avg_ms", 0)
        metrics.crypto_primitives.kem_decapsulation_time_ms = handshake_metrics.get("kem_decaps_avg_ms", 0)
        metrics.crypto_primitives.signature_sign_time_ms = handshake_metrics.get("sig_sign_avg_ms", 0)
        metrics.crypto_primitives.signature_verify_time_ms = handshake_metrics.get("sig_verify_avg_ms", 0)
        metrics.crypto_primitives.pub_key_size_bytes = handshake_metrics.get("pub_key_size_bytes", 0)
        metrics.crypto_primitives.ciphertext_size_bytes = handshake_metrics.get("ciphertext_size_bytes", 0)
        metrics.crypto_primitives.sig_size_bytes = handshake_metrics.get("sig_size_bytes", 0)
        
        # ========== G. Data Plane ==========
        echo_stats = self.echo_server.get_stats()
        metrics.data_plane.packets_received = echo_stats["rx_count"]
        metrics.data_plane.packets_sent = echo_stats["tx_count"]
        metrics.data_plane.bytes_received = echo_stats["rx_bytes"]
        metrics.data_plane.bytes_sent = echo_stats["tx_bytes"]
        
        if echo_stats["tx_count"] > 0:
            metrics.data_plane.packet_delivery_ratio = echo_stats["rx_count"] / max(1, echo_stats["tx_count"])
        
        # ========== H. Latency & Jitter ==========
        latencies = echo_stats.get("latencies", [])
        if latencies:
            metrics.latency_jitter.one_way_latency_avg_ms = statistics.mean(latencies)
            metrics.latency_jitter.one_way_latency_p50_ms = statistics.median(latencies)
            sorted_lat = sorted(latencies)
            p95_idx = int(len(sorted_lat) * 0.95)
            metrics.latency_jitter.one_way_latency_p95_ms = sorted_lat[p95_idx] if p95_idx < len(sorted_lat) else sorted_lat[-1] if sorted_lat else 0
            metrics.latency_jitter.one_way_latency_max_ms = max(latencies)
            
            # Jitter (inter-arrival variance)
            if len(latencies) > 1:
                diffs = [abs(latencies[i] - latencies[i-1]) for i in range(1, len(latencies))]
                metrics.latency_jitter.jitter_avg_ms = statistics.mean(diffs)
        
        # ========== Stop Suite ==========
        suite_deactivated = time.time()
        metrics.lifecycle.suite_deactivated_time = suite_deactivated
        metrics.lifecycle.suite_total_duration_ms = (suite_deactivated - suite_selected_time) * 1000
        metrics.lifecycle.suite_active_duration_ms = (traffic_end - handshake_end_drone) * 1000
        
        # Stop proxy
        self.proxy.stop()
        
        # Tell GCS to stop
        gcs_resp = send_gcs_command("stop_suite")
        
        # ========== I/J. MAVProxy Metrics ==========
        mav_drone, mav_integrity, fc_telem = self.mavlink_monitor.stop()
        metrics.mavproxy_drone = mav_drone
        metrics.mavlink_integrity = mav_integrity
        metrics.fc_telemetry = fc_telem
        
        # GCS MAVLink validation metrics from response (POLICY REALIGNMENT: pruned set)
        gcs_mav = gcs_resp.get("mavlink_validation", {})
        metrics.mavproxy_gcs.mavproxy_gcs_total_msgs_received = gcs_mav.get("total_msgs_received", 0)
        metrics.mavproxy_gcs.mavproxy_gcs_seq_gap_count = gcs_mav.get("seq_gap_count", 0)
        # NOTE: msg_type_counts, heartbeat_interval removed per policy realignment
        
        # Restart MAVLink monitor for next suite
        self.mavlink_monitor = MavLinkMetricsCollector()
        self.mavlink_monitor.start()
        
        # ========== M. Control Plane ==========
        metrics.control_plane.scheduler_tick_interval_ms = self.cycle_time * 1000
        metrics.control_plane.policy_name = "deterministic_rotation"
        metrics.control_plane.policy_suite_index = suite_index
        metrics.control_plane.policy_total_suites = len(get_available_suites())
        
        # ========== N. System Resources Drone ==========
        metrics.system_drone = self.system_monitor.stop_sampling()
        
        # ========== O. System Resources GCS (from GCS response) ==========
        metrics.system_gcs.cpu_usage_avg_percent = gcs_metrics.get("cpu_avg_percent", 0)
        metrics.system_gcs.cpu_usage_peak_percent = gcs_metrics.get("cpu_peak_percent", 0)
        metrics.system_gcs.memory_rss_mb = gcs_metrics.get("memory_rss_mb", 0)
        
        # ========== P. Power & Energy ==========
        power_samples = self.power_monitor.stop_sampling()
        traffic_duration = traffic_end - traffic_start
        power_stats = self.power_monitor.compute_stats(power_samples, traffic_duration)
        
        metrics.power_energy.power_sensor_type = self.power_monitor.sensor_type
        metrics.power_energy.power_sampling_rate_hz = power_stats["sample_hz"]
        metrics.power_energy.voltage_avg_v = power_stats["voltage_avg_v"]
        metrics.power_energy.current_avg_a = power_stats["current_avg_a"]
        metrics.power_energy.power_avg_w = power_stats["power_avg_w"]
        metrics.power_energy.power_peak_w = power_stats["power_peak_w"]
        metrics.power_energy.energy_total_j = power_stats["energy_total_j"]
        
        if metrics.handshake.handshake_total_duration_ms > 0:
            handshake_s = metrics.handshake.handshake_total_duration_ms / 1000.0
            metrics.power_energy.energy_per_handshake_j = power_stats["power_avg_w"] * handshake_s
        
        if traffic_duration > 0:
            metrics.power_energy.energy_per_second_j = power_stats["energy_total_j"] / traffic_duration
        
        # ========== Q. Observability ==========
        metrics.observability.log_sample_count = len(power_samples)
        metrics.observability.metrics_sampling_rate_hz = power_stats["sample_hz"]
        metrics.observability.collection_start_time = suite_selected_time
        metrics.observability.collection_end_time = suite_deactivated
        metrics.observability.collection_duration_ms = (suite_deactivated - suite_selected_time) * 1000
        
        # ========== R. Validation ==========
        metrics.validation.collected_samples = echo_stats["rx_count"]
        metrics.validation.success_rate_percent = 100.0 if metrics.handshake.handshake_success else 0.0
        metrics.validation.benchmark_pass_fail = "PASS" if metrics.handshake.handshake_success else "FAIL"
        
        log(f"  ✅ {suite_name}: {metrics.handshake.handshake_total_duration_ms:.1f}ms handshake, "
            f"{echo_stats['rx_count']} pkts, {power_stats['power_avg_w']:.2f}W avg")
        
        return metrics
    
    def stop(self):
        """Stop the benchmark."""
        self.running = False
        self.proxy.stop()
        self.echo_server.stop()

# =============================================================================
# Main Entry Point
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Drone Benchmark Scheduler - Operation Chronos v2")
    parser.add_argument("--cycle-time", type=float, default=DEFAULT_CYCLE_TIME,
                        help=f"Seconds per suite (default: {DEFAULT_CYCLE_TIME})")
    parser.add_argument("--max-suites", type=int, default=0,
                        help="Max suites to test (0=all)")
    parser.add_argument("--run-id", type=str, default=None,
                        help="Run ID (default: auto-generated)")
    args = parser.parse_args()
    
    # Generate run ID
    run_id = args.run_id or f"bench_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    
    # Create logs directory
    run_logs_dir = LOGS_DIR / run_id
    run_logs_dir.mkdir(parents=True, exist_ok=True)
    
    # Run benchmark
    controller = DroneBenchmarkController(
        logs_dir=run_logs_dir,
        run_id=run_id,
        cycle_time=args.cycle_time,
        max_suites=args.max_suites,
    )
    
    # Handle signals
    def signal_handler(sig, frame):
        log("Interrupt received, stopping...")
        controller.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        controller.run()
    except KeyboardInterrupt:
        log("Stopping...")
        controller.stop()

if __name__ == "__main__":
    main()
