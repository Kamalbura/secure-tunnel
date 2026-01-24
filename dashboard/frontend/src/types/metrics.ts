/**
 * TypeScript types matching backend Pydantic models.
 * 
 * Mirrors the canonical schema from core/metrics_schema.py
 */

// =============================================================================
// ENUMS
// =============================================================================

export type ReliabilityClass = 'VERIFIED' | 'CONDITIONAL' | 'DEPRECATED' | 'MISSING';

// =============================================================================
// A. RUN & CONTEXT METRICS
// =============================================================================

export interface RunContextMetrics {
    run_id: string;
    suite_id: string;
    suite_index: number;
    git_commit_hash: string;
    git_dirty_flag: boolean;
    gcs_hostname: string;
    drone_hostname: string;
    gcs_ip: string;
    drone_ip: string;
    python_env_gcs: string;
    python_env_drone: string;
    liboqs_version: string;
    kernel_version_gcs: string;
    kernel_version_drone: string;
    clock_offset_ms: number;
    clock_offset_method: string;
    run_start_time_wall: string;
    run_end_time_wall: string;
    run_start_time_mono: number;
    run_end_time_mono: number;
}

// =============================================================================
// B. SUITE CRYPTO IDENTITY
// =============================================================================

export interface SuiteCryptoIdentity {
    kem_algorithm: string;
    kem_family: string;
    kem_parameter_set: string;
    kem_nist_level: string;
    sig_algorithm: string;
    sig_family: string;
    sig_parameter_set: string;
    sig_nist_level: string;
    aead_algorithm: string;
    aead_mode: string;
    suite_security_level: string;
    suite_tier: string;
    suite_order_index: number;
}

// =============================================================================
// C. SUITE LIFECYCLE TIMELINE
// =============================================================================

export interface SuiteLifecycleTimeline {
    suite_selected_time: number;
    suite_activated_time: number;
    suite_traffic_start_time: number;
    suite_traffic_end_time: number;
    suite_rekey_start_time: number;
    suite_rekey_end_time: number;
    suite_deactivated_time: number;
    suite_total_duration_ms: number;
    suite_active_duration_ms: number;
    suite_blackout_count: number;
    suite_blackout_total_ms: number;
}

// =============================================================================
// D. HANDSHAKE METRICS
// =============================================================================

export interface HandshakeMetrics {
    handshake_start_time_drone: number;
    handshake_end_time_drone: number;
    handshake_start_time_gcs: number;
    handshake_end_time_gcs: number;
    handshake_total_duration_ms: number;
    handshake_rtt_ms: number;
    handshake_success: boolean;
    handshake_failure_reason: string;
}

// =============================================================================
// E. CRYPTO PRIMITIVE BREAKDOWN
// =============================================================================

export interface CryptoPrimitiveBreakdown {
    kem_keygen_time_ms: number;
    kem_encapsulation_time_ms: number;
    kem_decapsulation_time_ms: number;
    signature_sign_time_ms: number;
    signature_verify_time_ms: number;
    hkdf_extract_time_ms: number;
    hkdf_expand_time_ms: number;
    total_crypto_time_ms: number;
    kem_keygen_ns: number;
    kem_encaps_ns: number;
    kem_decaps_ns: number;
    sig_sign_ns: number;
    sig_verify_ns: number;
    pub_key_size_bytes: number;
    ciphertext_size_bytes: number;
    sig_size_bytes: number;
    shared_secret_size_bytes: number;
}

// =============================================================================
// F. REKEY METRICS
// =============================================================================

export interface RekeyMetrics {
    rekey_attempts: number;
    rekey_success: number;
    rekey_failure: number;
    rekey_interval_ms: number;
    rekey_duration_ms: number;
    rekey_blackout_duration_ms: number;
    rekey_trigger_reason: string;
}

// =============================================================================
// G. DATA PLANE
// =============================================================================

export interface DataPlaneMetrics {
    target_throughput_mbps: number;
    achieved_throughput_mbps: number;
    goodput_mbps: number;
    wire_rate_mbps: number;
    packets_sent: number;
    packets_received: number;
    packets_dropped: number;
    packet_loss_ratio: number;
    packet_delivery_ratio: number;
    replay_drop_count: number;
    decode_failure_count: number;
    ptx_in: number;
    ptx_out: number;
    enc_in: number;
    enc_out: number;
    drop_replay: number;
    drop_auth: number;
    drop_header: number;
    bytes_sent: number;
    bytes_received: number;
    aead_encrypt_avg_ns: number;
    aead_decrypt_avg_ns: number;
    aead_encrypt_count: number;
    aead_decrypt_count: number;
}

