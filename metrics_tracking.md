# Metrics Tracking (Implemented Sources)

This list reflects metrics wired to concrete sources in code.

## Run Context
- clock_offset_ms (source: sscheduler/sdrone_bench.py → core.clock_sync.ClockSync)
- clock_offset_method (source: sscheduler/sdrone_bench.py)

## Data Plane / Proxy Counters
- ptx_bytes_in/ptx_bytes_out (source: core/async_proxy.py)
- enc_bytes_in/enc_bytes_out (source: core/async_proxy.py)
- bytes_in/bytes_out (alias to enc_bytes_*; source: core/async_proxy.py)
- goodput_mbps / wire_rate_mbps / achieved_throughput_mbps (source: core/metrics_aggregator.py)

## Rekey Metrics
- rekey_attempts / rekey_success / rekey_failure (source: core/async_proxy.ProxyCounters)
- rekey_duration_ms (source: core/async_proxy.ProxyCounters.last_rekey_ms)

## Control Plane
- policy_name / policy_state / policy_suite_index / policy_total_suites
  (source: sscheduler/sdrone_bench.py → core/metrics_aggregator.record_control_plane_metrics)
- scheduler_action_type / scheduler_action_reason
  (source: sscheduler/sdrone_bench.py → BenchmarkPolicy output)
- scheduler_tick_interval_ms (source: sscheduler/sdrone_bench.py args.interval)

## Flight Controller Telemetry (Drone)
- fc_altitude_m
- fc_battery_remaining_percent
  (source: core/mavlink_collector.get_chronos_data → core/metrics_aggregator.finalize_suite)
