# FULL SYSTEM METRIC VERIFICATION REPORT

**Date:** 2026-01-19
**Entrypoints:** `sdrone_bench.py`, `sgcs_bench.py`
**Transitive Scope:** `metrics_aggregator.py`, `metrics_schema.py`, `metrics_collectors.py`, `mavlink_collector.py`, `benchmark_policy.py`

---

## VERIFICATION SUMMARY

| Status | Count |
|:---|:---:|
| **PRESENT** | 76 |
| **PARTIALLY PRESENT** | 8 |
| **NOT PRESENT** | 79 |
| **TOTAL** | 163 |

---

## SECTION A: RUN & CONTEXT METRICS (20)

| Metric | Side | Status | Evidence |
|:---|:---:|:---:|:---|
| `run_id` | DRONE | PRESENT | `metrics_aggregator.py:162` → `benchmark_policy.py:168` |
| `suite_id` | DRONE | PRESENT | `metrics_aggregator.py:163` |
| `suite_index` | DRONE | PRESENT | `metrics_aggregator.py:164` |
| `git_commit_hash` | DRONE | PRESENT | `metrics_aggregator.py:165` ← `metrics_collectors.py:125-141` |
| `git_dirty_flag` | DRONE | PRESENT | `metrics_aggregator.py:166` ← `metrics_collectors.py:143-152` |
| `gcs_hostname` | GCS | PRESENT | `metrics_aggregator.py:169` |
| `drone_hostname` | DRONE | PRESENT | `metrics_aggregator.py:174` |
| `gcs_ip` | GCS | PRESENT | `metrics_aggregator.py:170` |
| `drone_ip` | DRONE | PRESENT | `metrics_aggregator.py:175` |
| `python_env_gcs` | GCS | PRESENT | `metrics_aggregator.py:171` |
| `python_env_drone` | DRONE | PRESENT | `metrics_aggregator.py:176` |
| `liboqs_version` | DRONE | PRESENT | `metrics_aggregator.py:179` ← `metrics_collectors.py:154-173` |
| `kernel_version_gcs` | GCS | PRESENT | `metrics_aggregator.py:172` |
| `kernel_version_drone` | DRONE | PRESENT | `metrics_aggregator.py:177` |
| `clock_offset_ms` | DRONE | **NOT PRESENT** | Schema field exists but NO assignment in aggregator |
| `clock_offset_method` | DRONE | **NOT PRESENT** | Schema field exists but NO assignment in aggregator |
| `run_start_time_wall` | DRONE | PRESENT | `metrics_aggregator.py:180` |
| `run_end_time_wall` | DRONE | PRESENT | `metrics_aggregator.py:439` |
| `run_start_time_mono` | DRONE | PRESENT | `metrics_aggregator.py:181` |
| `run_end_time_mono` | DRONE | PRESENT | `metrics_aggregator.py:440` |

**Section A: 18 PRESENT, 2 NOT PRESENT**

---

## SECTION B: SUITE CRYPTO IDENTITY (13)

| Metric | Side | Status | Evidence |
|:---|:---:|:---:|:---|
| `kem_algorithm` | DRONE | PRESENT | `metrics_aggregator.py:185` |
| `kem_family` | DRONE | PRESENT | `metrics_aggregator.py:193-199` |
| `kem_parameter_set` | DRONE | **NOT PRESENT** | Schema field exists, NO assignment |
| `kem_nist_level` | DRONE | PRESENT | `metrics_aggregator.py:186` |
| `sig_algorithm` | DRONE | PRESENT | `metrics_aggregator.py:187` |
| `sig_family` | DRONE | PRESENT | `metrics_aggregator.py:201-207` |
| `sig_parameter_set` | DRONE | **NOT PRESENT** | Schema field exists, NO assignment |
| `sig_nist_level` | DRONE | PRESENT | `metrics_aggregator.py:188` |
| `aead_algorithm` | DRONE | PRESENT | `metrics_aggregator.py:189` |
| `aead_mode` | DRONE | **NOT PRESENT** | Schema field exists, NO assignment |
| `suite_security_level` | DRONE | PRESENT | `metrics_aggregator.py:190` |
| `suite_tier` | DRONE | **NOT PRESENT** | Schema field exists, NO assignment |
| `suite_order_index` | DRONE | **NOT PRESENT** | Schema uses `suite_index` instead |

