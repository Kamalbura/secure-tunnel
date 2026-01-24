# Metrics Truth Audit (Canonical vs Code Reality)

Date: 2026-01-24

Scope: Canonical metrics defined in core/metrics_schema.py. Each metric below includes source, trigger, scope, and feasibility.

Legend:
- Class: REAL (runtime), DERIVED (computed from runtime), CONDITIONAL (requires injected data)
- Scope: Per-suite (unless explicitly noted)

## A. Run & Context Metrics
| Metric | Present | Source (file:function:line) | Trigger | Scope | Class | Can be made REAL? | If NO → Why |
| --- | --- | --- | --- | --- | --- | --- | --- |
| run_id | YES | core/metrics_aggregator.py:start_suite (L161) | suite start | per-suite | REAL | YES |  |
| suite_id | YES | core/metrics_aggregator.py:start_suite (L161) | suite start | per-suite | REAL | YES |  |
| suite_index | YES | core/metrics_aggregator.py:start_suite (L161) | suite start | per-suite | REAL | YES |  |
| git_commit_hash | YES | core/metrics_aggregator.py:start_suite (L161); core/metrics_collectors.py:EnvironmentCollector.collect (L92) | env read | per-suite | REAL | YES |  |
| git_dirty_flag | YES | core/metrics_aggregator.py:start_suite (L161); core/metrics_collectors.py:EnvironmentCollector.collect (L92) | env read | per-suite | REAL | YES |  |
| gcs_hostname | YES | core/metrics_aggregator.py:_merge_peer_data (L647); sscheduler/sgcs_bench.py:get_info (L188) | control RPC | per-suite | REAL | YES |  |
| drone_hostname | YES | core/metrics_aggregator.py:start_suite (L161); core/metrics_collectors.py:EnvironmentCollector.collect (L92) | env read | per-suite | REAL | YES |  |
| gcs_ip | YES | core/metrics_aggregator.py:_merge_peer_data (L647); sscheduler/sgcs_bench.py:get_info (L188) | control RPC | per-suite | REAL | YES |  |
| drone_ip | YES | core/metrics_aggregator.py:start_suite (L161) | env read | per-suite | REAL | YES |  |
| python_env_gcs | YES | core/metrics_aggregator.py:_merge_peer_data (L647); sscheduler/sgcs_bench.py:get_info (L188) | control RPC | per-suite | REAL | YES |  |
| python_env_drone | YES | core/metrics_aggregator.py:start_suite (L161) | env read | per-suite | REAL | YES |  |
| liboqs_version | YES | core/metrics_aggregator.py:start_suite (L161); core/metrics_collectors.py:EnvironmentCollector.collect (L92) | env read | per-suite | REAL | YES |  |
| kernel_version_gcs | YES | core/metrics_aggregator.py:_merge_peer_data (L647); sscheduler/sgcs_bench.py:get_info (L188) | control RPC | per-suite | REAL | YES |  |
| kernel_version_drone | YES | core/metrics_aggregator.py:start_suite (L161) | env read | per-suite | REAL | YES |  |
| clock_offset_ms | YES | core/metrics_aggregator.py:set_clock_offset (L149) | clock sync | per-suite | CONDITIONAL | YES |  |
| clock_offset_method | YES | core/metrics_aggregator.py:set_clock_offset (L149) | clock sync | per-suite | CONDITIONAL | YES |  |
| run_start_time_wall | YES | core/metrics_aggregator.py:start_suite (L161) | suite start | per-suite | REAL | YES |  |
| run_end_time_wall | YES | core/metrics_aggregator.py:finalize_suite (L492) | suite finalize | per-suite | REAL | YES |  |
| run_start_time_mono | YES | core/metrics_aggregator.py:start_suite (L161) | suite start | per-suite | REAL | YES |  |
| run_end_time_mono | YES | core/metrics_aggregator.py:finalize_suite (L492) | suite finalize | per-suite | REAL | YES |  |

