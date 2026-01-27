#!/usr/bin/env python3
"""
Metrics Collectors - Base and System Collectors
core/metrics_collectors.py

Provides collectors for gathering metrics from various sources:
- System resources (CPU, memory, temperature)
- Power monitoring (INA219, RPi5 PMIC)
- Environment info (git, python, kernel)
- Network statistics

Usage:
    from core.metrics_collectors import SystemCollector, PowerCollector
    
    sys_collector = SystemCollector()
    metrics = sys_collector.collect()
"""

import os
import sys
import time
import json
import socket
import platform
import subprocess
import threading
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from datetime import datetime, timezone

# Try importing optional dependencies
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

# =============================================================================
# BASE COLLECTOR
# =============================================================================

class BaseCollector:
    """Base class for all metric collectors."""
    
    def __init__(self, name: str = "base"):
        self.name = name
        self.is_drone = self._detect_platform() == "linux_arm"
        self.is_gcs = not self.is_drone
        self._last_collect_time = 0.0
        self._collect_count = 0
    
    def _detect_platform(self) -> str:
        """Detect running platform."""
        system = platform.system().lower()
        machine = platform.machine().lower()
        
        if system == "linux" and ("arm" in machine or "aarch" in machine):
            return "linux_arm"
        elif system == "windows":
            return "windows"
        elif system == "linux":
            return "linux_x86"
        return "unknown"
    
    def collect(self) -> Dict[str, Any]:
        """Override in subclass to collect metrics."""
        raise NotImplementedError
    
    def collect_timed(self) -> Tuple[Dict[str, Any], float]:
        """Collect metrics and return with timing."""
        start = time.perf_counter()
        data = self.collect()
        elapsed_ms = (time.perf_counter() - start) * 1000
        self._last_collect_time = elapsed_ms
        self._collect_count += 1
        return data, elapsed_ms


# =============================================================================
# ENVIRONMENT COLLECTOR
# =============================================================================

class EnvironmentCollector(BaseCollector):
    """Collects environment and context information."""
    
    def __init__(self):
        super().__init__("environment")
        self._git_info_cache = None
        self._oqs_version_cache = None
    
    def collect(self) -> Dict[str, Any]:
        """Collect environment metrics."""
        return {
            "hostname": socket.gethostname(),
            "platform": platform.system(),
            "platform_release": platform.release(),
            "platform_version": platform.version(),
            "machine": platform.machine(),
            "python_version": platform.python_version(),
            "python_executable": sys.executable,
            "cwd": os.getcwd(),
            "pid": os.getpid(),
            "kernel_version": self._get_kernel_version(),
            "git_commit": self._get_git_commit(),
            "git_dirty": self._is_git_dirty(),
            "liboqs_version": self._get_oqs_version(),
            "conda_env": os.environ.get("CONDA_DEFAULT_ENV", ""),
            "virtual_env": os.environ.get("VIRTUAL_ENV", ""),
            "timestamp_wall": datetime.now(timezone.utc).isoformat(),
            "timestamp_mono": time.monotonic(),
        }
    
    def _get_kernel_version(self) -> str:
        """Get kernel version."""
        try:
            if platform.system() == "Linux":
                return platform.release()
            elif platform.system() == "Windows":
                return platform.version()
            return platform.release()
        except Exception:
            return ""
    
    def _get_git_commit(self) -> str:
        """Get current git commit hash."""
        if self._git_info_cache is not None:
            return self._git_info_cache.get("commit", "")
        
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                commit = result.stdout.strip()[:12]
                self._git_info_cache = {"commit": commit}
                return commit
        except Exception:
            pass
        return ""
    
    def _is_git_dirty(self) -> bool:
        """Check if git working directory is dirty."""
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True, text=True, timeout=5
            )
            return bool(result.stdout.strip())
        except Exception:
            return False
    
    def _get_oqs_version(self) -> str:
        """Get liboqs version if available."""
        if self._oqs_version_cache is not None:
            return self._oqs_version_cache
        
        try:
            import oqs
            version = getattr(oqs, '__version__', '')
            if not version:
                # Try to get from oqs.oqs
                try:
                    from oqs import oqs as oqs_mod
                    version = getattr(oqs_mod, '__version__', 'unknown')
                except Exception:
                    version = 'installed'
            self._oqs_version_cache = version
            return version
        except ImportError:
            self._oqs_version_cache = "not_installed"
            return "not_installed"
    
    def get_ip_address(self, interface: str = None) -> str:
        """Get IP address."""
        try:
            if interface and HAS_PSUTIL:
                addrs = psutil.net_if_addrs()
                if interface in addrs:
                    for addr in addrs[interface]:
                        if addr.family == socket.AF_INET:
                            return addr.address
            
            # Fallback: create UDP socket to get default route IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0.1)
            try:
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
            except Exception:
                return "127.0.0.1"
            finally:
                s.close()
        except Exception:
            return ""


