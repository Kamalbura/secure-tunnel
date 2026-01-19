# METRIC COLLECTION VERIFICATION AUDIT

**Date:** 2026-01-19
**Scripts Audited:** `sdrone_bench.py`, `sgcs_bench.py`, `benchmark_policy.py`, `core/metrics_aggregator.py`

---

## SECTION A: RUN & CONTEXT METRICS

Metric: `run_id`
Expected Side: DRONE
Status: **PRESENT**
Evidence:
- File: `benchmark_policy.py`
- Function: `__init__`
- Lines: 168
- Emitted: `sdrone_bench.py` L300 (file name), `metrics_aggregator.py` L162

---

Metric: `suite_id`
Expected Side: DRONE
Status: **PRESENT**
Evidence:
- File: `metrics_aggregator.py`
- Function: `start_suite`
- Lines: 163
- Emitted: `sdrone_bench.py` L565

---

Metric: `suite_index`
Expected Side: DRONE
Status: **PRESENT**
Evidence:
- File: `metrics_aggregator.py`
- Function: `start_suite`
- Lines: 164

---

Metric: `git_commit_hash`
Expected Side: DRONE
Status: **PRESENT**
Evidence:
- File: `metrics_aggregator.py`
- Function: `start_suite`
- Lines: 165

---

Metric: `git_dirty_flag`
Expected Side: DRONE
Status: **PRESENT**
Evidence:
- File: `metrics_aggregator.py`
- Function: `start_suite`
- Lines: 166

---

Metric: `gcs_hostname`
Expected Side: GCS
Status: **PRESENT**
Evidence:
- File: `metrics_aggregator.py`
- Function: `start_suite`
- Lines: 169

---

Metric: `drone_hostname`
Expected Side: DRONE
Status: **PRESENT**
Evidence:
- File: `metrics_aggregator.py`
- Function: `start_suite`
- Lines: 174

---

Metric: `gcs_ip`
Expected Side: GCS
Status: **PRESENT**
Evidence:
- File: `metrics_aggregator.py`
- Lines: 170

---

Metric: `drone_ip`
Expected Side: DRONE
Status: **PRESENT**
Evidence:
- File: `metrics_aggregator.py`
- Lines: 175

---

Metric: `python_env_gcs`
Expected Side: GCS
Status: **PRESENT**
Evidence:
- File: `metrics_aggregator.py`
- Lines: 171

---

Metric: `python_env_drone`
Expected Side: DRONE
Status: **PRESENT**
Evidence:
- File: `metrics_aggregator.py`
- Lines: 176

---

Metric: `liboqs_version`
Expected Side: DRONE
Status: **PRESENT**
Evidence:
- File: `metrics_aggregator.py`
- Lines: 179

---

Metric: `kernel_version_gcs`
Expected Side: GCS
Status: **PRESENT**
Evidence:
- File: `metrics_aggregator.py`
- Lines: 172

---

Metric: `kernel_version_drone`
Expected Side: DRONE
Status: **PRESENT**
Evidence:
- File: `metrics_aggregator.py`
- Lines: 177

---

Metric: `clock_offset_ms`
Expected Side: DRONE
Status: **NOT PRESENT**
Evidence:
- No assignment found in `metrics_aggregator.py`
- `ClockSync` class exists but offset not written to schema
Notes:
- ClockSync offset computed at `sdrone_bench.py` L352 but not stored in metrics

---

Metric: `clock_offset_method`
Expected Side: DRONE
Status: **NOT PRESENT**
Evidence:
- No assignment found

---

Metric: `run_start_time_wall`
Expected Side: DRONE
Status: **PRESENT**
Evidence:
- File: `metrics_aggregator.py`
- Lines: 180

---

Metric: `run_end_time_wall`
Expected Side: DRONE
Status: **PRESENT**
Evidence:
- File: `metrics_aggregator.py`
- Lines: 439

---

Metric: `run_start_time_mono`
Expected Side: DRONE
Status: **PRESENT**
Evidence:
- File: `metrics_aggregator.py`
- Lines: 181

---

Metric: `run_end_time_mono`
Expected Side: DRONE
Status: **PRESENT**
Evidence:
- File: `metrics_aggregator.py`
- Lines: 440

---

## SECTION B: SUITE CRYPTO IDENTITY