**Section B: 8 PRESENT, 5 NOT PRESENT**

---

## SECTION C: SUITE LIFECYCLE TIMELINE (11)

| Metric | Side | Status | Evidence |
|:---|:---:|:---:|:---|
| `suite_selected_time` | DRONE | PRESENT | `metrics_aggregator.py:210` |
| `suite_activated_time` | DRONE | PRESENT | `metrics_aggregator.py:261` |
| `suite_traffic_start_time` | DRONE | PRESENT | `metrics_aggregator.py:377` |
| `suite_traffic_end_time` | DRONE | PRESENT | `metrics_aggregator.py:382` |
| `suite_rekey_start_time` | DRONE | **NOT PRESENT** | Schema field exists, NO assignment |
| `suite_rekey_end_time` | DRONE | **NOT PRESENT** | Schema field exists, NO assignment |
| `suite_deactivated_time` | DRONE | PRESENT | `metrics_aggregator.py:443` |
| `suite_total_duration_ms` | DRONE | PRESENT | `metrics_aggregator.py:444` |
| `suite_active_duration_ms` | DRONE | PRESENT | `metrics_aggregator.py:446` |
| `suite_blackout_count` | DRONE | **NOT PRESENT** | Schema field exists, NO assignment |
| `suite_blackout_total_ms` | DRONE | **NOT PRESENT** | Schema field exists, NO assignment |

**Section C: 7 PRESENT, 4 NOT PRESENT**

---

## SECTION D: HANDSHAKE METRICS (8)

| Metric | Side | Status | Evidence |
|:---|:---:|:---:|:---|
| `handshake_start_time_drone` | DRONE | PRESENT | `metrics_aggregator.py:240` |
| `handshake_end_time_drone` | DRONE | PRESENT | `metrics_aggregator.py:253` |
| `handshake_start_time_gcs` | GCS | PRESENT | `metrics_aggregator.py:238` |
| `handshake_end_time_gcs` | GCS | PRESENT | `metrics_aggregator.py:249` |
| `handshake_total_duration_ms` | DRONE | PRESENT | `metrics_aggregator.py:251,255` |
| `handshake_rtt_ms` | DRONE | **NOT PRESENT** | Schema field exists, NO assignment |
| `handshake_success` | DRONE | PRESENT | `metrics_aggregator.py:257` |
| `handshake_failure_reason` | DRONE | PRESENT | `metrics_aggregator.py:258` |

**Section D: 7 PRESENT, 1 NOT PRESENT**

---

## SECTION E: CRYPTO PRIMITIVE BREAKDOWN (8)

| Metric | Side | Status | Evidence |
|:---|:---:|:---:|:---|
| `kem_keygen_time_ms` | DRONE | PRESENT | `metrics_aggregator.py:280` |
| `kem_encapsulation_time_ms` | DRONE | PRESENT | `metrics_aggregator.py:283` |
| `kem_decapsulation_time_ms` | DRONE | PRESENT | `metrics_aggregator.py:286` |
| `signature_sign_time_ms` | DRONE | PRESENT | `metrics_aggregator.py:289` |
| `signature_verify_time_ms` | DRONE | PRESENT | `metrics_aggregator.py:292` |
| `hkdf_extract_time_ms` | DRONE | **NOT PRESENT** | Schema field exists, NO assignment |
| `hkdf_expand_time_ms` | DRONE | **NOT PRESENT** | Schema field exists, NO assignment |
| `total_crypto_time_ms` | DRONE | PRESENT | `metrics_aggregator.py:314-320` |

**Section E: 6 PRESENT, 2 NOT PRESENT**

---

## SECTION F: REKEY METRICS (7)

| Metric | Side | Status | Evidence |
|:---|:---:|:---:|:---|
| `rekey_attempts` | DRONE | **NOT PRESENT** | Schema field exists, NO assignment in any file |
| `rekey_success` | DRONE | **NOT PRESENT** | Schema field exists, NO assignment |
| `rekey_failure` | DRONE | **NOT PRESENT** | Schema field exists, NO assignment |
| `rekey_interval_ms` | DRONE | **NOT PRESENT** | Schema field exists, NO assignment |
| `rekey_duration_ms` | DRONE | **NOT PRESENT** | Schema field exists, NO assignment |
| `rekey_blackout_duration_ms` | DRONE | **NOT PRESENT** | Schema field exists, NO assignment |
| `rekey_trigger_reason` | DRONE | **NOT PRESENT** | Schema field exists, NO assignment |

