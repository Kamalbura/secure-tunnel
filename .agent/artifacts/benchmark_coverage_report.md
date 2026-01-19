# Benchmark Coverage Report

> Phase 0.5 • Generated: 2026-01-18
> Status: VERIFIED FROM CODE

---

## Metric Category Implementation Status

| Category | Name | Drone | GCS | Status |
|----------|------|-------|-----|--------|
| A | Run Context | ✅ | ✅ | **IMPLEMENTED** |
| B | Crypto Identity | ✅ | — | **IMPLEMENTED** |
| C | Lifecycle Timeline | ✅ | — | **IMPLEMENTED** |
| D | Handshake Metrics | ✅ | ✅ | **IMPLEMENTED** |
| E | Crypto Primitives | ✅ | — | **PARTIAL** (from status file) |
| F | Rekey Metrics | ⚠️ | — | **NOT IMPLEMENTED** |
| G | Data Plane | ✅ | ✅ | **IMPLEMENTED** |
| H | Latency & Jitter | ✅ | ✅ | **IMPLEMENTED** |
| I | MAVProxy Drone | ✅ | — | **IMPLEMENTED** |
| J | MAVProxy GCS | — | ✅ | **IMPLEMENTED** (pruned) |
| K | MAVLink Integrity | ✅ | ✅ | **IMPLEMENTED** |
| L | FC Telemetry | ✅ | — | **IMPLEMENTED** |
| M | Control Plane | ✅ | — | **IMPLEMENTED** |
| N | System Resources Drone | ✅ | — | **IMPLEMENTED** |
| O | System Resources GCS | — | ❌ | **REMOVED** (policy) |
| P | Power & Energy | ✅ | — | **IMPLEMENTED** |
| Q | Observability | ✅ | — | **IMPLEMENTED** |
| R | Validation | ✅ | — | **IMPLEMENTED** |

---

## Detailed Metric Implementation

### ✅ Fully Implemented

| Metric | Source | Collection Method |
|--------|--------|-------------------|
| `run_id` | Drone | UUID generation |
| `suite_id` | Drone | Suite name |
| `git_commit_hash` | Drone | `git rev-parse HEAD` |
| `handshake_total_duration_ms` | Drone | `time.time()` delta |
| `packets_sent/received` | Both | Socket counters |
| `one_way_latency_avg_ms` | Drone | Embedded `ts_ns` in packets |
| `latency_p50/p95/max` | Drone | Sorted percentiles |
| `jitter_avg_ms` | Drone | Inter-arrival variance |
| `cpu_usage_avg_percent` | Drone | psutil sampling |
| `temperature_c` | Drone | `/sys/class/thermal` |
| `power_avg_w` | Drone | INA219 @ 100Hz |
| `energy_total_j` | Drone | avg_power × duration |
| `mavlink_seq_gap_count` | Both | Sequence tracking |

### ⚠️ Partial Implementation

| Metric | Issue |
|--------|-------|
| `kem_keygen_time_ms` | Read from proxy status file, may be 0 |
| `kem_encaps/decaps_time_ms` | Same — depends on proxy emitting metrics |
| `sig_sign/verify_time_ms` | Same — not always populated |

### ❌ Not Implemented

| Metric | Impact |
|--------|--------|
| `rekey_attempts/success/failure` | No rekey during benchmark |
| `rekey_blackout_duration_ms` | Benchmarks run single suite per cycle |
| `gcs_cpu/memory` | Removed per policy (GCS non-constrained) |

---

## Power Monitoring Details

```
Sensor: INA219 or RPi5 hwmon
Sample Rate: 100Hz (10ms interval)
Duration: Per-suite cycle time (default 10s)
Samples: ~1000 per suite

Captured:
  - voltage_v (bus voltage)
  - current_a (shunt current / 1000)
  - power_w (direct or computed)

Derived:
  - energy_total_j = avg_power × duration
  - energy_per_handshake_j = avg_power × handshake_s
```

---

## Latency Measurement

```
Method: Embedded timestamps in UDP packets

GCS TrafficGenerator:
  packet = {"ts_ns": time.time_ns(), "seq": n, "pad": ...}
  
Drone EchoServer:
  recv_ts = time.time_ns()
  latency_ms = (recv_ts - packet["ts_ns"]) / 1_000_000

Note: One-way latency (not RTT) — requires clock sync
```

---

## Output Format

| Output | Path | Format |
|--------|------|--------|
| Primary | `logs/benchmarks/{run_id}/benchmark_{run_id}.jsonl` | JSONL |
| Logs | `logs/benchmarks/{run_id}/*.log` | Text |