## B. Suite Crypto Identity
| Metric | Present | Source (file:function:line) | Trigger | Scope | Class | Can be made REAL? | If NO → Why |
| --- | --- | --- | --- | --- | --- | --- | --- |
| kem_algorithm | YES | core/metrics_aggregator.py:start_suite (L161) | suite config | per-suite | REAL | YES |  |
| kem_family | YES | core/metrics_aggregator.py:start_suite (L161) | derived from kem_algorithm | per-suite | DERIVED | YES |  |
| kem_nist_level | YES | core/metrics_aggregator.py:start_suite (L161) | suite config | per-suite | REAL | YES |  |
| sig_algorithm | YES | core/metrics_aggregator.py:start_suite (L161) | suite config | per-suite | REAL | YES |  |
| sig_family | YES | core/metrics_aggregator.py:start_suite (L161) | derived from sig_algorithm | per-suite | DERIVED | YES |  |
| sig_nist_level | YES | core/metrics_aggregator.py:start_suite (L161) | suite config | per-suite | REAL | YES |  |
| aead_algorithm | YES | core/metrics_aggregator.py:start_suite (L161) | suite config | per-suite | REAL | YES |  |
| suite_security_level | YES | core/metrics_aggregator.py:start_suite (L161) | suite config | per-suite | REAL | YES |  |

## C. Suite Lifecycle Timeline
| Metric | Present | Source (file:function:line) | Trigger | Scope | Class | Can be made REAL? | If NO → Why |
| --- | --- | --- | --- | --- | --- | --- | --- |
| suite_selected_time | YES | core/metrics_aggregator.py:start_suite (L161) | suite start | per-suite | REAL | YES |  |
| suite_activated_time | YES | core/metrics_aggregator.py:record_handshake_end (L261) | handshake end | per-suite | REAL | YES |  |
| suite_deactivated_time | YES | core/metrics_aggregator.py:finalize_suite (L492) | suite finalize | per-suite | REAL | YES |  |
| suite_total_duration_ms | YES | core/metrics_aggregator.py:finalize_suite (L492) | derived from monotonic | per-suite | DERIVED | YES |  |
| suite_active_duration_ms | YES | core/metrics_aggregator.py:finalize_suite (L492) | derived from monotonic | per-suite | DERIVED | YES |  |

## D. Handshake Metrics
| Metric | Present | Source (file:function:line) | Trigger | Scope | Class | Can be made REAL? | If NO → Why |
| --- | --- | --- | --- | --- | --- | --- | --- |
| handshake_start_time_drone | YES | core/metrics_aggregator.py:record_handshake_start (L252) | handshake start | per-suite | REAL | YES |  |
| handshake_end_time_drone | YES | core/metrics_aggregator.py:record_handshake_end (L261) | handshake end | per-suite | REAL | YES |  |
| handshake_total_duration_ms | YES | core/metrics_aggregator.py:record_handshake_end (L261) | derived from monotonic | per-suite | DERIVED | YES |  |
| handshake_success | YES | core/metrics_aggregator.py:record_handshake_end (L261); sscheduler/sdrone_bench.py:_activate_suite (L453) | handshake status | per-suite | REAL | YES |  |
| handshake_failure_reason | YES | core/metrics_aggregator.py:record_handshake_end (L261); sscheduler/sdrone_bench.py:_activate_suite (L453) | handshake status | per-suite | REAL | YES |  |

