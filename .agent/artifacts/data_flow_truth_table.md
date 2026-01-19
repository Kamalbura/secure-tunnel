# Data Flow Truth Table

**Phase:** X - Forensic Reality Check
**Date:** 2026-01-19
**Evidence Type:** JSONL Provenance + Code Path Analysis

## 1. Metric Categories with Source Verification

| Category | Source Signal | Code Path | JSONL Value | Validity |
|:---|:---|:---|:---|:---|
| **A. run_context** | Python runtime | `sdrone_bench.py` L792-806 | ✅ Populated | **VALID** |
| **B. crypto_identity** | `core/suites.py` config | `sdrone_bench.py` L808-830 | ✅ Populated | **VALID** |
| **C. lifecycle** | `time.time()` | `sdrone_bench.py` L833-934 | ✅ Populated | **VALID** |
| **D. handshake** | `time.time()` delta | `sdrone_bench.py` L841-873 | ✅ Populated | **VALID** |
| **E. crypto_primitives** | C-proxy status file | `sdrone_bench.py` L889-906 | `-1` (Pruned) | **MARKED INVALID** |
| **F. rekey** | Scheduler state | `sdrone_bench.py` (dormant) | `0` (Idle) | **VALID (Inactive)** |
| **G. data_plane** | `MavLinkMetricsCollector` | `sdrone_bench.py` L907-920 | ✅ Populated | **VALID** |
| **H. latency_jitter** | Heartbeat intervals | `sdrone_bench.py` L924-928 | ✅ Populated | **VALID** |
| **I. mavproxy_drone** | `MavLinkMetricsCollector.stop()` | `sdrone_bench.py` L942-944 | ✅ Populated | **VALID** |
| **J. mavproxy_gcs** | GCS `stop_suite` response | `sdrone_bench.py` L947-951 | ✅ Populated | **VALID** |
| **K. mavlink_integrity** | Sequence gap counter | `MavLinkMetricsCollector` | ✅ Populated | **VALID** |
| **L. fc_telemetry** | MAVLink `SYS_STATUS`, `HEARTBEAT` | `MavLinkMetricsCollector` L416-423 | ✅ Populated | **VALID** |
| **M. control_plane** | Scheduler config | `sdrone_bench.py` L957-961 | ✅ Populated | **VALID** |
| **N. system_drone** | `psutil` (CPU, Mem, Temp) | `SystemMetricsCollector` | ✅ Populated | **VALID** |
| **O. system_gcs** | GCS response | `sdrone_bench.py` L967-970 | `0` (Policy) | **VALID (Disabled)** |
| **P. power_energy** | INA219 (Hardware) | `DronePowerMonitor` L973-990 | ✅ Populated | **VALID** |
| **Q. observability** | Internal counters | `sdrone_bench.py` L992-997 | ✅ Populated | **VALID** |
| **R. validation** | Handshake result | `sdrone_bench.py` L999-1002 | ✅ Populated | **VALID** |

## 2. Source Signal Deep Verification

### G. Data Plane (Critical)

| Field | JSONL Value | Source Evidence |
|:---|:---:|:---|
| `packets_received` | 6174 | `MavLinkMetricsCollector._total_rx` (incremented in `_process_message`) |
| `bytes_received` | 347885 | `MavLinkMetricsCollector._total_bytes` (via `len(msg.get_msgbuf())`) |
| `achieved_throughput_mbps` | 0.278 | Derived: `(bytes * 8) / (duration * 1e6)` |

**Verdict:** ✅ **REAL SIGNAL** - Direct pymavlink introspection.

### P. Power/Energy (Critical)

| Field | JSONL Value | Source Evidence |
|:---|:---:|:---|
| `power_sensor_type` | "ina219" | Hardware detection in `power_monitor.py` |
| `voltage_avg_v` | 4.99 | `INA219.voltage()` over I2C |
| `current_avg_a` | 0.826 | `INA219.current()` over I2C |
| `power_avg_w` | 4.12 | `voltage * current` |
| `energy_total_j` | 41.2 | `power_avg * duration` |

**Verdict:** ✅ **HARDWARE SIGNAL** - INA219 sensor at I2C address 0x40.

### E. Crypto Primitives (Gap)

| Field | JSONL Value | Source Evidence |
|:---|:---:|:---|
| `kem_keygen_time_ms` | -1 | **No C-proxy status file instrumentation.** |
| `sig_sign_time_ms` | -1 | **No C-proxy status file instrumentation.** |

**Verdict:** ❌ **INSTRUMENTATION GAP** - Explicitly marked `-1` to prevent false interpretation.

### L. FC Telemetry (Hardware)

| Field | JSONL Value | Source Evidence |
|:---|:---:|:---|
| `fc_battery_voltage_v` | 3.159 | `SYS_STATUS.voltage_battery / 1000.0` (MAVLink) |
| `fc_battery_current_a` | 3.24 | `SYS_STATUS.current_battery / 100.0` (MAVLink) |
| `fc_mode` | 65536 | `HEARTBEAT.custom_mode` (MAVLink) |

**Verdict:** ✅ **HARDWARE SIGNAL** - Pixhawk 2.4.8 via USB.

---

## 3. Invalid/Stale Metrics

| Metric | Failure Mode | Root Cause |
|:---|:---|:---|
| `crypto_primitives.*` | `-1` | C-proxy does not write timings to status file. |
| `system_gcs.*` | `0` | Policy: GCS resources are non-constrained. |
| `handshake_end_time_gcs` | `0.0` | GCS does not report end time back. |
| `run_end_time_wall` | `""` | Not populated for mid-run suites. |

---

## 4. Summary Validity Matrix

| Category | Hardware? | Protocol? | Calculated? | Valid? |
|:---|:---:|:---:|:---:|:---|
| **Power** | ✅ INA219 | - | - | **YES** |
| **FC Telemetry** | ✅ Pixhawk | ✅ MAVLink | - | **YES** |
| **Data Plane** | - | ✅ pymavlink | ✅ Derived | **YES** |
| **Latency** | - | ✅ pymavlink | ✅ Derived | **YES** |
| **Crypto Primitives** | - | - | - | **NO** |
| **GCS System** | - | - | - | **DISABLED** |