Metric: `kem_algorithm`
Expected Side: DRONE
Status: **PRESENT**
Evidence:
- File: `metrics_aggregator.py`
- Lines: 185

---

Metric: `kem_family`
Expected Side: DRONE
Status: **PRESENT**
Evidence:
- File: `metrics_aggregator.py`
- Lines: 193-199

---

Metric: `kem_parameter_set`
Expected Side: DRONE
Status: **NOT PRESENT**
Evidence:
- No assignment found

---

Metric: `kem_nist_level`
Expected Side: DRONE
Status: **PRESENT**
Evidence:
- File: `metrics_aggregator.py`
- Lines: 186

---

Metric: `sig_algorithm`
Expected Side: DRONE
Status: **PRESENT**
Evidence:
- File: `metrics_aggregator.py`
- Lines: 187

---

Metric: `sig_family`
Expected Side: DRONE
Status: **PRESENT**
Evidence:
- File: `metrics_aggregator.py`
- Lines: 201-207

---

Metric: `sig_parameter_set`
Expected Side: DRONE
Status: **NOT PRESENT**
Evidence:
- No assignment found

---

Metric: `sig_nist_level`
Expected Side: DRONE
Status: **PRESENT**
Evidence:
- File: `metrics_aggregator.py`
- Lines: 188

---

Metric: `aead_algorithm`
Expected Side: DRONE
Status: **PRESENT**
Evidence:
- File: `metrics_aggregator.py`
- Lines: 189

---

Metric: `aead_mode`
Expected Side: DRONE
Status: **NOT PRESENT**
Evidence:
- No assignment found

---

Metric: `suite_security_level`
Expected Side: DRONE
Status: **PRESENT**
Evidence:
- File: `metrics_aggregator.py`
- Lines: 190

---

Metric: `suite_tier`
Expected Side: DRONE
Status: **NOT PRESENT**
Evidence:
- No assignment found

---

Metric: `suite_order_index`
Expected Side: DRONE
Status: **NOT PRESENT**
Evidence:
- `suite_index` is present, but `suite_order_index` is not explicitly mapped

---

## SECTION C: SUITE LIFECYCLE TIMELINE

Metric: `suite_selected_time`
Expected Side: DRONE
Status: **PRESENT**
Evidence:
- File: `metrics_aggregator.py`
- Lines: 210

---

Metric: `suite_activated_time`
Expected Side: DRONE
Status: **PRESENT**
Evidence:
- File: `metrics_aggregator.py`
- Lines: 261

---

Metric: `suite_traffic_start_time`
Expected Side: DRONE
Status: **PRESENT**
Evidence:
- File: `metrics_aggregator.py`
- Lines: 377

---

Metric: `suite_traffic_end_time`
Expected Side: DRONE
Status: **PRESENT**
Evidence:
- File: `metrics_aggregator.py`
- Lines: 382

---

Metric: `suite_rekey_start_time`
Expected Side: DRONE
Status: **NOT PRESENT**
Evidence:
- No assignment found

---

Metric: `suite_rekey_end_time`
Expected Side: DRONE
Status: **NOT PRESENT**
Evidence:
- No assignment found

---

Metric: `suite_deactivated_time`
Expected Side: DRONE
Status: **PRESENT**
Evidence:
- File: `metrics_aggregator.py`
- Lines: 443

---

Metric: `suite_total_duration_ms`
Expected Side: DRONE
Status: **PRESENT**
Evidence:
- File: `metrics_aggregator.py`
- Lines: 444

---

Metric: `suite_active_duration_ms`
Expected Side: DRONE
Status: **PRESENT**
Evidence:
- File: `metrics_aggregator.py`
- Lines: 446

---

Metric: `suite_blackout_count`
Expected Side: DRONE
Status: **NOT PRESENT**
Evidence:
- No assignment found

---

Metric: `suite_blackout_total_ms`
Expected Side: DRONE
Status: **NOT PRESENT**
Evidence:
- No assignment found

---

## SECTION D: HANDSHAKE METRICS

Metric: `handshake_start_time_drone`
Expected Side: DRONE
Status: **PRESENT**
Evidence:
- File: `metrics_aggregator.py`
- Lines: 240

---