## E. Crypto Primitive Breakdown
| Metric | Present | Source (file:function:line) | Trigger | Scope | Class | Can be made REAL? | If NO → Why |
| --- | --- | --- | --- | --- | --- | --- | --- |
| kem_keygen_time_ms | YES | core/handshake.py:build_server_hello (L115); core/metrics_aggregator.py:record_crypto_primitives (L296) | keygen | per-suite | REAL | YES |  |
| kem_encapsulation_time_ms | YES | core/handshake.py:client_encapsulate (L314); core/metrics_aggregator.py:record_crypto_primitives (L296) | encapsulate | per-suite | REAL | YES |  |
| kem_decapsulation_time_ms | YES | core/handshake.py:server_decapsulate (L345); core/metrics_aggregator.py:record_crypto_primitives (L296) | decapsulate | per-suite | REAL | YES |  |
| signature_sign_time_ms | YES | core/handshake.py:build_server_hello (L115); core/metrics_aggregator.py:record_crypto_primitives (L296) | signature sign | per-suite | REAL | YES |  |
| signature_verify_time_ms | YES | core/handshake.py:parse_and_verify_server_hello (L199); core/metrics_aggregator.py:record_crypto_primitives (L296) | signature verify | per-suite | REAL | YES |  |
| total_crypto_time_ms | YES | core/metrics_aggregator.py:record_crypto_primitives (L296) | derived sum | per-suite | DERIVED | YES |  |
| kem_keygen_ns | YES | core/handshake.py:build_server_hello (L115); core/metrics_aggregator.py:record_crypto_primitives (L296) | keygen | per-suite | REAL | YES |  |
| kem_encaps_ns | YES | core/handshake.py:client_encapsulate (L314); core/metrics_aggregator.py:record_crypto_primitives (L296) | encapsulate | per-suite | REAL | YES |  |
| kem_decaps_ns | YES | core/handshake.py:server_decapsulate (L345); core/metrics_aggregator.py:record_crypto_primitives (L296) | decapsulate | per-suite | REAL | YES |  |
| sig_sign_ns | YES | core/handshake.py:build_server_hello (L115); core/metrics_aggregator.py:record_crypto_primitives (L296) | signature sign | per-suite | REAL | YES |  |
| sig_verify_ns | YES | core/handshake.py:parse_and_verify_server_hello (L199); core/metrics_aggregator.py:record_crypto_primitives (L296) | signature verify | per-suite | REAL | YES |  |
| pub_key_size_bytes | YES | core/handshake.py:build_server_hello (L115); core/metrics_aggregator.py:record_crypto_primitives (L296) | keygen | per-suite | REAL | YES |  |
| ciphertext_size_bytes | YES | core/handshake.py:client_encapsulate (L314); core/metrics_aggregator.py:record_crypto_primitives (L296) | encapsulate | per-suite | REAL | YES |  |
| sig_size_bytes | YES | core/handshake.py:build_server_hello (L115); core/metrics_aggregator.py:record_crypto_primitives (L296) | signature sign | per-suite | REAL | YES |  |
| shared_secret_size_bytes | YES | core/handshake.py:client_encapsulate (L314); core/metrics_aggregator.py:record_crypto_primitives (L296) | encapsulate/decapsulate | per-suite | REAL | YES |  |

## F. Rekey Metrics
| Metric | Present | Source (file:function:line) | Trigger | Scope | Class | Can be made REAL? | If NO → Why |
| --- | --- | --- | --- | --- | --- | --- | --- |
| rekey_attempts | YES | core/metrics_aggregator.py:record_data_plane_metrics (L355); core/async_proxy.py:ProxyCounters (L70) | rekey events | per-suite | DERIVED | YES |  |
| rekey_success | YES | core/metrics_aggregator.py:record_data_plane_metrics (L355); core/async_proxy.py:ProxyCounters.to_dict (L201) | rekey success | per-suite | REAL | YES |  |
| rekey_failure | YES | core/metrics_aggregator.py:record_data_plane_metrics (L355); core/async_proxy.py:ProxyCounters.to_dict (L201) | rekey failure | per-suite | REAL | YES |  |
| rekey_interval_ms | YES | core/metrics_aggregator.py:record_data_plane_metrics (L355); core/async_proxy.py:ProxyCounters (L70) | rekey interval | per-suite | REAL | YES |  |
| rekey_duration_ms | YES | core/metrics_aggregator.py:record_data_plane_metrics (L355); core/async_proxy.py:ProxyCounters (L70) | rekey end | per-suite | REAL | YES |  |
| rekey_blackout_duration_ms | YES | core/metrics_aggregator.py:record_data_plane_metrics (L355); core/async_proxy.py:ProxyCounters (L70) | rekey blackout | per-suite | REAL | YES |  |
| rekey_trigger_reason | YES | core/metrics_aggregator.py:record_data_plane_metrics (L355); core/async_proxy.py:ProxyCounters (L70) | rekey trigger | per-suite | REAL | YES |  |