**Section F: 0 PRESENT, 7 NOT PRESENT**

---

## SECTION G: DATA PLANE (11)

| Metric | Side | Status | Evidence |
|:---|:---:|:---:|:---|
| `target_throughput_mbps` | DRONE | **NOT PRESENT** | Schema field exists, NO assignment |
| `achieved_throughput_mbps` | DRONE | **NOT PRESENT** | Schema field exists, NO assignment |
| `goodput_mbps` | DRONE | **NOT PRESENT** | Schema field exists, NO assignment |
| `wire_rate_mbps` | DRONE | **NOT PRESENT** | Schema field exists, NO assignment |
| `packets_sent` | DRONE | PRESENT | `metrics_aggregator.py:345` |
| `packets_received` | DRONE | PRESENT | `metrics_aggregator.py:346` |
| `packets_dropped` | DRONE | PRESENT | `metrics_aggregator.py:347` |
| `packet_loss_ratio` | DRONE | PRESENT | `metrics_aggregator.py:351` |
| `packet_delivery_ratio` | DRONE | PRESENT | `metrics_aggregator.py:352` |
| `replay_drop_count` | DRONE | **PARTIALLY PRESENT** | Stored as `drop_replay` (345), not canonical name |
| `decode_failure_count` | DRONE | **NOT PRESENT** | Schema field exists, NO assignment |

**Section G: 5 PRESENT, 1 PARTIALLY PRESENT, 5 NOT PRESENT**

---

## SECTION H: LATENCY & JITTER (10)

| Metric | Side | Status | Evidence |
|:---|:---:|:---:|:---|
| `one_way_latency_avg_ms` | DRONE | PRESENT | `metrics_aggregator.py:450` |
| `one_way_latency_p50_ms` | DRONE | PRESENT | `metrics_aggregator.py:451` |
| `one_way_latency_p95_ms` | DRONE | PRESENT | `metrics_aggregator.py:452` |
| `one_way_latency_max_ms` | DRONE | PRESENT | `metrics_aggregator.py:453` |
| `round_trip_latency_avg_ms` | DRONE | **NOT PRESENT** | Schema field exists, NO assignment |
| `round_trip_latency_p50_ms` | DRONE | **NOT PRESENT** | Schema field exists, NO assignment |
| `round_trip_latency_p95_ms` | DRONE | **NOT PRESENT** | Schema field exists, NO assignment |
| `round_trip_latency_max_ms` | DRONE | **NOT PRESENT** | Schema field exists, NO assignment |
| `jitter_avg_ms` | DRONE | **NOT PRESENT** | Schema field exists, NO assignment |
| `jitter_p95_ms` | DRONE | **NOT PRESENT** | Schema field exists, NO assignment |

**Section H: 4 PRESENT, 6 NOT PRESENT**

---

## SECTION I: MAVPROXY DRONE SIDE (17)