# =============================================================================
# SYSTEM RESOURCE COLLECTOR
# =============================================================================

class SystemCollector(BaseCollector):
    """Collects system resource metrics (CPU, memory, temperature)."""
    
    def __init__(self):
        super().__init__("system")
        self._cpu_samples: List[float] = []
        self._sample_window = 10  # Keep last N samples
    
    def collect(self) -> Dict[str, Any]:
        """Collect system resource metrics."""
        metrics = {
            "timestamp": time.time(),
            "cpu_percent": None,
            "cpu_freq_mhz": None,
            "memory_rss_mb": None,
            "memory_vms_mb": None,
            "memory_percent": None,
            "thread_count": None,
            "temperature_c": None,
            "load_avg_1m": None,
            "load_avg_5m": None,
            "load_avg_15m": None,
            "uptime_s": None,
        }
        
        if HAS_PSUTIL:
            try:
                try:
                    metrics["cpu_percent"] = psutil.cpu_percent(interval=None)
                    self._cpu_samples.append(metrics["cpu_percent"])
                    if len(self._cpu_samples) > self._sample_window:
                        self._cpu_samples.pop(0)
                except Exception as e:
                    metrics["cpu_error"] = str(e)

                try:
                    freq = psutil.cpu_freq()
                    if freq:
                        metrics["cpu_freq_mhz"] = freq.current
                except Exception as e:
                    metrics["cpu_freq_error"] = str(e)

                proc = psutil.Process()

                try:
                    mem_info = proc.memory_info()
                    metrics["memory_rss_mb"] = mem_info.rss / (1024 * 1024)
                    metrics["memory_vms_mb"] = mem_info.vms / (1024 * 1024)
                except Exception as e:
                    metrics["memory_info_error"] = str(e)

                try:
                    metrics["memory_percent"] = proc.memory_percent()
                except Exception as e:
                    metrics["memory_percent_error"] = str(e)

                try:
                    metrics["thread_count"] = proc.num_threads()
                except Exception as e:
                    metrics["thread_count_error"] = str(e)

                try:
                    vm = psutil.virtual_memory()
                    metrics["system_memory_percent"] = vm.percent
                    metrics["system_memory_available_mb"] = vm.available / (1024 * 1024)
                except Exception as e:
                    metrics["system_memory_error"] = str(e)

                try:
                    metrics["uptime_s"] = max(0.0, time.time() - psutil.boot_time())
                except Exception as e:
                    metrics["uptime_error"] = str(e)

            except Exception as e:
                metrics["error"] = str(e)
        
        # Linux-specific
        if platform.system() == "Linux":
            try:
                load = os.getloadavg()
                metrics["load_avg_1m"] = load[0]
                metrics["load_avg_5m"] = load[1]
                metrics["load_avg_15m"] = load[2]
            except Exception:
                pass
            
            # Temperature (RPi)
            metrics["temperature_c"] = self._read_temperature()
            metrics["thermal_throttled"] = self._check_throttling()
        
        return metrics
    
    def _read_temperature(self) -> float:
        """Read CPU temperature on Linux."""
        # Try thermal zone
        try:
            with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                return float(f.read().strip()) / 1000.0
        except Exception:
            pass
        
        # Try vcgencmd on RPi
        try:
            result = subprocess.run(
                ["vcgencmd", "measure_temp"],
                capture_output=True, text=True, timeout=2
            )
            if result.returncode == 0:
                # Output: temp=45.0'C
                temp_str = result.stdout.strip()
                return float(temp_str.split("=")[1].replace("'C", ""))
        except Exception:
            pass
        
        return 0.0
    
    def _check_throttling(self) -> bool:
        """Check if RPi is thermally throttled."""
        try:
            result = subprocess.run(
                ["vcgencmd", "get_throttled"],
                capture_output=True, text=True, timeout=2
            )
            if result.returncode == 0:
                # Output: throttled=0x0
                value = result.stdout.strip().split("=")[1]
                return int(value, 16) != 0
        except Exception:
            pass
        return False
    
    def get_cpu_stats(self) -> Dict[str, float]:
        """Get CPU statistics from collected samples."""
        if not self._cpu_samples:
            return {"avg": 0.0, "peak": 0.0, "min": 0.0}
        
        return {
            "avg": sum(self._cpu_samples) / len(self._cpu_samples),
            "peak": max(self._cpu_samples),
            "min": min(self._cpu_samples),
        }


