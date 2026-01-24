"""
Pydantic models for PQC Benchmark Dashboard.
Mirrors the canonical schema from core/metrics_schema.py.

Each model corresponds to one of the 18 metric categories (A-R).
"""

from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from enum import Enum


# =============================================================================
# ENUMS
# =============================================================================

class ReliabilityClass(str, Enum):
    """Metric reliability classification."""
    VERIFIED = "VERIFIED"
    CONDITIONAL = "CONDITIONAL"
    DEPRECATED = "DEPRECATED"
    MISSING = "MISSING"


# =============================================================================
# A. RUN & CONTEXT METRICS
# =============================================================================

class RunContextMetrics(BaseModel):
    """Run-level context and environment information."""
    run_id: str = ""
    suite_id: str = ""
    suite_index: int = 0
    git_commit_hash: str = ""
    git_dirty_flag: bool = False
    gcs_hostname: str = ""
    drone_hostname: str = ""
    gcs_ip: str = ""
    drone_ip: str = ""
    python_env_gcs: str = ""
    python_env_drone: str = ""
    liboqs_version: str = ""
    kernel_version_gcs: str = ""
    kernel_version_drone: str = ""
    clock_offset_ms: float = 0.0
    clock_offset_method: str = "ntp"
    run_start_time_wall: str = ""
    run_end_time_wall: str = ""
    run_start_time_mono: float = 0.0
    run_end_time_mono: float = 0.0

    class Config:
        extra = "forbid"


# =============================================================================
# B. SUITE CRYPTO IDENTITY
# =============================================================================

class SuiteCryptoIdentity(BaseModel):
    """Cryptographic identity and parameters for the suite."""
    kem_algorithm: str = ""
    kem_family: str = ""
    kem_parameter_set: str = ""
    kem_nist_level: str = ""
    sig_algorithm: str = ""
    sig_family: str = ""
    sig_parameter_set: str = ""
    sig_nist_level: str = ""
    aead_algorithm: str = ""
    aead_mode: str = ""
    suite_security_level: str = ""
    suite_tier: str = ""
    suite_order_index: int = 0

    class Config:
        extra = "forbid"


# =============================================================================
# C. SUITE LIFECYCLE TIMELINE
# =============================================================================

class SuiteLifecycleTimeline(BaseModel):
    """Timeline of suite activation and operation."""
    suite_selected_time: float = 0.0
    suite_activated_time: float = 0.0
    suite_traffic_start_time: float = 0.0
    suite_traffic_end_time: float = 0.0
    suite_rekey_start_time: float = 0.0
    suite_rekey_end_time: float = 0.0
    suite_deactivated_time: float = 0.0
    suite_total_duration_ms: float = 0.0
    suite_active_duration_ms: float = 0.0
    suite_blackout_count: int = 0
    suite_blackout_total_ms: float = 0.0

    class Config:
        extra = "forbid"


# =============================================================================
# D. HANDSHAKE METRICS
# =============================================================================

class HandshakeMetrics(BaseModel):
    """Handshake timing and status."""
    handshake_start_time_drone: float = 0.0
    handshake_end_time_drone: float = 0.0
    handshake_start_time_gcs: float = 0.0
    handshake_end_time_gcs: float = 0.0
    handshake_total_duration_ms: float = 0.0
    handshake_rtt_ms: float = 0.0
    handshake_success: bool = False
    handshake_failure_reason: str = ""

    class Config:
        extra = "forbid"


# =============================================================================
# E. CRYPTO PRIMITIVE BREAKDOWN
# =============================================================================

class CryptoPrimitiveBreakdown(BaseModel):
    """Detailed timing for each cryptographic primitive."""
    kem_keygen_time_ms: float = 0.0
    kem_encapsulation_time_ms: float = 0.0
    kem_decapsulation_time_ms: float = 0.0
    signature_sign_time_ms: float = 0.0
    signature_verify_time_ms: float = 0.0
    hkdf_extract_time_ms: float = 0.0
    hkdf_expand_time_ms: float = 0.0
    total_crypto_time_ms: float = 0.0
    kem_keygen_ns: int = 0
    kem_encaps_ns: int = 0
    kem_decaps_ns: int = 0
    sig_sign_ns: int = 0
    sig_verify_ns: int = 0
    pub_key_size_bytes: int = 0
    ciphertext_size_bytes: int = 0
    sig_size_bytes: int = 0
    shared_secret_size_bytes: int = 0

    class Config:
        extra = "forbid"


# =============================================================================
# F. REKEY METRICS
# =============================================================================