| Metric | Side | Status | Evidence |
|:---|:---:|:---:|:---|
| `mavproxy_drone_start_time` | DRONE | PRESENT | `mavlink_collector.py:541` |
| `mavproxy_drone_end_time` | DRONE | PRESENT | `mavlink_collector.py:542` |
| `mavproxy_drone_tx_pps` | DRONE | PRESENT | `mavlink_collector.py:543` |
| `mavproxy_drone_rx_pps` | DRONE | PRESENT | `mavlink_collector.py:544` |
| `mavproxy_drone_total_msgs_sent` | DRONE | PRESENT | `mavlink_collector.py:545` |
| `mavproxy_drone_total_msgs_received` | DRONE | PRESENT | `mavlink_collector.py:546` |
| `mavproxy_drone_msg_type_counts` | DRONE | PRESENT | `mavlink_collector.py:547` |
| `mavproxy_drone_heartbeat_interval_ms` | DRONE | PRESENT | `mavlink_collector.py:548` |
| `mavproxy_drone_heartbeat_loss_count` | DRONE | PRESENT | `mavlink_collector.py:549` |
| `mavproxy_drone_seq_gap_count` | DRONE | PRESENT | `mavlink_collector.py:550` |
| `mavproxy_drone_reconnect_count` | DRONE | **NOT PRESENT** | Schema field exists, NO assignment |
| `mavproxy_drone_cmd_sent_count` | DRONE | PRESENT | `mavlink_collector.py:551` |
| `mavproxy_drone_cmd_ack_received_count` | DRONE | PRESENT | `mavlink_collector.py:552` |
| `mavproxy_drone_cmd_ack_latency_avg_ms` | DRONE | PRESENT | `mavlink_collector.py:553` |
| `mavproxy_drone_cmd_ack_latency_p95_ms` | DRONE | PRESENT | `mavlink_collector.py:554` |
| `mavproxy_drone_stream_rate_hz` | DRONE | PRESENT | `mavlink_collector.py:555` |
| `mavproxy_drone_log_path` | DRONE | **NOT PRESENT** | Schema field exists, NO assignment |

**Section I: 15 PRESENT, 2 NOT PRESENT**

---

## SECTION J: MAVPROXY GCS SIDE (13)

| Metric | Side | Status | Evidence |
|:---|:---:|:---:|:---|
| `mavproxy_gcs_start_time` | GCS | PRESENT | `mavlink_collector.py:525` |
| `mavproxy_gcs_end_time` | GCS | PRESENT | `mavlink_collector.py:526` |
| `mavproxy_gcs_tx_pps` | GCS | PRESENT | `mavlink_collector.py:527` |
| `mavproxy_gcs_rx_pps` | GCS | PRESENT | `mavlink_collector.py:528` |
| `mavproxy_gcs_total_msgs_sent` | GCS | PRESENT | `mavlink_collector.py:529` |
| `mavproxy_gcs_total_msgs_received` | GCS | PRESENT | `mavlink_collector.py:530` |
| `mavproxy_gcs_seq_gap_count` | GCS | PRESENT | `mavlink_collector.py:534` |
| `mavproxy_gcs_reconnect_count` | GCS | **NOT PRESENT** | Schema field exists, NO assignment |
| `mavproxy_gcs_cmd_sent_count` | GCS | PRESENT | `mavlink_collector.py:535` |
| `mavproxy_gcs_cmd_ack_received_count` | GCS | PRESENT | `mavlink_collector.py:536` |
| `mavproxy_gcs_cmd_ack_latency_avg_ms` | GCS | PRESENT | `mavlink_collector.py:537` |
| `mavproxy_gcs_cmd_ack_latency_p95_ms` | GCS | PRESENT | `mavlink_collector.py:538` |
| `mavproxy_gcs_log_path` | GCS | **NOT PRESENT** | Schema field exists, NO assignment |

**Section J: 11 PRESENT, 2 NOT PRESENT**

---

## SECTION K: MAVLINK SEMANTIC INTEGRITY (10)

| Metric | Side | Status | Evidence |
|:---|:---:|:---:|:---|
| `mavlink_sysid` | DRONE | PRESENT | `mavlink_collector.py:566` |
| `mavlink_compid` | DRONE | PRESENT | `mavlink_collector.py:567` |
| `mavlink_protocol_version` | DRONE | PRESENT | `mavlink_collector.py:568` |
| `mavlink_packet_crc_error_count` | DRONE | PRESENT | `mavlink_collector.py:569` |
| `mavlink_decode_error_count` | DRONE | PRESENT | `mavlink_collector.py:570` |
| `mavlink_msg_drop_count` | DRONE | PRESENT | `mavlink_collector.py:571` |
| `mavlink_out_of_order_count` | DRONE | PRESENT | `mavlink_collector.py:572` |
| `mavlink_duplicate_count` | DRONE | PRESENT | `mavlink_collector.py:573` |
| `mavlink_message_latency_avg_ms` | DRONE | PRESENT | `mavlink_collector.py:574` |
| `mavlink_message_latency_p95_ms` | DRONE | **NOT PRESENT** | Missing from `populate_mavlink_integrity` |

**Section K: 9 PRESENT, 1 NOT PRESENT**

