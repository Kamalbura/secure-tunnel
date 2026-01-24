from typing import List, Dict, Optional
from pydantic import BaseModel, Field

# =============================================================================
# FORENSIC DASHBOARD SCHEMA
# Mirrors metrics_schema.py (Canonical) with strict enforcement
# =============================================================================

class CanonicalMetrics(BaseModel):
    """
    The definitive 163-field schema for Secure-Tunnel Benchmarks.
    Source Authority: dashboard_architecture.md v2.0
    """

    # --- A. RUN & CONTEXT (20) ---
    run_id: str = Field(..., description="UUID of the run")
    suite_id: str = Field(..., description="Canonical suite ID string")
    suite_index: int = Field(..., description="0-based index of suite in run")
    git_commit_hash: str
    git_dirty_flag: bool
    gcs_hostname: str
    drone_hostname: str
    gcs_ip: str
    drone_ip: str
    python_env_gcs: str
    python_env_drone: str
    liboqs_version: str
    kernel_version_gcs: str
    kernel_version_drone: str
    clock_offset_ms: Optional[float] = 0.0  # PRUNED
    clock_offset_method: Optional[str] = "" # PRUNED
    run_start_time_wall: str
    run_end_time_wall: str
    run_start_time_mono: float
    run_end_time_mono: float

    # --- B. CRYPTO IDENTITY (13) ---
    kem_algorithm: str
    kem_family: str
    kem_parameter_set: Optional[str] = "" # PRUNED
    kem_nist_level: str # L1-5
    sig_algorithm: str
    sig_family: str
    sig_parameter_set: Optional[str] = "" # PRUNED
    sig_nist_level: str # L1-5
    aead_algorithm: str
    aead_mode: Optional[str] = "" # PRUNED
    suite_security_level: str # L1-5
    suite_tier: Optional[str] = "" # PRUNED
    suite_order_index: Optional[int] = 0 # PRUNED

    # --- C. LIFECYCLE (11) ---
    suite_selected_time: float
    suite_activated_time: float
    suite_traffic_start_time: float
    suite_traffic_end_time: float
    suite_rekey_start_time: Optional[float] = 0.0 # PRUNED
    suite_rekey_end_time: Optional[float] = 0.0 # PRUNED
    suite_deactivated_time: float
    suite_total_duration_ms: float
    suite_active_duration_ms: float
    suite_blackout_count: Optional[int] = 0 # PRUNED
    suite_blackout_total_ms: Optional[float] = 0.0 # PRUNED

    # --- D. HANDSHAKE (8) ---
    handshake_start_time_drone: float
    handshake_end_time_drone: float
    handshake_start_time_gcs: float
    handshake_end_time_gcs: float
    handshake_total_duration_ms: float
    handshake_rtt_ms: Optional[float] = 0.0 # PRUNED
    handshake_success: bool
    handshake_failure_reason: str

    # --- E. CRYPTO PRIMITIVES (8) ---
    # Marked CONDITIONAL in Arch - Use Optional
    kem_keygen_time_ms: Optional[float] = 0.0
    kem_encapsulation_time_ms: Optional[float] = 0.0
    kem_decapsulation_time_ms: Optional[float] = 0.0
    signature_sign_time_ms: Optional[float] = 0.0
    signature_verify_time_ms: Optional[float] = 0.0
    hkdf_extract_time_ms: Optional[float] = 0.0 # PRUNED
    hkdf_expand_time_ms: Optional[float] = 0.0 # PRUNED
    total_crypto_time_ms: float

    # --- F. REKEY METRICS (7) ---
    # All PRUNED/FORBIDDEN - Optional/0
    rekey_attempts: Optional[int] = 0
    rekey_success: Optional[bool] = False
    rekey_failure: Optional[bool] = False
    rekey_interval_ms: Optional[float] = 0.0
    rekey_duration_ms: Optional[float] = 0.0
    rekey_blackout_duration_ms: Optional[float] = 0.0
    rekey_trigger_reason: Optional[str] = ""

    # --- G. DATA PLANE (11) ---
    target_throughput_mbps: Optional[float] = 0.0 # PRUNED
    achieved_throughput_mbps: Optional[float] = 0.0 # PRUNED
    goodput_mbps: Optional[float] = 0.0 # PRUNED
    wire_rate_mbps: Optional[float] = 0.0 # PRUNED
    packets_sent: int
    packets_received: int
    packets_dropped: int
    packet_loss_ratio: float
    packet_delivery_ratio: float
    replay_drop_count: Optional[int] = 0 # CONDITIONAL
    decode_failure_count: Optional[int] = 0 # PRUNED

    # --- H. LATENCY & JITTER (10) ---
    one_way_latency_avg_ms: float
    one_way_latency_p50_ms: float
    one_way_latency_p95_ms: float
    one_way_latency_max_ms: float
    round_trip_latency_avg_ms: Optional[float] = 0.0 # PRUNED
    round_trip_latency_p50_ms: Optional[float] = 0.0 # PRUNED
    round_trip_latency_p95_ms: Optional[float] = 0.0 # PRUNED
    round_trip_latency_max_ms: Optional[float] = 0.0 # PRUNED
    jitter_avg_ms: Optional[float] = 0.0 # PRUNED
    jitter_p95_ms: Optional[float] = 0.0 # PRUNED

    # --- I. MAVPROXY DRONE (17) ---
    mavproxy_drone_start_time: float
    mavproxy_drone_end_time: float
    mavproxy_drone_tx_pps: float
    mavproxy_drone_rx_pps: float
    mavproxy_drone_total_msgs_sent: int
    mavproxy_drone_total_msgs_received: int
    mavproxy_drone_msg_type_counts: Dict[str, int]
    mavproxy_drone_heartbeat_interval_ms: float
    mavproxy_drone_heartbeat_loss_count: int
    mavproxy_drone_seq_gap_count: int
    mavproxy_drone_reconnect_count: Optional[int] = 0 # PRUNED
    mavproxy_drone_cmd_sent_count: int
    mavproxy_drone_cmd_ack_received_count: int
    mavproxy_drone_cmd_ack_latency_avg_ms: float
    mavproxy_drone_cmd_ack_latency_p95_ms: float
    mavproxy_drone_stream_rate_hz: float
    mavproxy_drone_log_path: Optional[str] = "" # PRUNED

    # --- J. MAVPROXY GCS (13) ---
    # Mirrored structure
    mavproxy_gcs_start_time: float
    mavproxy_gcs_end_time: float
    mavproxy_gcs_tx_pps: float
    mavproxy_gcs_rx_pps: float
    mavproxy_gcs_total_msgs_sent: int
    mavproxy_gcs_total_msgs_received: int
    mavproxy_gcs_seq_gap_count: int
    mavproxy_gcs_reconnect_count: Optional[int] = 0 # PRUNED
    mavproxy_gcs_cmd_sent_count: int
    mavproxy_gcs_cmd_ack_received_count: int
    mavproxy_gcs_cmd_ack_latency_avg_ms: float
    mavproxy_gcs_cmd_ack_latency_p95_ms: float
    mavproxy_gcs_log_path: Optional[str] = "" # PRUNED

    # --- K. MAVLINK INTEGRITY (10) ---
    mavlink_sysid: int
    mavlink_compid: int
    mavlink_protocol_version: int
    mavlink_packet_crc_error_count: int
    mavlink_decode_error_count: int
    mavlink_msg_drop_count: int
    mavlink_out_of_order_count: int
    mavlink_duplicate_count: int
    mavlink_message_latency_avg_ms: float
    mavlink_message_latency_p95_ms: Optional[float] = 0.0 # PRUNED

    # --- L. FC TELEMETRY (10) ---
    # ALL PRUNED
    fc_mode: Optional[str] = ""
    fc_armed_state: Optional[bool] = False
    fc_heartbeat_age_ms: Optional[float] = 0.0
    fc_attitude_update_rate_hz: Optional[float] = 0.0
    fc_position_update_rate_hz: Optional[float] = 0.0
    fc_battery_voltage_v: Optional[float] = 0.0
    fc_battery_current_a: Optional[float] = 0.0
    fc_battery_remaining_percent: Optional[float] = 0.0
    fc_cpu_load_percent: Optional[float] = 0.0
    fc_sensor_health_flags: Optional[int] = 0

    # --- M. CONTROL PLANE (7) ---
    scheduler_tick_interval_ms: Optional[float] = 0.0
    scheduler_decision_latency_ms: Optional[float] = 0.0
    scheduler_action_type: Optional[str] = ""
    scheduler_action_reason: Optional[str] = ""
    scheduler_cooldown_remaining_ms: Optional[float] = 0.0
    control_channel_rtt_ms: Optional[float] = 0.0
    control_channel_disconnect_count: Optional[int] = 0

    # --- N. SYSTEM RESOURCES (8) ---
    cpu_usage_avg_percent: float
    cpu_usage_peak_percent: float
    cpu_freq_mhz: float
    memory_rss_mb: float
    memory_vms_mb: float
    thread_count: int
    temperature_c: float
    thermal_throttle_events: Optional[int] = 0 # PRUNED

    # --- P. POWER & ENERGY (10) ---
    power_sensor_type: str
    power_sampling_rate_hz: float
    voltage_avg_v: Optional[float] = 0.0 # PRUNED (Not collected currently)
    current_avg_a: Optional[float] = 0.0 # PRUNED
    power_avg_w: float
    power_peak_w: float
    energy_total_j: float
    energy_per_handshake_j: float
    energy_per_rekey_j: Optional[float] = 0.0 # PRUNED
    energy_per_second_j: Optional[float] = 0.0 # PRUNED

    # --- Q-R. OBSERVABILITY & VALIDATION (10) ---
    log_sample_count: int
    log_drop_count: int
    metrics_sampling_rate_hz: float
    trace_file_path: Optional[str] = ""
    power_trace_file_path: Optional[str] = ""
    traffic_trace_file_path: Optional[str] = ""
    expected_samples: int
    collected_samples: int
    lost_samples: int
    success_rate_percent: float
    benchmark_pass_fail: str
    termination_reason: Optional[str] = ""

    # --- Derived / Augmented Fields (Not in Schema but needed for Dashboard) ---
    # These will be computed during ingestion
    suite_relative_start_s: Optional[float] = 0.0
    
class RunSummary(BaseModel):
    run_id: str
    timestamp: str
    suites_total: int
    suites_completed: int
    success_rate: float
    duration_s: float

class SuiteDetail(CanonicalMetrics):
    pass