# =============================================================================
# POWER COLLECTOR
# =============================================================================

class PowerCollector(BaseCollector):
    """Collects power and energy metrics from hardware sensors."""
    
    def __init__(self, backend: str = "auto"):
        super().__init__("power")
        self.backend = backend
        self._ina219 = None
        self._ina_busnum: Optional[int] = None
        self._ina_address: int = 0x40
        self._sampling = False
        self._samples: List[Dict[str, float]] = []
        self._sample_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        
        # Detect available backend
        if backend == "auto":
            self.backend = self._detect_backend()
        
        # Initialize INA219 if available
        if self.backend == "ina219":
            self._init_ina219()
    
    def _detect_backend(self) -> str:
        """Detect available power monitoring backend."""
        if platform.system() != "Linux":
            return "none"
        
        # Check for INA219
        try:
            from ina219 import INA219
            # Raspberry Pi stacks vary; explicitly probe common bus numbers.
            bus_candidates = []
            env_bus = os.environ.get("INA219_BUSNUM")
            if env_bus:
                try:
                    bus_candidates.append(int(env_bus))
                except Exception:
                    pass
            bus_candidates.extend([1, 0, 20, 21])

            env_addr = os.environ.get("INA219_ADDRESS")
            addr_candidates = []
            if env_addr:
                try:
                    addr_candidates.append(int(env_addr, 0))
                except Exception:
                    pass
            addr_candidates.extend([0x40])

            for busnum in bus_candidates:
                for addr in addr_candidates:
                    try:
                        ina = INA219(shunt_ohms=0.1, address=addr, busnum=busnum)
                        ina.configure()
                        self._ina_busnum = busnum
                        self._ina_address = addr
                        return "ina219"
                    except Exception:
                        continue
        except Exception:
            pass
        
        # Check for RPi5 PMIC
        if Path("/sys/class/hwmon").exists():
            for hwmon in Path("/sys/class/hwmon").iterdir():
                name_file = hwmon / "name"
                if name_file.exists():
                    try:
                        name = name_file.read_text().strip()
                        if "rpi" in name.lower() or "pmic" in name.lower():
                            return "rpi5_hwmon"
                    except Exception:
                        pass
        
        return "none"
    
    def _init_ina219(self):
        """Initialize INA219 sensor."""
        try:
            from ina219 import INA219, DeviceRangeError
            busnum = self._ina_busnum
            if busnum is None:
                # Fallback to common Pi bus if detection didn't run or failed.
                busnum = 1
            addr = self._ina_address or 0x40
            self._ina219 = INA219(
                shunt_ohms=0.1,
                max_expected_amps=3.0,
                address=addr,
                busnum=busnum,
            )
            self._ina219.configure(
                voltage_range=self._ina219.RANGE_16V,
                gain=self._ina219.GAIN_AUTO,
                bus_adc=self._ina219.ADC_128SAMP,
                shunt_adc=self._ina219.ADC_128SAMP
            )
        except Exception as e:
            self._ina219 = None
            self.backend = "none"
    
    def collect(self) -> Dict[str, Any]:
        """Collect single power reading."""
        metrics = {
            "timestamp": time.time(),
            "backend": self.backend,
            "voltage_v": 0.0,
            "current_a": 0.0,
            "power_w": 0.0,
        }
        
        if self.backend == "ina219" and self._ina219:
            try:
                metrics["voltage_v"] = self._ina219.voltage()
                metrics["current_a"] = self._ina219.current() / 1000.0  # mA to A
                metrics["power_w"] = self._ina219.power() / 1000.0  # mW to W
            except Exception as e:
                metrics["error"] = str(e)
        
        elif self.backend == "rpi5_hwmon":
            metrics.update(self._read_rpi5_hwmon())
        
        return metrics
    
    def _read_rpi5_hwmon(self) -> Dict[str, float]:
        """Read power from RPi5 hwmon."""
        result = {"voltage_v": 0.0, "current_a": 0.0, "power_w": 0.0}
        
        try:
            hwmon_base = Path("/sys/class/hwmon")
            for hwmon in hwmon_base.iterdir():
                name_file = hwmon / "name"
                if name_file.exists():
                    name = name_file.read_text().strip()
                    if "rpi" in name.lower():
                        # Read voltage (in1_input is in mV)
                        volt_file = hwmon / "in1_input"
                        if volt_file.exists():
                            result["voltage_v"] = float(volt_file.read_text()) / 1000.0
                        
                        # Read current (curr1_input is in mA)
                        curr_file = hwmon / "curr1_input"
                        if curr_file.exists():
                            result["current_a"] = float(curr_file.read_text()) / 1000.0
                        
                        result["power_w"] = result["voltage_v"] * result["current_a"]
                        break
        except Exception:
            pass
        
        return result
    
    def start_sampling(self, rate_hz: float = 100.0):
        """Start continuous power sampling in background thread."""
        if self._sampling:
            return
        
        self._sampling = True
        self._samples = []
        self._stop_event.clear()
        
        interval = 1.0 / rate_hz
        
        def sample_loop():
            while not self._stop_event.is_set():
                sample = self.collect()
                sample["mono_time"] = time.monotonic()
                self._samples.append(sample)
                time.sleep(interval)
        
        self._sample_thread = threading.Thread(target=sample_loop, daemon=True)
        self._sample_thread.start()
    
    def stop_sampling(self) -> List[Dict[str, float]]:
        """Stop sampling and return collected samples."""
        if not self._sampling:
            return []
        
        self._stop_event.set()
        if self._sample_thread:
            self._sample_thread.join(timeout=1.0)
        
        self._sampling = False
        samples = self._samples.copy()
        self._samples = []
        return samples
    
    def get_energy_stats(self, samples: List[Dict[str, float]] = None) -> Dict[str, float]:
        """Calculate energy statistics from samples."""
        if samples is None:
            samples = self._samples
        
        if len(samples) < 2:
            return {
                "energy_total_j": None,
                "power_avg_w": None,
                "power_peak_w": None,
                "duration_s": None,
            }
        
        # Calculate energy using trapezoidal integration
        energy_j = 0.0
        powers = []
        voltages = []
        currents = []
        
        for i in range(1, len(samples)):
            dt = samples[i]["mono_time"] - samples[i-1]["mono_time"]
            p_avg = (samples[i]["power_w"] + samples[i-1]["power_w"]) / 2.0
            energy_j += p_avg * dt
            powers.append(samples[i]["power_w"])
            voltages.append(samples[i].get("voltage_v", 0.0))
            currents.append(samples[i].get("current_a", 0.0))
        
        duration = samples[-1]["mono_time"] - samples[0]["mono_time"]
        
        return {
            "energy_total_j": energy_j,
            "power_avg_w": sum(powers) / len(powers) if powers else 0.0,
            "power_peak_w": max(powers) if powers else 0.0,
            "power_min_w": min(powers) if powers else 0.0,
            "voltage_avg_v": sum(voltages) / len(voltages) if voltages else 0.0,
            "current_avg_a": sum(currents) / len(currents) if currents else 0.0,
            "duration_s": duration,
            "sample_count": len(samples),
        }