---

## SECTION L: FLIGHT CONTROLLER TELEMETRY (10)

| Metric | Side | Status | Evidence |
|:---|:---:|:---:|:---|
| `fc_mode` | DRONE | **NOT PRESENT** | Schema field exists, NO assignment |
| `fc_armed_state` | DRONE | **NOT PRESENT** | Schema field exists, NO assignment |
| `fc_heartbeat_age_ms` | DRONE | **NOT PRESENT** | Schema field exists, NO assignment |
| `fc_attitude_update_rate_hz` | DRONE | **NOT PRESENT** | Schema field exists, NO assignment |
| `fc_position_update_rate_hz` | DRONE | **NOT PRESENT** | Schema field exists, NO assignment |
| `fc_battery_voltage_v` | DRONE | **NOT PRESENT** | Schema field exists, NO assignment |
| `fc_battery_current_a` | DRONE | **NOT PRESENT** | Schema field exists, NO assignment |
| `fc_battery_remaining_percent` | DRONE | **NOT PRESENT** | Schema field exists, NO assignment |
| `fc_cpu_load_percent` | DRONE | **NOT PRESENT** | Schema field exists, NO assignment |
| `fc_sensor_health_flags` | DRONE | **NOT PRESENT** | Schema field exists, NO assignment |

**Section L: 0 PRESENT, 10 NOT PRESENT**

---

## SECTION M: CONTROL PLANE (7)

| Metric | Side | Status | Evidence |
|:---|:---:|:---:|:---|
| `scheduler_tick_interval_ms` | DRONE | **PARTIALLY PRESENT** | `sdrone_bench.py:406,425` calls `record_control_plane_metrics` but aggregator method existence unverified |
| `scheduler_decision_latency_ms` | DRONE | **NOT PRESENT** | Schema field exists, NO assignment |
| `scheduler_action_type` | DRONE | **PARTIALLY PRESENT** | `sdrone_bench.py:400,419` |
| `scheduler_action_reason` | DRONE | **PARTIALLY PRESENT** | `sdrone_bench.py:401,420` |
| `scheduler_cooldown_remaining_ms` | DRONE | **NOT PRESENT** | Schema field exists, NO assignment |
| `control_channel_rtt_ms` | DRONE | **NOT PRESENT** | Schema field exists, NO assignment |
| `control_channel_disconnect_count` | DRONE | **NOT PRESENT** | Schema field exists, NO assignment |

**Section M: 0 PRESENT, 3 PARTIALLY PRESENT, 4 NOT PRESENT**

---

## SECTION N: SYSTEM RESOURCES DRONE (8)

| Metric | Side | Status | Evidence |
|:---|:---:|:---:|:---|
| `cpu_usage_avg_percent` | DRONE | PRESENT | `metrics_aggregator.py:466` |
| `cpu_usage_peak_percent` | DRONE | PRESENT | `metrics_aggregator.py:467` |
| `cpu_freq_mhz` | DRONE | PRESENT | `metrics_aggregator.py:471` |
| `memory_rss_mb` | DRONE | PRESENT | `metrics_aggregator.py:472` |
| `memory_vms_mb` | DRONE | PRESENT | `metrics_aggregator.py:473` |
| `thread_count` | DRONE | PRESENT | `metrics_aggregator.py:474` |
| `temperature_c` | DRONE | PRESENT | `metrics_aggregator.py:477` |
| `thermal_throttle_events` | DRONE | **NOT PRESENT** | Schema field exists, NO assignment |

**Section N: 7 PRESENT, 1 NOT PRESENT**

---

## SECTION P: POWER & ENERGY (10)

| Metric | Side | Status | Evidence |
|:---|:---:|:---:|:---|
| `power_sensor_type` | DRONE | PRESENT | `metrics_aggregator.py:485` |
| `power_sampling_rate_hz` | DRONE | PRESENT | `metrics_aggregator.py:486` |
| `voltage_avg_v` | DRONE | **NOT PRESENT** | Schema field exists, NO assignment |
| `current_avg_a` | DRONE | **NOT PRESENT** | Schema field exists, NO assignment |
| `power_avg_w` | DRONE | PRESENT | `metrics_aggregator.py:487` |
| `power_peak_w` | DRONE | PRESENT | `metrics_aggregator.py:488` |
| `energy_total_j` | DRONE | PRESENT | `metrics_aggregator.py:489` |
| `energy_per_handshake_j` | DRONE | PRESENT | `metrics_aggregator.py:494` |
| `energy_per_rekey_j` | DRONE | **NOT PRESENT** | Schema field exists, NO assignment |
| `energy_per_second_j` | DRONE | **NOT PRESENT** | Schema field exists, NO assignment |