Metric: `handshake_end_time_drone`
Expected Side: DRONE
Status: **PRESENT**
Evidence:
- File: `metrics_aggregator.py`
- Lines: 253

---

Metric: `handshake_start_time_gcs`
Expected Side: GCS
Status: **PRESENT**
Evidence:
- File: `metrics_aggregator.py`
- Lines: 238

---

Metric: `handshake_end_time_gcs`
Expected Side: GCS
Status: **PRESENT**
Evidence:
- File: `metrics_aggregator.py`
- Lines: 249

---

Metric: `handshake_total_duration_ms`
Expected Side: DRONE
Status: **PRESENT**
Evidence:
- File: `metrics_aggregator.py`
- Lines: 251, 255

---

Metric: `handshake_rtt_ms`
Expected Side: DRONE
Status: **NOT PRESENT**
Evidence:
- No assignment found

---

Metric: `handshake_success`
Expected Side: DRONE
Status: **PRESENT**
Evidence:
- File: `metrics_aggregator.py`
- Lines: 257

---

Metric: `handshake_failure_reason`
Expected Side: DRONE
Status: **PRESENT**
Evidence:
- File: `metrics_aggregator.py`
- Lines: 258

---

## SECTION E: CRYPTO PRIMITIVE BREAKDOWN

Metric: `kem_keygen_time_ms`
Expected Side: DRONE
Status: **PRESENT**
Evidence:
- File: `metrics_aggregator.py`
- Lines: 280

---

Metric: `kem_encapsulation_time_ms`
Expected Side: DRONE
Status: **PRESENT**
Evidence:
- File: `metrics_aggregator.py`
- Lines: 283

---

Metric: `kem_decapsulation_time_ms`
Expected Side: DRONE
Status: **PRESENT**
Evidence:
- File: `metrics_aggregator.py`
- Lines: 286

---

Metric: `signature_sign_time_ms`
Expected Side: DRONE
Status: **PRESENT**
Evidence:
- File: `metrics_aggregator.py`
- Lines: 289

---

Metric: `signature_verify_time_ms`
Expected Side: DRONE
Status: **PRESENT**
Evidence:
- File: `metrics_aggregator.py`
- Lines: 292

---

Metric: `hkdf_extract_time_ms`
Expected Side: DRONE
Status: **NOT PRESENT**
Evidence:
- No assignment found

---

Metric: `hkdf_expand_time_ms`
Expected Side: DRONE
Status: **NOT PRESENT**
Evidence:
- No assignment found

---

Metric: `total_crypto_time_ms`
Expected Side: DRONE
Status: **PRESENT**
Evidence:
- File: `metrics_aggregator.py`
- Lines: 314-320

---

## SECTION F: REKEY METRICS

Metric: `rekey_attempts`
Expected Side: DRONE
Status: **NOT PRESENT**
Evidence:
- No assignment found in audited files

---

Metric: `rekey_success`
Expected Side: DRONE
Status: **NOT PRESENT**
Evidence:
- No assignment found

---

Metric: `rekey_failure`
Expected Side: DRONE
Status: **NOT PRESENT**
Evidence:
- No assignment found

---

Metric: `rekey_interval_ms`
Expected Side: DRONE
Status: **NOT PRESENT**
Evidence:
- No assignment found

---

Metric: `rekey_duration_ms`
Expected Side: DRONE
Status: **NOT PRESENT**
Evidence:
- No assignment found

---

Metric: `rekey_blackout_duration_ms`
Expected Side: DRONE
Status: **NOT PRESENT**
Evidence:
- No assignment found

---

Metric: `rekey_trigger_reason`
Expected Side: DRONE
Status: **NOT PRESENT**
Evidence:
- No assignment found

---

## SECTION G: DATA PLANE

Metric: `target_throughput_mbps`
Expected Side: DRONE
Status: **NOT PRESENT**
Evidence:
- No assignment found

---

Metric: `achieved_throughput_mbps`
Expected Side: DRONE
Status: **NOT PRESENT**
Evidence:
- No calculation in `record_data_plane_metrics`

---

Metric: `goodput_mbps`
Expected Side: DRONE
Status: **NOT PRESENT**
Evidence:
- No assignment found

---

Metric: `wire_rate_mbps`
Expected Side: DRONE
Status: **NOT PRESENT**
Evidence:
- No assignment found