## G. Data Plane
| Metric | Present | Source (file:function:line) | Trigger | Scope | Class | Can be made REAL? | If NO → Why |
| --- | --- | --- | --- | --- | --- | --- | --- |
| achieved_throughput_mbps | YES | core/metrics_aggregator.py:finalize_suite (L492) | derived from counters | per-suite | DERIVED | YES |  |
| goodput_mbps | YES | core/metrics_aggregator.py:finalize_suite (L492) | derived from counters | per-suite | DERIVED | YES |  |
| wire_rate_mbps | YES | core/metrics_aggregator.py:finalize_suite (L492) | derived from counters | per-suite | DERIVED | YES |  |
| packets_sent | YES | core/metrics_aggregator.py:record_data_plane_metrics (L355) | proxy counters | per-suite | REAL | YES |  |
| packets_received | YES | core/metrics_aggregator.py:record_data_plane_metrics (L355) | proxy counters | per-suite | REAL | YES |  |
| packets_dropped | YES | core/metrics_aggregator.py:record_data_plane_metrics (L355) | derived from drop counters | per-suite | DERIVED | YES |  |
| packet_loss_ratio | YES | core/metrics_aggregator.py:record_data_plane_metrics (L355) | derived from counters | per-suite | DERIVED | YES |  |
| packet_delivery_ratio | YES | core/metrics_aggregator.py:record_data_plane_metrics (L355) | derived from counters | per-suite | DERIVED | YES |  |
| replay_drop_count | YES | core/metrics_aggregator.py:record_data_plane_metrics (L355); core/async_proxy.py:ProxyCounters.to_dict (L201) | replay window | per-suite | REAL | YES |  |
| decode_failure_count | YES | core/metrics_aggregator.py:record_data_plane_metrics (L355) | derived from drop counters | per-suite | DERIVED | YES |  |
| ptx_in | YES | core/metrics_aggregator.py:record_data_plane_metrics (L355); core/async_proxy.py:ProxyCounters (L70) | proxy counters | per-suite | REAL | YES |  |
| ptx_out | YES | core/metrics_aggregator.py:record_data_plane_metrics (L355); core/async_proxy.py:ProxyCounters (L70) | proxy counters | per-suite | REAL | YES |  |
| enc_in | YES | core/metrics_aggregator.py:record_data_plane_metrics (L355); core/async_proxy.py:ProxyCounters (L70) | proxy counters | per-suite | REAL | YES |  |
| enc_out | YES | core/metrics_aggregator.py:record_data_plane_metrics (L355); core/async_proxy.py:ProxyCounters (L70) | proxy counters | per-suite | REAL | YES |  |
| drop_replay | YES | core/metrics_aggregator.py:record_data_plane_metrics (L355); core/async_proxy.py:ProxyCounters (L70) | replay window | per-suite | REAL | YES |  |
| drop_auth | YES | core/metrics_aggregator.py:record_data_plane_metrics (L355); core/async_proxy.py:ProxyCounters (L70) | AEAD auth fail | per-suite | REAL | YES |  |
| drop_header | YES | core/metrics_aggregator.py:record_data_plane_metrics (L355); core/async_proxy.py:ProxyCounters (L70) | header parse | per-suite | REAL | YES |  |
| bytes_sent | YES | core/metrics_aggregator.py:record_data_plane_metrics (L355) | proxy counters | per-suite | REAL | YES |  |
| bytes_received | YES | core/metrics_aggregator.py:record_data_plane_metrics (L355) | proxy counters | per-suite | REAL | YES |  |
| aead_encrypt_avg_ns | YES | core/metrics_aggregator.py:record_data_plane_metrics (L355); core/async_proxy.py:ProxyCounters (L70) | AEAD encrypt | per-suite | DERIVED | YES |  |
| aead_decrypt_avg_ns | YES | core/metrics_aggregator.py:record_data_plane_metrics (L355); core/async_proxy.py:ProxyCounters (L70) | AEAD decrypt | per-suite | DERIVED | YES |  |
| aead_encrypt_count | YES | core/metrics_aggregator.py:record_data_plane_metrics (L355); core/async_proxy.py:ProxyCounters (L70) | AEAD encrypt | per-suite | REAL | YES |  |
| aead_decrypt_count | YES | core/metrics_aggregator.py:record_data_plane_metrics (L355); core/async_proxy.py:ProxyCounters (L70) | AEAD decrypt | per-suite | REAL | YES |  |

