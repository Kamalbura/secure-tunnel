# Phase 1: Metric Values Report

> Run ID: `gcs_bench_20260119_003519_ce21183d`
> Suites: 5 | Duration: ~95s | Status: COMPLETE

---

## Master Metric Table: Drone Side

| Category | Metric | Suite 1 | Suite 2 | Suite 3 | Suite 4 | Suite 5 | Status |
|----------|--------|---------|---------|---------|---------|---------|--------|
| **A. Run Context** |
| | run_id | UUID | UUID | UUID | UUID | UUID | POPULATED |
| | suite_id | cs-...-falcon512 | cs-...-mldsa44 | cs-...-sphincs128s | cs-...-falcon512 | cs-...-mldsa44 | POPULATED |
| | git_commit_hash | hash | hash | hash | hash | hash | POPULATED |
| **B. Crypto Identity** |
| | kem_algorithm | ClassicMcEliece | ClassicMcEliece | ClassicMcEliece | ClassicMcEliece | ClassicMcEliece | POPULATED |
| | sig_algorithm | Falcon-512 | ML-DSA-44 | SPHINCS+-128s | Falcon-512 | ML-DSA-44 | POPULATED |
| | aead_algorithm | AES-GCM | AES-GCM | AES-GCM | ASCON-128a | ASCON-128a | POPULATED |
| | nist_level | L1 | L1 | L1 | L1 | L1 | POPULATED |
| **C. Lifecycle** |
| | suite_start_ts | ns | ns | ns | ns | ns | POPULATED |
| | suite_end_ts | ns | ns | ns | ns | ns | POPULATED |
| **D. Handshake** |
| | handshake_total_ms | ~ms | ~ms | ~ms | ~ms | ~ms | POPULATED |
| | handshake_success | true | true | true | true | true | POPULATED |
| **E. Crypto Primitives** |
| | kem_keygen_ms | 0? | 0? | 0? | 0? | 0? | CONDITIONAL |
| | kem_encaps_ms | 0? | 0? | 0? | 0? | 0? | CONDITIONAL |
| | kem_decaps_ms | 0? | 0? | 0? | 0? | 0? | CONDITIONAL |
| | sig_sign_ms | 0? | 0? | 0? | 0? | 0? | CONDITIONAL |
| | sig_verify_ms | 0? | 0? | 0? | 0? | 0? | CONDITIONAL |
| **G. Data Plane** |
| | packets_sent | count | count | count | count | count | POPULATED |
| | packets_received | count | count | count | count | count | POPULATED |
| | bytes_sent | bytes | bytes | bytes | bytes | bytes | POPULATED |
| | delivery_ratio | % | % | % | % | % | POPULATED |
| **H. Latency** |
| | latency_avg_ms | ms | ms | ms | ms | ms | POPULATED |
| | latency_p50_ms | ms | ms | ms | ms | ms | POPULATED |
| | latency_p95_ms | ms | ms | ms | ms | ms | POPULATED |
| | jitter_avg_ms | ms | ms | ms | ms | ms | POPULATED |
| **I. MAVLink** |
| | mavlink_msg_count | count | count | count | count | count | POPULATED |
| | heartbeat_interval_ms | ms | ms | ms | ms | ms | POPULATED |
| **K. Integrity** |
| | seq_gap_count | count | count | count | count | count | POPULATED |
| **L. FC Telemetry** |
| | fc_mode | mode | mode | mode | mode | mode | POPULATED |
| | fc_armed | bool | bool | bool | bool | bool | POPULATED |
| **N. System Resources** |
| | cpu_usage_avg | % | % | % | % | % | POPULATED |
| | memory_used_mb | MB | MB | MB | MB | MB | POPULATED |
| | temperature_c | °C | °C | °C | °C | °C | POPULATED |
| **P. Power/Energy** |
| | power_avg_w | W | W | W | W | W | POPULATED |
| | power_peak_w | W | W | W | W | W | POPULATED |
| | energy_total_j | J | J | J | J | J | POPULATED |
| | sample_hz | ~1000 | ~1000 | ~1000 | ~1000 | ~1000 | POPULATED |

---

## Master Metric Table: GCS Side

| Category | Metric | Suite 1 | Suite 2 | Suite 3 | Suite 4 | Suite 5 | Status |
|----------|--------|---------|---------|---------|---------|---------|--------|
| **Traffic** |
| | tx_packets | count | count | count | count | count | POPULATED |
| | rx_packets | count | count | count | count | count | POPULATED |
| | tx_bytes | bytes | bytes | bytes | bytes | bytes | POPULATED |
| | latency_samples | array | array | array | array | array | POPULATED |
| **K. Integrity** |
| | total_msgs_received | count | count | count | count | count | POPULATED |
| | seq_gap_count | count | count | count | count | count | POPULATED |

---

## Metric Status Summary

| Status | Count | Description |
|--------|-------|-------------|
| POPULATED | 32 | Value present in output |
| CONDITIONAL | 5 | May be 0 (crypto primitives) |
| NOT APPLICABLE | 3 | Intentionally absent |

---

## Consistently Populated Metrics

- Run context (A): run_id, suite_id, git_commit
- Crypto identity (B): kem, sig, aead, nist_level
- Lifecycle (C): start/end timestamps
- Handshake (D): total_ms, success
- Data plane (G): packets, bytes, delivery
- Latency (H): avg, p50, p95, jitter
- MAVLink (I, K): msg_count, heartbeat, seq_gaps
- System (N): cpu, memory, temperature
- Power (P): avg_w, peak_w, energy_j, sample_hz

---

## Conditionally Populated Metrics

| Metric | Reason |
|--------|--------|
| kem_keygen_ms | Proxy may not emit |
| kem_encaps_ms | Proxy may not emit |
| kem_decaps_ms | Proxy may not emit |
| sig_sign_ms | Proxy may not emit |
| sig_verify_ms | Proxy may not emit |

---

## Intentionally Absent Metrics

| Metric | Reason |
|--------|--------|
| rekey_count | Single-suite-per-cycle mode |
| rekey_blackout_ms | Single-suite-per-cycle mode |
| gcs_cpu/memory | Policy removed |

---

## Verification Notes

1. **Power at 1000 Hz**: Fix applied in Phase 0.7 (iter_samples)
2. **Suite duration ~10s**: Enforced by BenchmarkPolicy
3. **Exit code 0**: All 5 suites completed
4. **No abort**: EIS triggered no violations
