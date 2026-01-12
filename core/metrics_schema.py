#!/usr/bin/env python3
"""
Comprehensive Metrics Schema for PQC Benchmark
core/metrics_schema.py

Defines all 18 metric categories (A-R) as structured dataclasses.
This schema ensures consistent, typed metrics collection across GCS and Drone.

Categories:
    A. Run & Context Metrics
    B. Suite Crypto Identity
    C. Suite Lifecycle Timeline
    D. Handshake Metrics
    E. Crypto Primitive Breakdown
    F. Rekey Metrics
    G. Data Plane (Proxy Level)
    H. Latency & Jitter (Transport)
    I. MAVProxy Application Layer — Drone Side
    J. MAVProxy Application Layer — GCS Side
    K. MAVLink Semantic Integrity
    L. Flight Controller Telemetry (Drone)
    M. Control Plane (Scheduler)
    N. System Resources — Drone
    O. System Resources — GCS
    P. Power & Energy (Drone)
    Q. Observability & Logging
    R. Validation & Integrity
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any
from datetime import datetime
import json
import time
import platform
import os
import subprocess


# =============================================================================
# A. RUN & CONTEXT METRICS
# =============================================================================

@dataclass
class RunContextMetrics:
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


# =============================================================================
# B. SUITE CRYPTO IDENTITY
# =============================================================================

@dataclass
class SuiteCryptoIdentity:
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


# =============================================================================
# C. SUITE LIFECYCLE TIMELINE
# =============================================================================

@dataclass
class SuiteLifecycleTimeline:
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


# =============================================================================
# D. HANDSHAKE METRICS
# =============================================================================

@dataclass
class HandshakeMetrics:
    """Handshake timing and status."""
    handshake_start_time_drone: float = 0.0
    handshake_end_time_drone: float = 0.0
    handshake_start_time_gcs: float = 0.0
    handshake_end_time_gcs: float = 0.0
    handshake_total_duration_ms: float = 0.0
    handshake_rtt_ms: float = 0.0
    handshake_success: bool = False
    handshake_failure_reason: str = ""


# =============================================================================
# E. CRYPTO PRIMITIVE BREAKDOWN
# =============================================================================

@dataclass
class CryptoPrimitiveBreakdown:
    """Detailed timing for each cryptographic primitive."""
    kem_keygen_time_ms: float = 0.0
    kem_encapsulation_time_ms: float = 0.0
    kem_decapsulation_time_ms: float = 0.0
    signature_sign_time_ms: float = 0.0
    signature_verify_time_ms: float = 0.0
    hkdf_extract_time_ms: float = 0.0
    hkdf_expand_time_ms: float = 0.0
    total_crypto_time_ms: float = 0.0
    
    # Extended primitive timing (nanoseconds for precision)
    kem_keygen_ns: int = 0
    kem_encaps_ns: int = 0
    kem_decaps_ns: int = 0
    sig_sign_ns: int = 0
    sig_verify_ns: int = 0
    
    # Artifact sizes
    pub_key_size_bytes: int = 0
    ciphertext_size_bytes: int = 0
    sig_size_bytes: int = 0
    shared_secret_size_bytes: int = 0


# =============================================================================
# F. REKEY METRICS
# =============================================================================

@dataclass
class RekeyMetrics:
    """Rekey operation metrics."""
    rekey_attempts: int = 0
    rekey_success: int = 0
    rekey_failure: int = 0
    rekey_interval_ms: float = 0.0
    rekey_duration_ms: float = 0.0
    rekey_blackout_duration_ms: float = 0.0
    rekey_trigger_reason: str = ""


# =============================================================================
# G. DATA PLANE (PROXY LEVEL)
# =============================================================================

@dataclass
class DataPlaneMetrics:
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
    
    # Detailed packet counters
    ptx_in: int = 0  # Plaintext in
    ptx_out: int = 0  # Plaintext out
    enc_in: int = 0  # Encrypted in
    enc_out: int = 0  # Encrypted out
    drop_replay: int = 0
    drop_auth: int = 0
    drop_header: int = 0
    
    # Byte counters
    bytes_sent: int = 0
    bytes_received: int = 0
    
    # AEAD timing
    aead_encrypt_avg_ns: float = 0.0
    aead_decrypt_avg_ns: float = 0.0
    aead_encrypt_count: int = 0
    aead_decrypt_count: int = 0


# =============================================================================
# H. LATENCY & JITTER (TRANSPORT)
# =============================================================================

@dataclass
class LatencyJitterMetrics:
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
    
    # Raw samples for post-processing
    latency_samples: List[float] = field(default_factory=list)


# =============================================================================
# I. MAVPROXY APPLICATION LAYER — DRONE SIDE
# =============================================================================

@dataclass
class MavProxyDroneMetrics:
    """MAVProxy metrics from the drone side."""
    mavproxy_drone_start_time: float = 0.0
    mavproxy_drone_end_time: float = 0.0
    mavproxy_drone_tx_pps: float = 0.0
    mavproxy_drone_rx_pps: float = 0.0
    mavproxy_drone_total_msgs_sent: int = 0
    mavproxy_drone_total_msgs_received: int = 0
    mavproxy_drone_msg_type_counts: Dict[str, int] = field(default_factory=dict)
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


# =============================================================================
# J. MAVPROXY APPLICATION LAYER — GCS SIDE
# =============================================================================

@dataclass
class MavProxyGcsMetrics:
    """MAVProxy metrics from the GCS side."""
    mavproxy_gcs_start_time: float = 0.0
    mavproxy_gcs_end_time: float = 0.0
    mavproxy_gcs_tx_pps: float = 0.0
    mavproxy_gcs_rx_pps: float = 0.0
    mavproxy_gcs_total_msgs_sent: int = 0
    mavproxy_gcs_total_msgs_received: int = 0
    mavproxy_gcs_msg_type_counts: Dict[str, int] = field(default_factory=dict)
    mavproxy_gcs_heartbeat_interval_ms: float = 0.0
    mavproxy_gcs_heartbeat_loss_count: int = 0
    mavproxy_gcs_seq_gap_count: int = 0
    mavproxy_gcs_reconnect_count: int = 0
    mavproxy_gcs_cmd_sent_count: int = 0
    mavproxy_gcs_cmd_ack_received_count: int = 0
    mavproxy_gcs_cmd_ack_latency_avg_ms: float = 0.0
    mavproxy_gcs_cmd_ack_latency_p95_ms: float = 0.0
    mavproxy_gcs_stream_rate_hz: float = 0.0
    mavproxy_gcs_log_path: str = ""


# =============================================================================
# K. MAVLINK SEMANTIC INTEGRITY
# =============================================================================

@dataclass
class MavLinkIntegrityMetrics:
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


# =============================================================================
# L. FLIGHT CONTROLLER TELEMETRY (DRONE)
# =============================================================================

@dataclass
class FlightControllerTelemetry:
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
    
    # Extended telemetry
    fc_gps_fix_type: int = 0
    fc_gps_satellites: int = 0
    fc_altitude_m: float = 0.0
    fc_groundspeed_mps: float = 0.0


# =============================================================================
# M. CONTROL PLANE (SCHEDULER)
# =============================================================================

@dataclass
class ControlPlaneMetrics:
    """Scheduler and control plane metrics."""
    scheduler_tick_interval_ms: float = 0.0
    scheduler_decision_latency_ms: float = 0.0
    scheduler_action_type: str = ""
    scheduler_action_reason: str = ""
    scheduler_cooldown_remaining_ms: float = 0.0
    control_channel_rtt_ms: float = 0.0
    control_channel_disconnect_count: int = 0
    
    # Policy state
    policy_name: str = ""
    policy_state: str = ""
    policy_suite_index: int = 0
    policy_total_suites: int = 0


# =============================================================================
# N. SYSTEM RESOURCES — DRONE
# =============================================================================

@dataclass
class SystemResourcesDrone:
    """System resource metrics from the drone."""
    cpu_usage_avg_percent: float = 0.0
    cpu_usage_peak_percent: float = 0.0
    cpu_freq_mhz: float = 0.0
    memory_rss_mb: float = 0.0
    memory_vms_mb: float = 0.0
    thread_count: int = 0
    temperature_c: float = 0.0
    thermal_throttle_events: int = 0
    
    # Extended system info
    uptime_s: float = 0.0
    load_avg_1m: float = 0.0
    load_avg_5m: float = 0.0
    load_avg_15m: float = 0.0
    disk_usage_percent: float = 0.0
    network_rx_bytes: int = 0
    network_tx_bytes: int = 0


# =============================================================================
# O. SYSTEM RESOURCES — GCS
# =============================================================================

@dataclass
class SystemResourcesGcs:
    """System resource metrics from the GCS."""
    cpu_usage_avg_percent: float = 0.0
    cpu_usage_peak_percent: float = 0.0
    cpu_freq_mhz: float = 0.0
    memory_rss_mb: float = 0.0
    memory_vms_mb: float = 0.0
    thread_count: int = 0
    
    # Extended system info
    uptime_s: float = 0.0
    disk_usage_percent: float = 0.0


# =============================================================================
# P. POWER & ENERGY (DRONE)
# =============================================================================

@dataclass
class PowerEnergyMetrics:
    """Power and energy measurements from the drone."""
    power_sensor_type: str = ""  # "ina219", "rpi5_pmic", "rpi5_hwmon", "none"
    power_sampling_rate_hz: float = 0.0
    voltage_avg_v: float = 0.0
    current_avg_a: float = 0.0
    power_avg_w: float = 0.0
    power_peak_w: float = 0.0
    energy_total_j: float = 0.0
    energy_per_handshake_j: float = 0.0
    energy_per_rekey_j: float = 0.0
    energy_per_second_j: float = 0.0
    
    # Raw power samples
    power_samples: List[Dict[str, float]] = field(default_factory=list)


# =============================================================================
# Q. OBSERVABILITY & LOGGING
# =============================================================================

@dataclass
class ObservabilityMetrics:
    """Logging and observability metrics."""
    log_sample_count: int = 0
    log_drop_count: int = 0
    metrics_sampling_rate_hz: float = 0.0
    trace_file_path: str = ""
    power_trace_file_path: str = ""
    traffic_trace_file_path: str = ""
    
    # Collection timestamps
    collection_start_time: float = 0.0
    collection_end_time: float = 0.0
    collection_duration_ms: float = 0.0


# =============================================================================
# R. VALIDATION & INTEGRITY
# =============================================================================

@dataclass
class ValidationMetrics:
    """Validation and integrity check results."""
    expected_samples: int = 0
    collected_samples: int = 0
    lost_samples: int = 0
    success_rate_percent: float = 0.0
    benchmark_pass_fail: str = ""
    termination_reason: str = ""
    
    # Data quality
    data_completeness_percent: float = 0.0
    schema_validation_errors: List[str] = field(default_factory=list)


# =============================================================================
# COMPREHENSIVE SUITE METRICS (ALL CATEGORIES)
# =============================================================================

@dataclass
class ComprehensiveSuiteMetrics:
    """
    Complete metrics for a single suite benchmark iteration.
    Combines all 18 categories (A-R) into one unified structure.
    """
    # A. Run & Context
    run_context: RunContextMetrics = field(default_factory=RunContextMetrics)
    
    # B. Suite Crypto Identity
    crypto_identity: SuiteCryptoIdentity = field(default_factory=SuiteCryptoIdentity)
    
    # C. Suite Lifecycle Timeline
    lifecycle: SuiteLifecycleTimeline = field(default_factory=SuiteLifecycleTimeline)
    
    # D. Handshake Metrics
    handshake: HandshakeMetrics = field(default_factory=HandshakeMetrics)
    
    # E. Crypto Primitive Breakdown
    crypto_primitives: CryptoPrimitiveBreakdown = field(default_factory=CryptoPrimitiveBreakdown)
    
    # F. Rekey Metrics
    rekey: RekeyMetrics = field(default_factory=RekeyMetrics)
    
    # G. Data Plane (Proxy Level)
    data_plane: DataPlaneMetrics = field(default_factory=DataPlaneMetrics)
    
    # H. Latency & Jitter
    latency_jitter: LatencyJitterMetrics = field(default_factory=LatencyJitterMetrics)
    
    # I. MAVProxy Drone
    mavproxy_drone: MavProxyDroneMetrics = field(default_factory=MavProxyDroneMetrics)
    
    # J. MAVProxy GCS
    mavproxy_gcs: MavProxyGcsMetrics = field(default_factory=MavProxyGcsMetrics)
    
    # K. MAVLink Integrity
    mavlink_integrity: MavLinkIntegrityMetrics = field(default_factory=MavLinkIntegrityMetrics)
    
    # L. Flight Controller Telemetry
    fc_telemetry: FlightControllerTelemetry = field(default_factory=FlightControllerTelemetry)
    
    # M. Control Plane
    control_plane: ControlPlaneMetrics = field(default_factory=ControlPlaneMetrics)
    
    # N. System Resources Drone
    system_drone: SystemResourcesDrone = field(default_factory=SystemResourcesDrone)
    
    # O. System Resources GCS
    system_gcs: SystemResourcesGcs = field(default_factory=SystemResourcesGcs)
    
    # P. Power & Energy
    power_energy: PowerEnergyMetrics = field(default_factory=PowerEnergyMetrics)
    
    # Q. Observability
    observability: ObservabilityMetrics = field(default_factory=ObservabilityMetrics)
    
    # R. Validation
    validation: ValidationMetrics = field(default_factory=ValidationMetrics)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent, default=str)
    
    def save_json(self, filepath: str):
        """Save metrics to JSON file."""
        with open(filepath, 'w') as f:
            f.write(self.to_json())
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ComprehensiveSuiteMetrics':
        """Create from dictionary."""
        metrics = cls()
        
        if 'run_context' in data:
            metrics.run_context = RunContextMetrics(**data['run_context'])
        if 'crypto_identity' in data:
            metrics.crypto_identity = SuiteCryptoIdentity(**data['crypto_identity'])
        if 'lifecycle' in data:
            metrics.lifecycle = SuiteLifecycleTimeline(**data['lifecycle'])
        if 'handshake' in data:
            metrics.handshake = HandshakeMetrics(**data['handshake'])
        if 'crypto_primitives' in data:
            metrics.crypto_primitives = CryptoPrimitiveBreakdown(**data['crypto_primitives'])
        if 'rekey' in data:
            metrics.rekey = RekeyMetrics(**data['rekey'])
        if 'data_plane' in data:
            metrics.data_plane = DataPlaneMetrics(**data['data_plane'])
        if 'latency_jitter' in data:
            metrics.latency_jitter = LatencyJitterMetrics(**data['latency_jitter'])
        if 'mavproxy_drone' in data:
            metrics.mavproxy_drone = MavProxyDroneMetrics(**data['mavproxy_drone'])
        if 'mavproxy_gcs' in data:
            metrics.mavproxy_gcs = MavProxyGcsMetrics(**data['mavproxy_gcs'])
        if 'mavlink_integrity' in data:
            metrics.mavlink_integrity = MavLinkIntegrityMetrics(**data['mavlink_integrity'])
        if 'fc_telemetry' in data:
            metrics.fc_telemetry = FlightControllerTelemetry(**data['fc_telemetry'])
        if 'control_plane' in data:
            metrics.control_plane = ControlPlaneMetrics(**data['control_plane'])
        if 'system_drone' in data:
            metrics.system_drone = SystemResourcesDrone(**data['system_drone'])
        if 'system_gcs' in data:
            metrics.system_gcs = SystemResourcesGcs(**data['system_gcs'])
        if 'power_energy' in data:
            metrics.power_energy = PowerEnergyMetrics(**data['power_energy'])
        if 'observability' in data:
            metrics.observability = ObservabilityMetrics(**data['observability'])
        if 'validation' in data:
            metrics.validation = ValidationMetrics(**data['validation'])
        
        return metrics
    
    @classmethod
    def from_json(cls, json_str: str) -> 'ComprehensiveSuiteMetrics':
        """Create from JSON string."""
        return cls.from_dict(json.loads(json_str))
    
    @classmethod
    def load_json(cls, filepath: str) -> 'ComprehensiveSuiteMetrics':
        """Load from JSON file."""
        with open(filepath, 'r') as f:
            return cls.from_json(f.read())


# =============================================================================
# HELPER: Get metric field count
# =============================================================================

def count_metrics() -> Dict[str, int]:
    """Count metrics in each category."""
    from dataclasses import fields
    
    categories = {
        'A. Run & Context': RunContextMetrics,
        'B. Suite Crypto Identity': SuiteCryptoIdentity,
        'C. Suite Lifecycle Timeline': SuiteLifecycleTimeline,
        'D. Handshake Metrics': HandshakeMetrics,
        'E. Crypto Primitive Breakdown': CryptoPrimitiveBreakdown,
        'F. Rekey Metrics': RekeyMetrics,
        'G. Data Plane': DataPlaneMetrics,
        'H. Latency & Jitter': LatencyJitterMetrics,
        'I. MAVProxy Drone': MavProxyDroneMetrics,
        'J. MAVProxy GCS': MavProxyGcsMetrics,
        'K. MAVLink Integrity': MavLinkIntegrityMetrics,
        'L. Flight Controller': FlightControllerTelemetry,
        'M. Control Plane': ControlPlaneMetrics,
        'N. System Drone': SystemResourcesDrone,
        'O. System GCS': SystemResourcesGcs,
        'P. Power & Energy': PowerEnergyMetrics,
        'Q. Observability': ObservabilityMetrics,
        'R. Validation': ValidationMetrics,
    }
    
    counts = {}
    total = 0
    for name, cls in categories.items():
        count = len(fields(cls))
        counts[name] = count
        total += count
    
    counts['TOTAL'] = total
    return counts


if __name__ == "__main__":
    # Print metric counts
    print("=" * 60)
    print("COMPREHENSIVE METRICS SCHEMA")
    print("=" * 60)
    
    counts = count_metrics()
    for category, count in counts.items():
        print(f"  {category}: {count} fields")
    
    print()
    print("Creating sample metrics object...")
    
    # Create a sample metrics object
    metrics = ComprehensiveSuiteMetrics()
    metrics.run_context.run_id = "test_run_001"
    metrics.run_context.suite_id = "cs-mlkem512-aesgcm-falcon512"
    metrics.crypto_identity.kem_algorithm = "ML-KEM-512"
    metrics.handshake.handshake_total_duration_ms = 15.5
    
    # Print sample JSON
    print("\nSample JSON (truncated):")
    print(metrics.to_json()[:500] + "...")