## I. MAVProxy Drone Metrics
| Metric | Present | Source (file:function:line) | Trigger | Scope | Class | Can be made REAL? | If NO → Why |
| --- | --- | --- | --- | --- | --- | --- | --- |
| mavproxy_drone_start_time | YES | core/mavlink_collector.py:get_metrics (L532); core/mavlink_collector.py:populate_schema_metrics (L637) | MAVLink sniff start | per-suite | REAL | YES |  |
| mavproxy_drone_end_time | YES | core/mavlink_collector.py:get_metrics (L532); core/mavlink_collector.py:populate_schema_metrics (L637) | MAVLink sniff end | per-suite | REAL | YES |  |
| mavproxy_drone_tx_pps | YES | core/mavlink_collector.py:get_metrics (L532) | MAVLink sniff | per-suite | DERIVED | YES |  |
| mavproxy_drone_rx_pps | YES | core/mavlink_collector.py:get_metrics (L532) | MAVLink sniff | per-suite | DERIVED | YES |  |
| mavproxy_drone_total_msgs_sent | YES | core/mavlink_collector.py:get_metrics (L532) | MAVLink sniff | per-suite | REAL | YES |  |
| mavproxy_drone_total_msgs_received | YES | core/mavlink_collector.py:get_metrics (L532) | MAVLink sniff | per-suite | REAL | YES |  |
| mavproxy_drone_msg_type_counts | YES | core/mavlink_collector.py:get_metrics (L532) | MAVLink sniff | per-suite | REAL | YES |  |
| mavproxy_drone_heartbeat_interval_ms | YES | core/mavlink_collector.py:get_metrics (L532) | heartbeat | per-suite | DERIVED | YES |  |
| mavproxy_drone_heartbeat_loss_count | YES | core/mavlink_collector.py:get_metrics (L532) | heartbeat | per-suite | REAL | YES |  |
| mavproxy_drone_seq_gap_count | YES | core/mavlink_collector.py:get_metrics (L532) | sequence tracking | per-suite | REAL | YES |  |
| mavproxy_drone_cmd_sent_count | YES | core/mavlink_collector.py:get_metrics (L532) | command tracking | per-suite | REAL | YES |  |
| mavproxy_drone_cmd_ack_received_count | YES | core/mavlink_collector.py:get_metrics (L532) | command tracking | per-suite | REAL | YES |  |
| mavproxy_drone_cmd_ack_latency_avg_ms | YES | core/mavlink_collector.py:get_metrics (L532) | command tracking | per-suite | DERIVED | YES |  |
| mavproxy_drone_cmd_ack_latency_p95_ms | YES | core/mavlink_collector.py:get_metrics (L532) | command tracking | per-suite | DERIVED | YES |  |
| mavproxy_drone_stream_rate_hz | YES | core/mavlink_collector.py:get_metrics (L532) | MAVLink sniff | per-suite | DERIVED | YES |  |