class RekeyMetrics(BaseModel):
    """Rekey operation metrics."""
    rekey_attempts: int = 0
    rekey_success: int = 0
    rekey_failure: int = 0
    rekey_interval_ms: float = 0.0
    rekey_duration_ms: float = 0.0
    rekey_blackout_duration_ms: float = 0.0
    rekey_trigger_reason: str = ""

    class Config:
        extra = "forbid"


# =============================================================================
# G. DATA PLANE (PROXY LEVEL)
# =============================================================================

class DataPlaneMetrics(BaseModel):
    """Proxy-level data plane metrics."""
    target_throughput_mbps: float = 0.0
    achieved_throughput_mbps: float = 0.0
    goodput_mbps: float = 0.0
    wire_rate_mbps: float = 0.0
    packets_sent: int = 0
    packets_received: int = 0
    packets_dropped: int = 0
    packet_loss_ratio: float = 0.0
    packet_delivery_ratio: float = 0.0
    replay_drop_count: int = 0
    decode_failure_count: int = 0
    ptx_in: int = 0
    ptx_out: int = 0
    enc_in: int = 0
    enc_out: int = 0
    drop_replay: int = 0
    drop_auth: int = 0
    drop_header: int = 0
    bytes_sent: int = 0
    bytes_received: int = 0
    aead_encrypt_avg_ns: float = 0.0
    aead_decrypt_avg_ns: float = 0.0
    aead_encrypt_count: int = 0
    aead_decrypt_count: int = 0

    class Config:
        extra = "forbid"


# =============================================================================
# H. LATENCY & JITTER (TRANSPORT)
# =============================================================================

class LatencyJitterMetrics(BaseModel):
    """Transport layer latency and jitter statistics."""
    one_way_latency_avg_ms: float = 0.0
    one_way_latency_p50_ms: float = 0.0
    one_way_latency_p95_ms: float = 0.0
    one_way_latency_max_ms: float = 0.0
    round_trip_latency_avg_ms: float = 0.0
    round_trip_latency_p50_ms: float = 0.0
    round_trip_latency_p95_ms: float = 0.0
    round_trip_latency_max_ms: float = 0.0
    jitter_avg_ms: float = 0.0
    jitter_p95_ms: float = 0.0
    latency_samples: List[float] = Field(default_factory=list)

    class Config:
        extra = "forbid"


# =============================================================================
# I. MAVPROXY APPLICATION LAYER — DRONE SIDE
# =============================================================================

class MavProxyDroneMetrics(BaseModel):
    """MAVProxy metrics from the drone side."""
    mavproxy_drone_start_time: float = 0.0
    mavproxy_drone_end_time: float = 0.0
    mavproxy_drone_tx_pps: float = 0.0
    mavproxy_drone_rx_pps: float = 0.0
    mavproxy_drone_total_msgs_sent: int = 0
    mavproxy_drone_total_msgs_received: int = 0
    mavproxy_drone_msg_type_counts: Dict[str, int] = Field(default_factory=dict)
    mavproxy_drone_heartbeat_interval_ms: float = 0.0
    mavproxy_drone_heartbeat_loss_count: int = 0
    mavproxy_drone_seq_gap_count: int = 0
    mavproxy_drone_reconnect_count: int = 0
    mavproxy_drone_cmd_sent_count: int = 0
    mavproxy_drone_cmd_ack_received_count: int = 0
    mavproxy_drone_cmd_ack_latency_avg_ms: float = 0.0
    mavproxy_drone_cmd_ack_latency_p95_ms: float = 0.0
    mavproxy_drone_stream_rate_hz: float = 0.0
    mavproxy_drone_log_path: str = ""

    class Config:
        extra = "forbid"


# =============================================================================
# J. MAVPROXY APPLICATION LAYER — GCS SIDE (PRUNED)
# =============================================================================

class MavProxyGcsMetrics(BaseModel):
    """
    MAVProxy metrics from the GCS side.
    
    POLICY: Pruned to validation-only metrics.
    Fields marked DEPRECATED are retained for schema compatibility but not collected.
    """
    # VERIFIED metrics
    mavproxy_gcs_total_msgs_received: int = 0
    mavproxy_gcs_seq_gap_count: int = 0
    # DEPRECATED fields (schema compatibility)
    mavproxy_gcs_start_time: float = 0.0
    mavproxy_gcs_end_time: float = 0.0
    mavproxy_gcs_tx_pps: float = 0.0
    mavproxy_gcs_rx_pps: float = 0.0
    mavproxy_gcs_total_msgs_sent: int = 0
    mavproxy_gcs_msg_type_counts: Dict[str, int] = Field(default_factory=dict)
    mavproxy_gcs_heartbeat_interval_ms: float = 0.0
    mavproxy_gcs_heartbeat_loss_count: int = 0
    mavproxy_gcs_reconnect_count: int = 0
    mavproxy_gcs_cmd_sent_count: int = 0
    mavproxy_gcs_cmd_ack_received_count: int = 0
    mavproxy_gcs_cmd_ack_latency_avg_ms: float = 0.0
    mavproxy_gcs_cmd_ack_latency_p95_ms: float = 0.0
    mavproxy_gcs_stream_rate_hz: float = 0.0
    mavproxy_gcs_log_path: str = ""

    class Config:
        extra = "forbid"