---

Metric: `packets_sent`
Expected Side: DRONE
Status: **PRESENT**
Evidence:
- File: `metrics_aggregator.py`
- Lines: 345

---

Metric: `packets_received`
Expected Side: DRONE
Status: **PRESENT**
Evidence:
- File: `metrics_aggregator.py`
- Lines: 346

---

Metric: `packets_dropped`
Expected Side: DRONE
Status: **PRESENT**
Evidence:
- File: `metrics_aggregator.py`
- Lines: 347

---

Metric: `packet_loss_ratio`
Expected Side: DRONE
Status: **PRESENT**
Evidence:
- File: `metrics_aggregator.py`
- Lines: 351

---

Metric: `packet_delivery_ratio`
Expected Side: DRONE
Status: **PRESENT**
Evidence:
- File: `metrics_aggregator.py`
- Lines: 352

---

Metric: `replay_drop_count`
Expected Side: DRONE
Status: **PARTIALLY PRESENT**
Evidence:
- Stored as `drop_replay` (L341), not `replay_drop_count`

---

Metric: `decode_failure_count`
Expected Side: DRONE
Status: **NOT PRESENT**
Evidence:
- No assignment found

---

## SECTION H: LATENCY & JITTER

Metric: `one_way_latency_avg_ms`
Expected Side: DRONE
Status: **PRESENT**
Evidence:
- File: `metrics_aggregator.py`
- Lines: 450

---

Metric: `one_way_latency_p50_ms`
Expected Side: DRONE
Status: **PRESENT**
Evidence:
- File: `metrics_aggregator.py`
- Lines: 451

---

Metric: `one_way_latency_p95_ms`
Expected Side: DRONE
Status: **PRESENT**
Evidence:
- File: `metrics_aggregator.py`
- Lines: 452

---

Metric: `one_way_latency_max_ms`
Expected Side: DRONE
Status: **PRESENT**
Evidence:
- File: `metrics_aggregator.py`
- Lines: 453

---

Metric: `round_trip_latency_avg_ms`
Expected Side: DRONE
Status: **NOT PRESENT**
Evidence:
- No assignment found

---

Metric: `round_trip_latency_p50_ms`
Expected Side: DRONE
Status: **NOT PRESENT**
Evidence:
- No assignment found

---

Metric: `round_trip_latency_p95_ms`
Expected Side: DRONE
Status: **NOT PRESENT**
Evidence:
- No assignment found

---

Metric: `round_trip_latency_max_ms`
Expected Side: DRONE
Status: **NOT PRESENT**
Evidence:
- No assignment found

---

Metric: `jitter_avg_ms`
Expected Side: DRONE
Status: **NOT PRESENT**
Evidence:
- No assignment to `jitter_avg_ms` in `finalize_suite`

---

Metric: `jitter_p95_ms`
Expected Side: DRONE
Status: **NOT PRESENT**
Evidence:
- No assignment found

---

## SECTION I: MAVPROXY DRONE SIDE

Metric: `mavproxy_drone_start_time`
Expected Side: DRONE
Status: **NOT PRESENT**
Evidence:
- No explicit assignment in `populate_schema_metrics`

---

Metric: `mavproxy_drone_end_time`
Expected Side: DRONE
Status: **NOT PRESENT**
Evidence:
- No assignment found

---

Metric: `mavproxy_drone_tx_pps`
Expected Side: DRONE
Status: **NOT PRESENT**
Evidence:
- No assignment found

---

Metric: `mavproxy_drone_rx_pps`
Expected Side: DRONE
Status: **NOT PRESENT**
Evidence:
- No assignment found

---

Metric: `mavproxy_drone_total_msgs_sent`
Expected Side: DRONE
Status: **NOT PRESENT**
Evidence:
- No assignment found

---

Metric: `mavproxy_drone_total_msgs_received`
Expected Side: DRONE
Status: **PARTIALLY PRESENT**
Evidence:
- Populated via `mavlink_collector.populate_schema_metrics` (L504) but dependson external collector

---

Metric: `mavproxy_drone_msg_type_counts`
Expected Side: DRONE
Status: **PARTIALLY PRESENT**
Evidence:
- Dependent on mavlink_collector implementation

---