# =============================================================================
# NETWORK COLLECTOR
# =============================================================================

class NetworkCollector(BaseCollector):
    """Collects network statistics."""
    
    def __init__(self, interface: str = None):
        super().__init__("network")
        self.interface = interface
        self._last_stats = None
        self._last_time = None
    
    def collect(self) -> Dict[str, Any]:
        """Collect network statistics."""
        metrics = {
            "timestamp": time.time(),
            "rx_bytes": 0,
            "tx_bytes": 0,
            "rx_packets": 0,
            "tx_packets": 0,
            "rx_errors": 0,
            "tx_errors": 0,
            "rx_dropped": 0,
            "tx_dropped": 0,
        }
        
        if not HAS_PSUTIL:
            return metrics
        
        try:
            counters = psutil.net_io_counters(pernic=True)
            
            if self.interface and self.interface in counters:
                stats = counters[self.interface]
            else:
                # Use total
                stats = psutil.net_io_counters()
            
            metrics["rx_bytes"] = stats.bytes_recv
            metrics["tx_bytes"] = stats.bytes_sent
            metrics["rx_packets"] = stats.packets_recv
            metrics["tx_packets"] = stats.packets_sent
            metrics["rx_errors"] = stats.errin
            metrics["tx_errors"] = stats.errout
            metrics["rx_dropped"] = stats.dropin
            metrics["tx_dropped"] = stats.dropout
            
            # Calculate rates if we have previous reading
            if self._last_stats and self._last_time:
                dt = metrics["timestamp"] - self._last_time
                if dt > 0:
                    metrics["rx_rate_mbps"] = (metrics["rx_bytes"] - self._last_stats["rx_bytes"]) * 8 / dt / 1_000_000
                    metrics["tx_rate_mbps"] = (metrics["tx_bytes"] - self._last_stats["tx_bytes"]) * 8 / dt / 1_000_000
            
            self._last_stats = metrics.copy()
            self._last_time = metrics["timestamp"]
            
        except Exception as e:
            metrics["error"] = str(e)
        
        return metrics