# =============================================================================
# K. MAVLINK SEMANTIC INTEGRITY
# =============================================================================

class MavLinkIntegrityMetrics(BaseModel):
    """MAVLink protocol integrity metrics."""
    mavlink_sysid: int = 0
    mavlink_compid: int = 0
    mavlink_protocol_version: str = ""
    mavlink_packet_crc_error_count: int = 0
    mavlink_decode_error_count: int = 0
    mavlink_msg_drop_count: int = 0
    mavlink_out_of_order_count: int = 0
    mavlink_duplicate_count: int = 0
    mavlink_message_latency_avg_ms: float = 0.0
    mavlink_message_latency_p95_ms: float = 0.0

    class Config:
        extra = "forbid"


# =============================================================================
# L. FLIGHT CONTROLLER TELEMETRY (DRONE)
# =============================================================================

class FlightControllerTelemetry(BaseModel):
    """Flight controller telemetry from the drone."""
    fc_mode: str = ""
    fc_armed_state: bool = False
    fc_heartbeat_age_ms: float = 0.0
    fc_attitude_update_rate_hz: float = 0.0
    fc_position_update_rate_hz: float = 0.0
    fc_battery_voltage_v: float = 0.0
    fc_battery_current_a: float = 0.0
    fc_battery_remaining_percent: float = 0.0
    fc_cpu_load_percent: float = 0.0
    fc_sensor_health_flags: int = 0
    fc_gps_fix_type: int = 0
    fc_gps_satellites: int = 0
    fc_altitude_m: float = 0.0
    fc_groundspeed_mps: float = 0.0

    class Config:
        extra = "forbid"


# =============================================================================
# M. CONTROL PLANE (SCHEDULER)
# =============================================================================

class ControlPlaneMetrics(BaseModel):
    """Scheduler and control plane metrics."""
    scheduler_tick_interval_ms: float = 0.0
    scheduler_decision_latency_ms: float = 0.0
    scheduler_action_type: str = ""
    scheduler_action_reason: str = ""
    scheduler_cooldown_remaining_ms: float = 0.0
    control_channel_rtt_ms: float = 0.0
    control_channel_disconnect_count: int = 0
    policy_name: str = ""
    policy_state: str = ""
    policy_suite_index: int = 0
    policy_total_suites: int = 0

    class Config:
        extra = "forbid"


# =============================================================================
# N. SYSTEM RESOURCES — DRONE
# =============================================================================

class SystemResourcesDrone(BaseModel):
    """System resource metrics from the drone."""
    cpu_usage_avg_percent: float = 0.0
    cpu_usage_peak_percent: float = 0.0
    cpu_freq_mhz: float = 0.0
    memory_rss_mb: float = 0.0
    memory_vms_mb: float = 0.0
    thread_count: int = 0
    temperature_c: float = 0.0
    thermal_throttle_events: int = 0
    uptime_s: float = 0.0
    load_avg_1m: float = 0.0
    load_avg_5m: float = 0.0
    load_avg_15m: float = 0.0
    disk_usage_percent: float = 0.0
    network_rx_bytes: int = 0
    network_tx_bytes: int = 0

    class Config:
        extra = "forbid"


# =============================================================================
# O. SYSTEM RESOURCES — GCS (DEPRECATED)
# =============================================================================

class SystemResourcesGcs(BaseModel):
    """
    DEPRECATED: GCS system resource metrics.
    These metrics are NO LONGER COLLECTED per policy realignment.
    """
    cpu_usage_avg_percent: float = 0.0
    cpu_usage_peak_percent: float = 0.0
    cpu_freq_mhz: float = 0.0
    memory_rss_mb: float = 0.0
    memory_vms_mb: float = 0.0
    thread_count: int = 0
    uptime_s: float = 0.0
    disk_usage_percent: float = 0.0

    class Config:
        extra = "forbid"


# =============================================================================
# P. POWER & ENERGY (DRONE)
# =============================================================================

class PowerEnergyMetrics(BaseModel):
    """Power and energy measurements from the drone."""
    power_sensor_type: str = ""
    power_sampling_rate_hz: float = 0.0
    voltage_avg_v: float = 0.0
    current_avg_a: float = 0.0
    power_avg_w: float = 0.0
    power_peak_w: float = 0.0
    energy_total_j: float = 0.0
    energy_per_handshake_j: float = 0.0
    energy_per_rekey_j: float = 0.0
    energy_per_second_j: float = 0.0
    power_samples: List[Dict[str, float]] = Field(default_factory=list)

    class Config:
        extra = "forbid"