Metric: `mavproxy_drone_heartbeat_interval_ms`
Expected Side: DRONE
Status: **PARTIALLY PRESENT**
Evidence:
- Dependent on mavlink_collector implementation

---

Metric: `mavproxy_drone_heartbeat_loss_count`
Expected Side: DRONE
Status: **NOT PRESENT**
Evidence:
- No assignment found

---

Metric: `mavproxy_drone_seq_gap_count`
Expected Side: DRONE
Status: **PARTIALLY PRESENT**
Evidence:
- Dependent on mavlink_collector (L507)

---

Metric: `mavproxy_drone_reconnect_count`
Expected Side: DRONE
Status: **NOT PRESENT**
Evidence:
- No assignment found

---

Metric: `mavproxy_drone_cmd_sent_count`
Expected Side: DRONE
Status: **NOT PRESENT**
Evidence:
- No assignment found

---

Metric: `mavproxy_drone_cmd_ack_received_count`
Expected Side: DRONE
Status: **NOT PRESENT**
Evidence:
- No assignment found

---

Metric: `mavproxy_drone_cmd_ack_latency_avg_ms`
Expected Side: DRONE
Status: **NOT PRESENT**
Evidence:
- No assignment found

---

Metric: `mavproxy_drone_cmd_ack_latency_p95_ms`
Expected Side: DRONE
Status: **NOT PRESENT**
Evidence:
- No assignment found

---

Metric: `mavproxy_drone_stream_rate_hz`
Expected Side: DRONE
Status: **NOT PRESENT**
Evidence:
- No assignment found

---

Metric: `mavproxy_drone_log_path`
Expected Side: DRONE
Status: **NOT PRESENT**
Evidence:
- Log path created at L253 in `sdrone_bench.py` but not stored in metrics

---

## SECTION J: MAVPROXY GCS SIDE

(Similar analysis - most are NOT PRESENT or PARTIALLY PRESENT via mavlink_collector)

Metric: `mavproxy_gcs_total_msgs_received`
Expected Side: GCS
Status: **PRESENT**
Evidence:
- File: `sgcs_bench.py`
- `GcsMavLinkCollector.stop()` returns this via L647

---

Metric: `mavproxy_gcs_seq_gap_count`
Expected Side: GCS
Status: **PRESENT**
Evidence:
- Returned by `GcsMavLinkCollector.stop()`

---

(Other GCS MAVProxy metrics: NOT PRESENT)

---

## SECTION K: MAVLINK SEMANTIC INTEGRITY

Metric: `mavlink_out_of_order_count`
Expected Side: DRONE
Status: **PARTIALLY PRESENT**
Evidence:
- Mapped via `mavlink_collector.populate_mavlink_integrity` (L507)

---

(All other Section K metrics: NOT PRESENT)

---

## SECTION L: FLIGHT CONTROLLER TELEMETRY

(All metrics: NOT PRESENT - no FC telemetry extraction in current code)

---

## SECTION M: CONTROL PLANE

Metric: `scheduler_tick_interval_ms`
Expected Side: DRONE
Status: **NOT PRESENT**
Evidence:
- `cycle_interval_s` exists but not written to metrics

---

(All other Section M metrics: NOT PRESENT)

---

## SECTION N: SYSTEM RESOURCES DRONE

Metric: `cpu_usage_avg_percent`
Expected Side: DRONE
Status: **PRESENT**
Evidence:
- File: `metrics_aggregator.py`
- Lines: 466

---

Metric: `cpu_usage_peak_percent`
Expected Side: DRONE
Status: **PRESENT**
Evidence:
- File: `metrics_aggregator.py`
- Lines: 467

---

Metric: `cpu_freq_mhz`
Expected Side: DRONE
Status: **PRESENT**
Evidence:
- File: `metrics_aggregator.py`
- Lines: 471

---

Metric: `memory_rss_mb`
Expected Side: DRONE
Status: **PRESENT**
Evidence:
- File: `metrics_aggregator.py`
- Lines: 472

---

Metric: `memory_vms_mb`
Expected Side: DRONE
Status: **PRESENT**
Evidence:
- File: `metrics_aggregator.py`
- Lines: 473

---

Metric: `thread_count`
Expected Side: DRONE
Status: **PRESENT**
Evidence:
- File: `metrics_aggregator.py`
- Lines: 474

