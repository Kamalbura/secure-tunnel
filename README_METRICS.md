# Metrics Catalog (Code-Derived)

This file is derived strictly from implemented code. No documentation or comments are treated as authoritative.

## Drone-Side Metrics (VERIFIED)

### Suite Result JSONL (sdrone_bench)
Written per suite to logs/benchmarks/benchmark_<run_id>.jsonl by sscheduler/sdrone_bench.py.
Fields:
- ts (UTC ISO)
- suite_id
- nist_level, kem_name, sig_name, aead
- success, error
- handshake_ms
- kem_keygen_ms, kem_encaps_ms, kem_decaps_ms
- sig_sign_ms, sig_verify_ms
- pub_key_size_bytes, ciphertext_size_bytes, sig_size_bytes

### Comprehensive Metrics (Optional)
When core.metrics_aggregator.MetricsAggregator is available, per-suite data includes:
- Handshake timing and primitive metrics (from core/handshake and core/async_proxy counters)
- Data-plane counters (ptx_in, enc_out, enc_in, drops, replay/auth/header errors, rekey stats)
- Optional power metrics if enabled

### Proxy Status File
core/async_proxy writes logs/benchmarks/drone_status.json periodically:
- status
- suite
- counters (ptx_in, enc_out, enc_in, drops, rekeys_ok/fail, last_rekey_ms, handshake_metrics, primitive_metrics)
- ts_ns

## GCS-Side Metrics (VERIFIED)

### GCS Suite Metrics JSONL
Written per suite to logs/benchmarks/<run_id>/gcs_suite_metrics.jsonl by sscheduler/sgcs_bench.py.
Payload includes:
- suite
- mavlink_validation (total_msgs_received, seq_gap_count)
- proxy_status (from logs/benchmarks/<run_id>/gcs_status.json when available)

### MAVLink Telemetry Collector (MAV Variant)
sscheduler/gcs_metrics.py logs JSONL telemetry snapshots to logs/gcs_telemetry_v1.jsonl with:
- link window stats: sample_count, rx_pps, rx_bps, silence_ms, gap metrics, jitter, blackout stats
- MAVLink heartbeat age, battery voltage
- proxy status (alive, pid)

## Benchmark Policy Metrics (VERIFIED)
sscheduler/benchmark_policy.py tracks per-suite metrics in memory and outputs JSON/CSV with:
- suite_id, iteration, nist_level, kem_name, sig_name, aead
- handshake_ms, throughput_mbps, latency_ms, power_w, energy_mj
- kem/sign timings (keygen/encaps/decaps), sig sign/verify
- artifact sizes (public key, ciphertext, signature)
- success, error_message

## UNVERIFIED
- External monitoring tools, MAVProxy settings, or non-code pipelines are not included here.