# =============================================================================
# LATENCY TRACKER
# =============================================================================

class LatencyTracker:
    """Tracks packet latency using timestamps."""
    
    def __init__(self, max_samples: int = 10000):
        self.max_samples = max_samples
        self._samples: List[float] = []
        self._lock = threading.Lock()
    
    def record(self, latency_ms: float):
        """Record a latency sample."""
        with self._lock:
            self._samples.append(latency_ms)
            if len(self._samples) > self.max_samples:
                self._samples.pop(0)
    
    def get_stats(self) -> Dict[str, float]:
        """Get latency statistics."""
        with self._lock:
            samples = self._samples.copy()
        
        if not samples:
            return {
                "avg_ms": 0.0,
                "p50_ms": 0.0,
                "p95_ms": 0.0,
                "p99_ms": 0.0,
                "max_ms": 0.0,
                "min_ms": 0.0,
                "count": 0,
            }
        
        samples_sorted = sorted(samples)
        n = len(samples_sorted)
        
        return {
            "avg_ms": sum(samples) / n,
            "p50_ms": samples_sorted[int(n * 0.50)],
            "p95_ms": samples_sorted[int(n * 0.95)] if n >= 20 else samples_sorted[-1],
            "p99_ms": samples_sorted[int(n * 0.99)] if n >= 100 else samples_sorted[-1],
            "max_ms": samples_sorted[-1],
            "min_ms": samples_sorted[0],
            "count": n,
        }

    def get_samples(self) -> List[float]:
        """Return a copy of raw latency samples."""
        with self._lock:
            return self._samples.copy()
    
    def clear(self):
        """Clear all samples."""
        with self._lock:
            self._samples.clear()


# =============================================================================
# MAIN - Test collectors
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("METRICS COLLECTORS TEST")
    print("=" * 60)
    
    # Test Environment Collector
    print("\n--- Environment Collector ---")
    env = EnvironmentCollector()
    env_metrics = env.collect()
    for k, v in env_metrics.items():
        print(f"  {k}: {v}")
    
    # Test System Collector
    print("\n--- System Collector ---")
    sys_coll = SystemCollector()
    sys_metrics = sys_coll.collect()
    for k, v in sys_metrics.items():
        print(f"  {k}: {v}")
    
    # Test Power Collector
    print("\n--- Power Collector ---")
    pwr = PowerCollector(backend="auto")
    print(f"  Backend: {pwr.backend}")
    if pwr.backend != "none":
        pwr_metrics = pwr.collect()
        for k, v in pwr_metrics.items():
            print(f"  {k}: {v}")
    else:
        print("  No power sensor available")
    
    # Test Network Collector
    print("\n--- Network Collector ---")
    net = NetworkCollector()
    net_metrics = net.collect()
    for k, v in net_metrics.items():
        print(f"  {k}: {v}")
    
    print("\n" + "=" * 60)
    print("All collectors tested successfully!")