// =============================================================================
// H. LATENCY & JITTER
// =============================================================================

export interface LatencyJitterMetrics {
    one_way_latency_avg_ms: number;
    one_way_latency_p50_ms: number;
    one_way_latency_p95_ms: number;
    one_way_latency_max_ms: number;
    round_trip_latency_avg_ms: number;
    round_trip_latency_p50_ms: number;
    round_trip_latency_p95_ms: number;
    round_trip_latency_max_ms: number;
    jitter_avg_ms: number;
    jitter_p95_ms: number;
    latency_samples: number[];
}

// =============================================================================
// I. MAVPROXY DRONE
// =============================================================================

export interface MavProxyDroneMetrics {
    mavproxy_drone_start_time: number;
    mavproxy_drone_end_time: number;
    mavproxy_drone_tx_pps: number;
    mavproxy_drone_rx_pps: number;
    mavproxy_drone_total_msgs_sent: number;
    mavproxy_drone_total_msgs_received: number;
    mavproxy_drone_msg_type_counts: Record<string, number>;
    mavproxy_drone_heartbeat_interval_ms: number;
    mavproxy_drone_heartbeat_loss_count: number;
    mavproxy_drone_seq_gap_count: number;
    mavproxy_drone_reconnect_count: number;
    mavproxy_drone_cmd_sent_count: number;
    mavproxy_drone_cmd_ack_received_count: number;
    mavproxy_drone_cmd_ack_latency_avg_ms: number;
    mavproxy_drone_cmd_ack_latency_p95_ms: number;
    mavproxy_drone_stream_rate_hz: number;
    mavproxy_drone_log_path: string;
}

// =============================================================================
// J. MAVPROXY GCS (PRUNED)
// =============================================================================

export interface MavProxyGcsMetrics {
    mavproxy_gcs_total_msgs_received: number;
    mavproxy_gcs_seq_gap_count: number;
    // Deprecated fields (retained for schema compatibility)
    mavproxy_gcs_start_time: number;
    mavproxy_gcs_end_time: number;
    mavproxy_gcs_tx_pps: number;
    mavproxy_gcs_rx_pps: number;
    mavproxy_gcs_total_msgs_sent: number;
    mavproxy_gcs_msg_type_counts: Record<string, number>;
    mavproxy_gcs_heartbeat_interval_ms: number;
    mavproxy_gcs_heartbeat_loss_count: number;
    mavproxy_gcs_reconnect_count: number;
    mavproxy_gcs_cmd_sent_count: number;
    mavproxy_gcs_cmd_ack_received_count: number;
    mavproxy_gcs_cmd_ack_latency_avg_ms: number;
    mavproxy_gcs_cmd_ack_latency_p95_ms: number;
    mavproxy_gcs_stream_rate_hz: number;
    mavproxy_gcs_log_path: string;
}

// =============================================================================
// K. MAVLINK INTEGRITY
// =============================================================================

export interface MavLinkIntegrityMetrics {
    mavlink_sysid: number;
    mavlink_compid: number;
    mavlink_protocol_version: string;
    mavlink_packet_crc_error_count: number;
    mavlink_decode_error_count: number;
    mavlink_msg_drop_count: number;
    mavlink_out_of_order_count: number;
    mavlink_duplicate_count: number;
    mavlink_message_latency_avg_ms: number;
    mavlink_message_latency_p95_ms: number;
}

// =============================================================================
// L. FLIGHT CONTROLLER TELEMETRY
// =============================================================================

export interface FlightControllerTelemetry {
    fc_mode: string;
    fc_armed_state: boolean;
    fc_heartbeat_age_ms: number;
    fc_attitude_update_rate_hz: number;
    fc_position_update_rate_hz: number;
    fc_battery_voltage_v: number;
    fc_battery_current_a: number;
    fc_battery_remaining_percent: number;
    fc_cpu_load_percent: number;
    fc_sensor_health_flags: number;
    fc_gps_fix_type: number;
    fc_gps_satellites: number;
    fc_altitude_m: number;
    fc_groundspeed_mps: number;
}

// =============================================================================
// M. CONTROL PLANE
// =============================================================================

export interface ControlPlaneMetrics {
    scheduler_tick_interval_ms: number;
    scheduler_decision_latency_ms: number;
    scheduler_action_type: string;
    scheduler_action_reason: string;
    scheduler_cooldown_remaining_ms: number;
    control_channel_rtt_ms: number;
    control_channel_disconnect_count: number;
    policy_name: string;
    policy_state: string;
    policy_suite_index: number;
    policy_total_suites: number;
}