**Section P: 6 PRESENT, 4 NOT PRESENT**

---

## SECTION Q: OBSERVABILITY (4)

| Metric | Side | Status | Evidence |
|:---|:---:|:---:|:---|
| `metrics_sampling_rate_hz` | DRONE | PRESENT | `metrics_aggregator.py:513` |
| `trace_file_path` | DRONE | **NOT PRESENT** | Schema field exists, NO assignment |
| `power_trace_file_path` | DRONE | **NOT PRESENT** | Schema field exists, NO assignment |
| `traffic_trace_file_path` | DRONE | **NOT PRESENT** | Schema field exists, NO assignment |

**Section Q: 1 PRESENT, 3 NOT PRESENT**

---

## SECTION R: VALIDATION (6)

| Metric | Side | Status | Evidence |
|:---|:---:|:---:|:---|
| `expected_samples` | DRONE | PRESENT | `metrics_aggregator.py:519` |
| `collected_samples` | DRONE | PRESENT | `metrics_aggregator.py:520` |
| `lost_samples` | DRONE | PRESENT | `metrics_aggregator.py:521` |
| `success_rate_percent` | DRONE | PRESENT | `metrics_aggregator.py:522` |
| `benchmark_pass_fail` | DRONE | PRESENT | `metrics_aggregator.py:523` |
| `termination_reason` | DRONE | **NOT PRESENT** | Schema field exists, NO assignment |

**Section R: 5 PRESENT, 1 NOT PRESENT**

---

# FINAL SUMMARY

## TOTALS BY SECTION

| Section | PRESENT | PARTIAL | NOT PRESENT | TOTAL |
|:---|:---:|:---:|:---:|:---:|
| A. Run & Context | 18 | 0 | 2 | 20 |
| B. Crypto Identity | 8 | 0 | 5 | 13 |
| C. Lifecycle | 7 | 0 | 4 | 11 |
| D. Handshake | 7 | 0 | 1 | 8 |
| E. Crypto Primitives | 6 | 0 | 2 | 8 |
| **F. Rekey** | **0** | **0** | **7** | **7** |
| G. Data Plane | 5 | 1 | 5 | 11 |
| H. Latency/Jitter | 4 | 0 | 6 | 10 |
| I. MAVProxy Drone | 15 | 0 | 2 | 17 |
| J. MAVProxy GCS | 11 | 0 | 2 | 13 |
| K. MAVLink Integrity | 9 | 0 | 1 | 10 |
| **L. FC Telemetry** | **0** | **0** | **10** | **10** |
| M. Control Plane | 0 | 3 | 4 | 7 |
| N. System Drone | 7 | 0 | 1 | 8 |
| P. Power/Energy | 6 | 0 | 4 | 10 |
| Q. Observability | 1 | 0 | 3 | 4 |
| R. Validation | 5 | 0 | 1 | 6 |
| **TOTAL** | **109** | **4** | **60** | **163** |

---

## LIST OF NOT PRESENT METRICS (60)

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
mavproxy_drone_reconnect_count
mavproxy_drone_log_path
mavproxy_gcs_reconnect_count
mavproxy_gcs_log_path
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
scheduler_decision_latency_ms
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

## LIST OF PARTIALLY PRESENT METRICS (4)

```
replay_drop_count (stored as drop_replay, not canonical name)
scheduler_tick_interval_ms (recently added, aggregator method unverified)
scheduler_action_type (recently added, aggregator method unverified)
scheduler_action_reason (recently added, aggregator method unverified)
```

---

## CRITICAL GAPS (Entire Sections Missing)

1. **F. Rekey Metrics** — 0/7 collected
2. **L. FC Telemetry** — 0/10 collected

---

## VERIFICATION COMPLETE