# =============================================================================
# Q. OBSERVABILITY & LOGGING
# =============================================================================

class ObservabilityMetrics(BaseModel):
    """Logging and observability metrics."""
    log_sample_count: int = 0
    log_drop_count: int = 0
    metrics_sampling_rate_hz: float = 0.0
    trace_file_path: str = ""
    power_trace_file_path: str = ""
    traffic_trace_file_path: str = ""
    collection_start_time: float = 0.0
    collection_end_time: float = 0.0
    collection_duration_ms: float = 0.0

    class Config:
        extra = "forbid"


# =============================================================================
# R. VALIDATION & INTEGRITY
# =============================================================================

class ValidationMetrics(BaseModel):
    """Validation and integrity check results."""
    expected_samples: int = 0
    collected_samples: int = 0
    lost_samples: int = 0
    success_rate_percent: float = 0.0
    benchmark_pass_fail: str = ""
    termination_reason: str = ""
    data_completeness_percent: float = 0.0
    schema_validation_errors: List[str] = Field(default_factory=list)

    class Config:
        extra = "forbid"


# =============================================================================
# COMPREHENSIVE SUITE METRICS (ALL CATEGORIES)
# =============================================================================

class ComprehensiveSuiteMetrics(BaseModel):
    """
    Complete metrics for a single suite benchmark iteration.
    Combines all 18 categories (A-R) into one unified structure.
    """
    run_context: RunContextMetrics = Field(default_factory=RunContextMetrics)
    crypto_identity: SuiteCryptoIdentity = Field(default_factory=SuiteCryptoIdentity)
    lifecycle: SuiteLifecycleTimeline = Field(default_factory=SuiteLifecycleTimeline)
    handshake: HandshakeMetrics = Field(default_factory=HandshakeMetrics)
    crypto_primitives: CryptoPrimitiveBreakdown = Field(default_factory=CryptoPrimitiveBreakdown)
    rekey: RekeyMetrics = Field(default_factory=RekeyMetrics)
    data_plane: DataPlaneMetrics = Field(default_factory=DataPlaneMetrics)
    latency_jitter: LatencyJitterMetrics = Field(default_factory=LatencyJitterMetrics)
    mavproxy_drone: MavProxyDroneMetrics = Field(default_factory=MavProxyDroneMetrics)
    mavproxy_gcs: MavProxyGcsMetrics = Field(default_factory=MavProxyGcsMetrics)
    mavlink_integrity: MavLinkIntegrityMetrics = Field(default_factory=MavLinkIntegrityMetrics)
    fc_telemetry: FlightControllerTelemetry = Field(default_factory=FlightControllerTelemetry)
    control_plane: ControlPlaneMetrics = Field(default_factory=ControlPlaneMetrics)
    system_drone: SystemResourcesDrone = Field(default_factory=SystemResourcesDrone)
    system_gcs: SystemResourcesGcs = Field(default_factory=SystemResourcesGcs)
    power_energy: PowerEnergyMetrics = Field(default_factory=PowerEnergyMetrics)
    observability: ObservabilityMetrics = Field(default_factory=ObservabilityMetrics)
    validation: ValidationMetrics = Field(default_factory=ValidationMetrics)

    class Config:
        extra = "forbid"


# =============================================================================
# API RESPONSE MODELS
# =============================================================================

class SuiteSummary(BaseModel):
    """Summary of a suite for listing."""
    suite_id: str
    run_id: str
    suite_index: int
    kem_algorithm: str
    sig_algorithm: str
    aead_algorithm: str
    suite_security_level: str
    handshake_success: bool
    handshake_total_duration_ms: float
    power_avg_w: float
    energy_total_j: float
    benchmark_pass_fail: str


class RunSummary(BaseModel):
    """Summary of a benchmark run."""
    run_id: str
    run_start_time_wall: str
    gcs_hostname: str
    drone_hostname: str
    suite_count: int
    git_commit_hash: str


class ComparisonResult(BaseModel):
    """Result of comparing two suites."""
    suite_a: ComprehensiveSuiteMetrics
    suite_b: ComprehensiveSuiteMetrics
    diff_handshake_ms: float
    diff_power_w: float
    diff_energy_j: float


class SchemaField(BaseModel):
    """Schema field definition."""
    name: str
    category: str
    type: str
    unit: str
    reliability: ReliabilityClass
    description: str


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    suites_loaded: int
    runs_loaded: int