// =============================================================================
// N. SYSTEM RESOURCES DRONE
// =============================================================================

export interface SystemResourcesDrone {
    cpu_usage_avg_percent: number;
    cpu_usage_peak_percent: number;
    cpu_freq_mhz: number;
    memory_rss_mb: number;
    memory_vms_mb: number;
    thread_count: number;
    temperature_c: number;
    thermal_throttle_events: number;
    uptime_s: number;
    load_avg_1m: number;
    load_avg_5m: number;
    load_avg_15m: number;
    disk_usage_percent: number;
    network_rx_bytes: number;
    network_tx_bytes: number;
}

// =============================================================================
// O. SYSTEM RESOURCES GCS (DEPRECATED)
// =============================================================================

export interface SystemResourcesGcs {
    cpu_usage_avg_percent: number;
    cpu_usage_peak_percent: number;
    cpu_freq_mhz: number;
    memory_rss_mb: number;
    memory_vms_mb: number;
    thread_count: number;
    uptime_s: number;
    disk_usage_percent: number;
}

// =============================================================================
// P. POWER & ENERGY
// =============================================================================

export interface PowerEnergyMetrics {
    power_sensor_type: string;
    power_sampling_rate_hz: number;
    voltage_avg_v: number;
    current_avg_a: number;
    power_avg_w: number;
    power_peak_w: number;
    energy_total_j: number;
    energy_per_handshake_j: number;
    energy_per_rekey_j: number;
    energy_per_second_j: number;
    power_samples: Array<Record<string, number>>;
}

// =============================================================================
// Q. OBSERVABILITY
// =============================================================================

export interface ObservabilityMetrics {
    log_sample_count: number;
    log_drop_count: number;
    metrics_sampling_rate_hz: number;
    trace_file_path: string;
    power_trace_file_path: string;
    traffic_trace_file_path: string;
    collection_start_time: number;
    collection_end_time: number;
    collection_duration_ms: number;
}

// =============================================================================
// R. VALIDATION
// =============================================================================

export interface ValidationMetrics {
    expected_samples: number;
    collected_samples: number;
    lost_samples: number;
    success_rate_percent: number;
    benchmark_pass_fail: string;
    termination_reason: string;
    data_completeness_percent: number;
    schema_validation_errors: string[];
}

// =============================================================================
// COMPREHENSIVE SUITE METRICS
// =============================================================================

export interface ComprehensiveSuiteMetrics {
    run_context: RunContextMetrics;
    crypto_identity: SuiteCryptoIdentity;
    lifecycle: SuiteLifecycleTimeline;
    handshake: HandshakeMetrics;
    crypto_primitives: CryptoPrimitiveBreakdown;
    rekey: RekeyMetrics;
    data_plane: DataPlaneMetrics;
    latency_jitter: LatencyJitterMetrics;
    mavproxy_drone: MavProxyDroneMetrics;
    mavproxy_gcs: MavProxyGcsMetrics;
    mavlink_integrity: MavLinkIntegrityMetrics;
    fc_telemetry: FlightControllerTelemetry;
    control_plane: ControlPlaneMetrics;
    system_drone: SystemResourcesDrone;
    system_gcs: SystemResourcesGcs;
    power_energy: PowerEnergyMetrics;
    observability: ObservabilityMetrics;
    validation: ValidationMetrics;
}

// =============================================================================
// API RESPONSE TYPES
// =============================================================================

export interface SuiteSummary {
    suite_id: string;
    run_id: string;
    suite_index: number;
    kem_algorithm: string;
    sig_algorithm: string;
    aead_algorithm: string;
    suite_security_level: string;
    handshake_success: boolean;
    handshake_total_duration_ms: number;
    power_avg_w: number;
    energy_total_j: number;
    benchmark_pass_fail: string;
}

export interface RunSummary {
    run_id: string;
    run_start_time_wall: string;
    gcs_hostname: string;
    drone_hostname: string;
    suite_count: number;
    git_commit_hash: string;
}

export interface SchemaField {
    name: string;
    category: string;
    type: string;
    unit: string;
    reliability: ReliabilityClass;
    description: string;
}

export interface HealthResponse {
    status: string;
    suites_loaded: number;
    runs_loaded: number;
}

export interface FiltersResponse {
    kem_families: string[];
    sig_families: string[];
    aead_algorithms: string[];
    nist_levels: string[];
}