## J. MAVProxy GCS Metrics
| Metric | Present | Source (file:function:line) | Trigger | Scope | Class | Can be made REAL? | If NO → Why |
| --- | --- | --- | --- | --- | --- | --- | --- |
| mavproxy_gcs_total_msgs_received | YES | sscheduler/sgcs_bench.py:GcsMavLinkCollector.stop (L396); core/metrics_aggregator.py:_merge_peer_data (L647) | MAVLink sniff | per-suite | REAL | YES |  |
| mavproxy_gcs_seq_gap_count | YES | sscheduler/sgcs_bench.py:GcsMavLinkCollector.stop (L396); core/metrics_aggregator.py:_merge_peer_data (L647) | sequence tracking | per-suite | REAL | YES |  |

## K. MAVLink Integrity
| Metric | Present | Source (file:function:line) | Trigger | Scope | Class | Can be made REAL? | If NO → Why |
| --- | --- | --- | --- | --- | --- | --- | --- |
| mavlink_sysid | YES | core/mavlink_collector.py:populate_mavlink_integrity (L667) | MAVLink sniff | per-suite | REAL | YES |  |
| mavlink_compid | YES | core/mavlink_collector.py:populate_mavlink_integrity (L667) | MAVLink sniff | per-suite | REAL | YES |  |
| mavlink_protocol_version | YES | core/mavlink_collector.py:populate_mavlink_integrity (L667) | MAVLink sniff | per-suite | REAL | YES |  |
| mavlink_packet_crc_error_count | YES | core/mavlink_collector.py:populate_mavlink_integrity (L667) | MAVLink parse | per-suite | REAL | YES |  |
| mavlink_decode_error_count | YES | core/mavlink_collector.py:populate_mavlink_integrity (L667) | MAVLink parse | per-suite | REAL | YES |  |
| mavlink_msg_drop_count | YES | core/mavlink_collector.py:populate_mavlink_integrity (L667) | MAVLink parse | per-suite | REAL | YES |  |
| mavlink_out_of_order_count | YES | core/mavlink_collector.py:populate_mavlink_integrity (L667) | sequence tracking | per-suite | REAL | YES |  |
| mavlink_duplicate_count | YES | core/mavlink_collector.py:populate_mavlink_integrity (L667) | sequence tracking | per-suite | REAL | YES |  |
| mavlink_message_latency_avg_ms | YES | core/mavlink_collector.py:get_metrics (L532) | timestamped messages | per-suite | CONDITIONAL | YES |  |

## L. Flight Controller Telemetry
| Metric | Present | Source (file:function:line) | Trigger | Scope | Class | Can be made REAL? | If NO → Why |
| --- | --- | --- | --- | --- | --- | --- | --- |
| fc_mode | YES | core/mavlink_collector.py:get_flight_controller_metrics (L686) | MAVLink telemetry | per-suite | REAL | YES |  |
| fc_armed_state | YES | core/mavlink_collector.py:get_flight_controller_metrics (L686) | MAVLink telemetry | per-suite | REAL | YES |  |
| fc_heartbeat_age_ms | YES | core/mavlink_collector.py:get_flight_controller_metrics (L686) | MAVLink telemetry | per-suite | DERIVED | YES |  |
| fc_attitude_update_rate_hz | YES | core/mavlink_collector.py:get_flight_controller_metrics (L686) | MAVLink telemetry | per-suite | DERIVED | YES |  |
| fc_position_update_rate_hz | YES | core/mavlink_collector.py:get_flight_controller_metrics (L686) | MAVLink telemetry | per-suite | DERIVED | YES |  |
| fc_battery_voltage_v | YES | core/mavlink_collector.py:get_flight_controller_metrics (L686) | MAVLink telemetry | per-suite | REAL | YES |  |
| fc_battery_current_a | YES | core/mavlink_collector.py:get_flight_controller_metrics (L686) | MAVLink telemetry | per-suite | REAL | YES |  |
| fc_battery_remaining_percent | YES | core/mavlink_collector.py:get_flight_controller_metrics (L686) | MAVLink telemetry | per-suite | REAL | YES |  |
| fc_cpu_load_percent | YES | core/mavlink_collector.py:get_flight_controller_metrics (L686) | MAVLink telemetry | per-suite | REAL | YES |  |
| fc_sensor_health_flags | YES | core/mavlink_collector.py:get_flight_controller_metrics (L686) | MAVLink telemetry | per-suite | REAL | YES |  |

