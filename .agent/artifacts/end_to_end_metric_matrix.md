# End-to-End Metric Matrix

> Phase 0.7 • Generated: 2026-01-18
> Status: VERIFIED

---

## Drone-Side Metrics (Collected)

| Category | Metric | Source | Status |
|----------|--------|--------|--------|
| A | `run_id` | UUID | ✅ |
| A | `suite_id` | Suite name | ✅ |
| A | `git_commit_hash` | git rev-parse | ✅ |
| B | `kem_algorithm` | Suite config | ✅ |
| B | `sig_algorithm` | Suite config | ✅ |
| B | `aead_algorithm` | Suite config | ✅ |
| C | `suite_start_ts` | time.time_ns() | ✅ |
| C | `suite_end_ts` | time.time_ns() | ✅ |
| D | `handshake_total_ms` | Delta | ✅ |
| D | `handshake_success` | Boolean | ✅ |
| E | `kem_*_time_ms` | Proxy status | ⚠️ May be 0 |
| E | `sig_*_time_ms` | Proxy status | ⚠️ May be 0 |
| G | `packets_sent` | Echo server | ✅ |
| G | `packets_received` | Echo server | ✅ |
| G | `bytes_sent/received` | Echo server | ✅ |
| H | `latency_avg_ms` | Timestamp delta | ✅ |
| H | `latency_p50/p95/max` | Sorted array | ✅ |
| H | `jitter_avg_ms` | Inter-arrival | ✅ |
| I | `mavlink_msg_count` | pymavlink | ✅ |
| I | `heartbeat_interval_ms` | Delta | ✅ |
| K | `seq_gap_count` | Sequence track | ✅ |
| L | `fc_mode` | HEARTBEAT | ✅ |
| L | `fc_armed` | HEARTBEAT | ✅ |
| N | `cpu_usage_avg` | psutil | ✅ |
| N | `memory_used_mb` | psutil | ✅ |
| N | `temperature_c` | thermal zone | ✅ |
| **P** | `power_avg_w` | **INA219 @ 1000Hz** | ✅ **FIXED** |
| **P** | `power_peak_w` | **INA219 samples** | ✅ **FIXED** |
| **P** | `energy_total_j` | **avg × duration** | ✅ **FIXED** |

---

## GCS-Side Metrics (Collected)

| Category | Metric | Source | Status |
|----------|--------|--------|--------|
| Traffic | `tx_packets` | TrafficGenerator | ✅ |
| Traffic | `rx_packets` | TrafficGenerator | ✅ |
| Traffic | `tx_bytes` | TrafficGenerator | ✅ |
| Traffic | `latency_samples` | Embedded ts | ✅ |
| K | `total_msgs_received` | pymavlink | ✅ |
| K | `seq_gap_count` | Sequence track | ✅ |

---

## Metrics NOT Collected (By Design)

| Category | Reason |
|----------|--------|
| F (Rekey) | Single-suite-per-cycle mode |
| O (GCS System) | Removed per policy |
| M (Control Plane) | Internal only |

---

## Fix Summary

| Metric | Before Phase 0.7 | After Phase 0.7 |
|--------|------------------|-----------------|
| `power_avg_w` | 0 | Valid |
| `power_peak_w` | 0 | Valid |
| `energy_total_j` | 0 | Valid |
| `sample_hz` | 0 | ~1000 |