---

Metric: `temperature_c`
Expected Side: DRONE
Status: **PRESENT**
Evidence:
- File: `metrics_aggregator.py`
- Lines: 477

---

Metric: `thermal_throttle_events`
Expected Side: DRONE
Status: **NOT PRESENT**
Evidence:
- No assignment found

---

## SECTION P: POWER & ENERGY

Metric: `power_sensor_type`
Expected Side: DRONE
Status: **PRESENT**
Evidence:
- File: `metrics_aggregator.py`
- Lines: 485

---

Metric: `power_sampling_rate_hz`
Expected Side: DRONE
Status: **PRESENT**
Evidence:
- File: `metrics_aggregator.py`
- Lines: 486

---

Metric: `voltage_avg_v`
Expected Side: DRONE
Status: **NOT PRESENT**
Evidence:
- Not extracted from power samples in current code

---

Metric: `current_avg_a`
Expected Side: DRONE
Status: **NOT PRESENT**
Evidence:
- Not extracted from power samples

---

Metric: `power_avg_w`
Expected Side: DRONE
Status: **PRESENT**
Evidence:
- File: `metrics_aggregator.py`
- Lines: 487

---

Metric: `power_peak_w`
Expected Side: DRONE
Status: **PRESENT**
Evidence:
- File: `metrics_aggregator.py`
- Lines: 488

---

Metric: `energy_total_j`
Expected Side: DRONE
Status: **PRESENT**
Evidence:
- File: `metrics_aggregator.py`
- Lines: 489

---

Metric: `energy_per_handshake_j`
Expected Side: DRONE
Status: **PRESENT**
Evidence:
- File: `metrics_aggregator.py`
- Lines: 494

---

Metric: `energy_per_rekey_j`
Expected Side: DRONE
Status: **NOT PRESENT**
Evidence:
- No assignment found

---

Metric: `energy_per_second_j`
Expected Side: DRONE
Status: **NOT PRESENT**
Evidence:
- No assignment found

---

## SECTION Q: OBSERVABILITY

Metric: `metrics_sampling_rate_hz`
Expected Side: DRONE
Status: **PRESENT**
Evidence:
- File: `metrics_aggregator.py`
- Lines: 513

---

Metric: `trace_file_path`
Expected Side: DRONE
Status: **NOT PRESENT**
Evidence:
- No assignment found

---

Metric: `power_trace_file_path`
Expected Side: DRONE
Status: **NOT PRESENT**
Evidence:
- No assignment found

---

Metric: `traffic_trace_file_path`
Expected Side: DRONE
Status: **NOT PRESENT**
Evidence:
- No assignment found

---

## SECTION R: VALIDATION

Metric: `expected_samples`
Expected Side: DRONE
Status: **PRESENT**
Evidence:
- File: `metrics_aggregator.py`
- Lines: 519

---

Metric: `collected_samples`
Expected Side: DRONE
Status: **PRESENT**
Evidence:
- File: `metrics_aggregator.py`
- Lines: 520

---

Metric: `lost_samples`
Expected Side: DRONE
Status: **PRESENT**
Evidence:
- File: `metrics_aggregator.py`
- Lines: 521

---

Metric: `success_rate_percent`
Expected Side: DRONE
Status: **PRESENT**
Evidence:
- File: `metrics_aggregator.py`
- Lines: 522

---

Metric: `benchmark_pass_fail`
Expected Side: DRONE
Status: **PRESENT**
Evidence:
- File: `metrics_aggregator.py`
- Lines: 523

---

Metric: `termination_reason`
Expected Side: DRONE
Status: **NOT PRESENT**
Evidence:
- No assignment found

---

# SUMMARY

## TOTALS