## M. Control Plane Metrics
| Metric | Present | Source (file:function:line) | Trigger | Scope | Class | Can be made REAL? | If NO → Why |
| --- | --- | --- | --- | --- | --- | --- | --- |
| scheduler_tick_interval_ms | YES | core/metrics_aggregator.py:record_control_plane_metrics (L422); sscheduler/sdrone_bench.py:_activate_suite (L453) | scheduler config | per-suite | REAL | YES |  |
| policy_name | YES | core/metrics_aggregator.py:record_control_plane_metrics (L422); sscheduler/sdrone_bench.py:_activate_suite (L453) | scheduler state | per-suite | REAL | YES |  |
| policy_state | YES | core/metrics_aggregator.py:record_control_plane_metrics (L422); sscheduler/sdrone_bench.py:_activate_suite (L453) | scheduler state | per-suite | REAL | YES |  |
| policy_suite_index | YES | core/metrics_aggregator.py:record_control_plane_metrics (L422); sscheduler/sdrone_bench.py:_activate_suite (L453) | scheduler state | per-suite | REAL | YES |  |
| policy_total_suites | YES | core/metrics_aggregator.py:record_control_plane_metrics (L422); sscheduler/sdrone_bench.py:_activate_suite (L453) | scheduler state | per-suite | REAL | YES |  |

## N. System Resources — Drone
| Metric | Present | Source (file:function:line) | Trigger | Scope | Class | Can be made REAL? | If NO → Why |
| --- | --- | --- | --- | --- | --- | --- | --- |
| cpu_usage_avg_percent | YES | core/metrics_collectors.py:SystemCollector.collect (L211); core/metrics_aggregator.py:finalize_suite (L492) | periodic sampling | per-suite | DERIVED | YES |  |
| cpu_usage_peak_percent | YES | core/metrics_collectors.py:SystemCollector.collect (L211); core/metrics_aggregator.py:finalize_suite (L492) | periodic sampling | per-suite | DERIVED | YES |  |
| cpu_freq_mhz | YES | core/metrics_collectors.py:SystemCollector.collect (L211); core/metrics_aggregator.py:finalize_suite (L492) | periodic sampling | per-suite | REAL | YES |  |
| memory_rss_mb | YES | core/metrics_collectors.py:SystemCollector.collect (L211); core/metrics_aggregator.py:finalize_suite (L492) | periodic sampling | per-suite | REAL | YES |  |
| memory_vms_mb | YES | core/metrics_collectors.py:SystemCollector.collect (L211); core/metrics_aggregator.py:finalize_suite (L492) | periodic sampling | per-suite | REAL | YES |  |
| thread_count | YES | core/metrics_collectors.py:SystemCollector.collect (L211); core/metrics_aggregator.py:finalize_suite (L492) | periodic sampling | per-suite | REAL | YES |  |
| temperature_c | YES | core/metrics_collectors.py:SystemCollector.collect (L211); core/metrics_aggregator.py:finalize_suite (L492) | periodic sampling | per-suite | REAL | YES |  |
| uptime_s | YES | core/metrics_collectors.py:SystemCollector.collect (L211); core/metrics_aggregator.py:finalize_suite (L492) | periodic sampling | per-suite | REAL | YES |  |
| load_avg_1m | YES | core/metrics_collectors.py:SystemCollector.collect (L211); core/metrics_aggregator.py:finalize_suite (L492) | periodic sampling | per-suite | REAL | YES |  |
| load_avg_5m | YES | core/metrics_collectors.py:SystemCollector.collect (L211); core/metrics_aggregator.py:finalize_suite (L492) | periodic sampling | per-suite | REAL | YES |  |
| load_avg_15m | YES | core/metrics_collectors.py:SystemCollector.collect (L211); core/metrics_aggregator.py:finalize_suite (L492) | periodic sampling | per-suite | REAL | YES |  |

