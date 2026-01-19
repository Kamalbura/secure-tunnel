# SGCS & Drone Execution Report

> Phase 0.7 • Generated: 2026-01-18
> Status: FIXED

---

## Entry Point Comparison

| Component | sdrone_mav.py | sdrone_bench.py |
|-----------|---------------|-----------------|
| Power Monitor | ❌ | ✅ (now fixed) |
| System Metrics | ❌ | ✅ |
| MAVLink Collector | ❌ | ✅ |
| Proxy Manager | `DroneProxyManager` | Same |
| Echo Server | `UdpEchoServer` | Same |
| GCS Control | `send_gcs_command()` | Same |

| Component | sgcs_mav.py | sgcs_bench.py |
|-----------|-------------|---------------|
| MAVProxy GUI | Optional | `GcsMavProxyManager` |
| Traffic Generator | `TrafficGenerator` | Same |
| Proxy Manager | `GcsProxyManager` | Same |
| Control Server | `ControlServer` | `GcsBenchmarkServer` |
| MAVLink Collector | ❌ | `GcsMavLinkCollector` |

---

## Power Monitor Fix Applied

```diff
- def _sample_loop(self):
-     """Background sampling at ~100Hz."""
-     while self._sampling and not self._stop_event.is_set():
-         if self._monitor and hasattr(self._monitor, 'read_metrics'):
-             reading = self._monitor.read_metrics()  # BROKEN
-         time.sleep(0.01)

+ def _sample_loop(self):
+     """Background sampling using core module's iter_samples (1000 Hz)."""
+     for sample in self._monitor.iter_samples():
+         if not self._sampling or self._stop_event.is_set():
+             break
+         self._samples.append({
+             "ts": sample.timestamp_ns,
+             "voltage_v": sample.voltage_v,
+             "current_a": sample.current_a,
+             "power_w": sample.power_w,
+         })
```

---

## Execution Path Verified

### Drone Side

1. `python -m sscheduler.sdrone_bench` starts `DroneBenchmarkController`
2. Initializes: `DronePowerMonitor`, `SystemMetricsCollector`, `MavLinkMetricsCollector`
3. Waits for GCS via `wait_for_gcs()`
4. For each suite: starts power sampling, proxy, traffic, collects metrics
5. Writes JSONL output

### GCS Side

1. `python -m sscheduler.sgcs_bench` starts `GcsBenchmarkServer`
2. Initializes: `GcsProxyManager`, `TrafficGenerator`, `GcsMavLinkCollector`
3. Listens on TCP 48080 for drone commands
4. Handles: `start_proxy`, `start_traffic`, `stop_suite`, `shutdown`
5. Returns traffic stats and validation metrics

---

## Verified Working Components

| Component | Status |
|-----------|--------|
| `DronePowerMonitor` | ✅ Fixed |
| `SystemMetricsCollector` | ✅ psutil-based |
| `MavLinkMetricsCollector` | ✅ pymavlink |
| `DroneProxyManager` | ✅ subprocess |
| `UdpEchoServer` | ✅ echo server |
| `GcsProxyManager` | ✅ subprocess |
| `TrafficGenerator` | ✅ UDP blast |
| `GcsMavLinkCollector` | ✅ validation only |
| `GcsBenchmarkServer` | ✅ TCP control |