| Category | PRESENT | PARTIALLY PRESENT | NOT PRESENT |
|:---|:---:|:---:|:---:|
| A. Run & Context (20) | 16 | 0 | 4 |
| B. Crypto Identity (13) | 8 | 0 | 5 |
| C. Lifecycle (11) | 7 | 0 | 4 |
| D. Handshake (8) | 7 | 0 | 1 |
| E. Crypto Primitives (8) | 6 | 0 | 2 |
| F. Rekey (7) | 0 | 0 | 7 |
| G. Data Plane (11) | 5 | 1 | 5 |
| H. Latency/Jitter (10) | 4 | 0 | 6 |
| I. MAVProxy Drone (17) | 0 | 5 | 12 |
| J. MAVProxy GCS (13) | 2 | 0 | 11 |
| K. MAVLink Integrity (10) | 0 | 1 | 9 |
| L. FC Telemetry (10) | 0 | 0 | 10 |
| M. Control Plane (7) | 0 | 0 | 7 |
| N. System Drone (8) | 7 | 0 | 1 |
| P. Power/Energy (10) | 6 | 0 | 4 |
| Q. Observability (4) | 1 | 0 | 3 |
| R. Validation (6) | 5 | 0 | 1 |

---

## GRAND TOTALS

**TOTAL METRICS CHECKED:** 163

**PRESENT:** 74

**PARTIALLY PRESENT:** 7

**NOT PRESENT:** 82

---

## LIST OF NOT PRESENT METRICS

```
clock_offset_ms
clock_offset_method
kem_parameter_set
sig_parameter_set
aead_mode
suite_tier
suite_order_index
suite_rekey_start_time
suite_rekey_end_time
suite_blackout_count
suite_blackout_total_ms
handshake_rtt_ms
hkdf_extract_time_ms
hkdf_expand_time_ms
rekey_attempts
rekey_success
rekey_failure
rekey_interval_ms
rekey_duration_ms
rekey_blackout_duration_ms
rekey_trigger_reason
target_throughput_mbps
achieved_throughput_mbps
goodput_mbps
wire_rate_mbps
decode_failure_count
round_trip_latency_avg_ms
round_trip_latency_p50_ms
round_trip_latency_p95_ms
round_trip_latency_max_ms
jitter_avg_ms
jitter_p95_ms
mavproxy_drone_start_time
mavproxy_drone_end_time
mavproxy_drone_tx_pps
mavproxy_drone_rx_pps
mavproxy_drone_total_msgs_sent
mavproxy_drone_heartbeat_loss_count
mavproxy_drone_reconnect_count
mavproxy_drone_cmd_sent_count
mavproxy_drone_cmd_ack_received_count
mavproxy_drone_cmd_ack_latency_avg_ms
mavproxy_drone_cmd_ack_latency_p95_ms
mavproxy_drone_stream_rate_hz
mavproxy_drone_log_path
mavproxy_gcs_start_time
mavproxy_gcs_end_time
mavproxy_gcs_tx_pps
mavproxy_gcs_rx_pps
mavproxy_gcs_total_msgs_sent
mavproxy_gcs_reconnect_count
mavproxy_gcs_cmd_sent_count
mavproxy_gcs_cmd_ack_received_count
mavproxy_gcs_cmd_ack_latency_avg_ms
mavproxy_gcs_cmd_ack_latency_p95_ms
mavproxy_gcs_log_path
mavlink_sysid
mavlink_compid
mavlink_protocol_version
mavlink_packet_crc_error_count
mavlink_decode_error_count
mavlink_msg_drop_count
mavlink_duplicate_count
mavlink_message_latency_avg_ms
mavlink_message_latency_p95_ms
fc_mode
fc_armed_state
fc_heartbeat_age_ms
fc_attitude_update_rate_hz
fc_position_update_rate_hz
fc_battery_voltage_v
fc_battery_current_a
fc_battery_remaining_percent
fc_cpu_load_percent
fc_sensor_health_flags
scheduler_tick_interval_ms
scheduler_decision_latency_ms
scheduler_action_type
scheduler_action_reason
scheduler_cooldown_remaining_ms
control_channel_rtt_ms
control_channel_disconnect_count
thermal_throttle_events
voltage_avg_v
current_avg_a
energy_per_rekey_j
energy_per_second_j
trace_file_path
power_trace_file_path
traffic_trace_file_path
termination_reason
```

---

## LIST OF PARTIALLY PRESENT METRICS

```
replay_drop_count (stored as drop_replay)
mavproxy_drone_total_msgs_received (via external collector)
mavproxy_drone_msg_type_counts (via external collector)
mavproxy_drone_heartbeat_interval_ms (via external collector)
mavproxy_drone_seq_gap_count (via external collector)
mavlink_out_of_order_count (via external collector)
(additional dependency on mavlink_collector implementation)
```