## P. Power & Energy (Drone)
| Metric | Present | Source (file:function:line) | Trigger | Scope | Class | Can be made REAL? | If NO → Why |
| --- | --- | --- | --- | --- | --- | --- | --- |
| power_sensor_type | YES | core/metrics_aggregator.py:finalize_suite (L492); core/metrics_collectors.py:PowerCollector.collect (L451) | power sampling | per-suite | REAL | YES |  |
| power_sampling_rate_hz | YES | core/metrics_aggregator.py:start_suite (L161) | power sampling | per-suite | REAL | YES |  |
| voltage_avg_v | YES | core/metrics_collectors.py:PowerCollector.get_energy_stats (L537); core/metrics_aggregator.py:finalize_suite (L492) | power sampling | per-suite | DERIVED | YES |  |
| current_avg_a | YES | core/metrics_collectors.py:PowerCollector.get_energy_stats (L537); core/metrics_aggregator.py:finalize_suite (L492) | power sampling | per-suite | DERIVED | YES |  |
| power_avg_w | YES | core/metrics_collectors.py:PowerCollector.get_energy_stats (L537); core/metrics_aggregator.py:finalize_suite (L492) | power sampling | per-suite | DERIVED | YES |  |
| power_peak_w | YES | core/metrics_collectors.py:PowerCollector.get_energy_stats (L537); core/metrics_aggregator.py:finalize_suite (L492) | power sampling | per-suite | DERIVED | YES |  |
| energy_total_j | YES | core/metrics_collectors.py:PowerCollector.get_energy_stats (L537); core/metrics_aggregator.py:finalize_suite (L492) | power sampling | per-suite | DERIVED | YES |  |
| energy_per_handshake_j | YES | core/metrics_aggregator.py:finalize_suite (L492) | derived from power_avg_w + handshake duration | per-suite | DERIVED | YES |  |

## Q. Observability & Logging
| Metric | Present | Source (file:function:line) | Trigger | Scope | Class | Can be made REAL? | If NO → Why |
| --- | --- | --- | --- | --- | --- | --- | --- |
| log_sample_count | YES | core/metrics_aggregator.py:finalize_suite (L492) | background sampling | per-suite | REAL | YES |  |
| metrics_sampling_rate_hz | YES | core/metrics_aggregator.py:finalize_suite (L492) | background sampling | per-suite | REAL | YES |  |
| collection_start_time | YES | core/metrics_aggregator.py:finalize_suite (L492) | suite start | per-suite | REAL | YES |  |
| collection_end_time | YES | core/metrics_aggregator.py:finalize_suite (L492) | suite finalize | per-suite | REAL | YES |  |
| collection_duration_ms | YES | core/metrics_aggregator.py:finalize_suite (L492) | derived | per-suite | DERIVED | YES |  |

## R. Validation & Integrity
| Metric | Present | Source (file:function:line) | Trigger | Scope | Class | Can be made REAL? | If NO → Why |
| --- | --- | --- | --- | --- | --- | --- | --- |
| expected_samples | YES | core/metrics_aggregator.py:finalize_suite (L492) | derived | per-suite | DERIVED | YES |  |
| collected_samples | YES | core/metrics_aggregator.py:finalize_suite (L492) | background sampling | per-suite | REAL | YES |  |
| lost_samples | YES | core/metrics_aggregator.py:finalize_suite (L492) | derived | per-suite | DERIVED | YES |  |
| success_rate_percent | YES | core/metrics_aggregator.py:finalize_suite (L492) | derived from handshake_success | per-suite | DERIVED | YES |  |
| benchmark_pass_fail | YES | core/metrics_aggregator.py:finalize_suite (L492) | derived from handshake_success | per-suite | DERIVED | YES |  |
