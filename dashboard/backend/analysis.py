"""
Analysis Module for PQC Benchmark Dashboard.

Provides Pandas-based analysis functions for:
- Per-suite metric extraction
- Cross-suite comparison
- Regime filtering
- Drone vs GCS metric split
"""

import pandas as pd
from typing import Dict, List, Optional, Any, Tuple
from models import (
    ComprehensiveSuiteMetrics,
    ComparisonResult,
    ReliabilityClass,
    SchemaField
)


# =============================================================================
# SCHEMA METADATA
# =============================================================================

# Fields that are DEPRECATED/CONDITIONAL (from policy realignment)
DEPRECATED_FIELDS = {
    # GCS MAVProxy (pruned)
    "mavproxy_gcs.mavproxy_gcs_tx_pps",
    "mavproxy_gcs.mavproxy_gcs_rx_pps",
    "mavproxy_gcs.mavproxy_gcs_total_msgs_sent",
    "mavproxy_gcs.mavproxy_gcs_msg_type_counts",
    "mavproxy_gcs.mavproxy_gcs_heartbeat_interval_ms",
    "mavproxy_gcs.mavproxy_gcs_heartbeat_loss_count",
    "mavproxy_gcs.mavproxy_gcs_reconnect_count",
    "mavproxy_gcs.mavproxy_gcs_cmd_sent_count",
    "mavproxy_gcs.mavproxy_gcs_cmd_ack_received_count",
    "mavproxy_gcs.mavproxy_gcs_cmd_ack_latency_avg_ms",
    "mavproxy_gcs.mavproxy_gcs_cmd_ack_latency_p95_ms",
    "mavproxy_gcs.mavproxy_gcs_stream_rate_hz",
    "mavproxy_gcs.mavproxy_gcs_log_path",
    # GCS System Resources (all deprecated)
    "system_gcs.cpu_usage_avg_percent",
    "system_gcs.cpu_usage_peak_percent",
    "system_gcs.cpu_freq_mhz",
    "system_gcs.memory_rss_mb",
    "system_gcs.memory_vms_mb",
    "system_gcs.thread_count",
    "system_gcs.uptime_s",
    "system_gcs.disk_usage_percent",
}

# Fields that are validation-only from GCS
CONDITIONAL_FIELDS = {
    "mavproxy_gcs.mavproxy_gcs_total_msgs_received",
    "mavproxy_gcs.mavproxy_gcs_seq_gap_count",
}

# Metric units
METRIC_UNITS = {
    "handshake_total_duration_ms": "ms",
    "handshake_rtt_ms": "ms",
    "kem_keygen_time_ms": "ms",
    "kem_encapsulation_time_ms": "ms",
    "kem_decapsulation_time_ms": "ms",
    "signature_sign_time_ms": "ms",
    "signature_verify_time_ms": "ms",
    "power_avg_w": "W",
    "power_peak_w": "W",
    "energy_total_j": "J",
    "energy_per_handshake_j": "J",
    "voltage_avg_v": "V",
    "current_avg_a": "A",
    "cpu_usage_avg_percent": "%",
    "cpu_usage_peak_percent": "%",
    "memory_rss_mb": "MB",
    "temperature_c": "°C",
    "jitter_avg_ms": "ms",
    "one_way_latency_avg_ms": "ms",
    "round_trip_latency_avg_ms": "ms",
    "packets_sent": "count",
    "packets_received": "count",
    "packets_dropped": "count",
    "suite_total_duration_ms": "ms",
    "suite_active_duration_ms": "ms",
}


def get_field_reliability(field_path: str) -> ReliabilityClass:
    """Get the reliability class for a field."""
    if field_path in DEPRECATED_FIELDS:
        return ReliabilityClass.DEPRECATED
    if field_path in CONDITIONAL_FIELDS:
        return ReliabilityClass.CONDITIONAL
    return ReliabilityClass.VERIFIED


def get_field_unit(field_name: str) -> str:
    """Get the unit for a field."""
    return METRIC_UNITS.get(field_name, "")


# =============================================================================
# SUITE DATA EXTRACTION
# =============================================================================

def suite_to_flat_dict(suite: ComprehensiveSuiteMetrics) -> Dict[str, Any]:
    """Flatten a suite's metrics into a single-level dictionary."""
    flat = {}
    data = suite.model_dump()
    
    for category, fields in data.items():
        if isinstance(fields, dict):
            for field, value in fields.items():
                # Skip complex nested structures for flat representation
                if isinstance(value, (list, dict)) and value:
                    continue
                flat[f"{category}.{field}"] = value
        else:
            flat[category] = fields
    
    return flat


def suites_to_dataframe(suites: List[ComprehensiveSuiteMetrics]) -> pd.DataFrame:
    """Convert a list of suites to a Pandas DataFrame."""
    rows = [suite_to_flat_dict(s) for s in suites]
    return pd.DataFrame(rows)


# =============================================================================
# COMPARISON
# =============================================================================

def compare_suites(
    suite_a: ComprehensiveSuiteMetrics,
    suite_b: ComprehensiveSuiteMetrics
) -> ComparisonResult:
    """
    Compare two suites side-by-side.
    
    Returns a ComparisonResult with both suites and computed differences.
    """
    diff_handshake = (
        suite_b.handshake.handshake_total_duration_ms -
        suite_a.handshake.handshake_total_duration_ms
    )
    diff_power = (
        suite_b.power_energy.power_avg_w -
        suite_a.power_energy.power_avg_w
    )
    diff_energy = (
        suite_b.power_energy.energy_total_j -
        suite_a.power_energy.energy_total_j
    )
    
    return ComparisonResult(
        suite_a=suite_a,
        suite_b=suite_b,
        diff_handshake_ms=diff_handshake,
        diff_power_w=diff_power,
        diff_energy_j=diff_energy
    )


def compute_comparison_table(
    suite_a: ComprehensiveSuiteMetrics,
    suite_b: ComprehensiveSuiteMetrics
) -> List[Dict[str, Any]]:
    """
    Create a detailed comparison table of all metrics.
    
    Returns a list of rows with metric, value_a, value_b, diff, unit, reliability.
    """
    flat_a = suite_to_flat_dict(suite_a)
    flat_b = suite_to_flat_dict(suite_b)
    
    all_keys = set(flat_a.keys()) | set(flat_b.keys())
    
    rows = []
    for key in sorted(all_keys):
        val_a = flat_a.get(key)
        val_b = flat_b.get(key)
        
        # Compute diff for numeric values
        diff = None
        if isinstance(val_a, (int, float)) and isinstance(val_b, (int, float)):
            diff = val_b - val_a
        
        field_name = key.split(".")[-1] if "." in key else key
        rows.append({
            "metric": key,
            "value_a": val_a,
            "value_b": val_b,
            "diff": diff,
            "unit": get_field_unit(field_name),
            "reliability": get_field_reliability(key).value
        })
    
    return rows


# =============================================================================
# DRONE VS GCS SPLIT
# =============================================================================

def extract_drone_metrics(suite: ComprehensiveSuiteMetrics) -> Dict[str, Any]:
    """Extract drone-side metrics from a suite."""
    return {
        "mavproxy": suite.mavproxy_drone.model_dump(),
        "system": suite.system_drone.model_dump(),
        "power_energy": suite.power_energy.model_dump(),
        "fc_telemetry": suite.fc_telemetry.model_dump(),
    }


def extract_gcs_metrics(suite: ComprehensiveSuiteMetrics) -> Dict[str, Any]:
    """
    Extract GCS-side metrics from a suite.
    
    Note: Most GCS metrics are DEPRECATED per policy realignment.
    """
    return {
        "mavproxy": suite.mavproxy_gcs.model_dump(),
        "system": suite.system_gcs.model_dump(),
    }


def get_drone_vs_gcs_summary(suite: ComprehensiveSuiteMetrics) -> Dict[str, Any]:
    """Get comparative summary of drone vs GCS for a suite."""
    drone_msgs = suite.mavproxy_drone.mavproxy_drone_total_msgs_received
    gcs_msgs = suite.mavproxy_gcs.mavproxy_gcs_total_msgs_received
    
    return {
        "drone": {
            "msgs_received": drone_msgs,
            "seq_gaps": suite.mavproxy_drone.mavproxy_drone_seq_gap_count,
            "heartbeat_loss": suite.mavproxy_drone.mavproxy_drone_heartbeat_loss_count,
            "cpu_avg": suite.system_drone.cpu_usage_avg_percent,
            "memory_mb": suite.system_drone.memory_rss_mb,
            "power_w": suite.power_energy.power_avg_w,
        },
        "gcs": {
            "msgs_received": gcs_msgs,
            "msgs_received_reliability": ReliabilityClass.CONDITIONAL.value,
            "seq_gaps": suite.mavproxy_gcs.mavproxy_gcs_seq_gap_count,
            "seq_gaps_reliability": ReliabilityClass.CONDITIONAL.value,
        },
        "cross_side": {
            "msg_delivery_ratio": gcs_msgs / drone_msgs if drone_msgs > 0 else None,
        }
    }


# =============================================================================
# AGGREGATION (EXPLICIT ONLY)
# =============================================================================

def aggregate_by_kem_family(
    suites: List[ComprehensiveSuiteMetrics]
) -> pd.DataFrame:
    """
    Aggregate metrics by KEM family.
    
    This is an EXPLICIT aggregation - only called when user requests it.
    """
    df = suites_to_dataframe(suites)
    
    if df.empty:
        return pd.DataFrame()
    
    # Group by KEM family
    agg_cols = {
        "handshake.handshake_total_duration_ms": ["mean", "std", "min", "max"],
        "power_energy.power_avg_w": ["mean", "std"],
        "power_energy.energy_total_j": ["mean", "sum"],
    }
    
    available_cols = {c: agg for c, agg in agg_cols.items() if c in df.columns}
    
    if not available_cols:
        return pd.DataFrame()
    
    return df.groupby("crypto_identity.kem_family").agg(available_cols)


def aggregate_by_nist_level(
    suites: List[ComprehensiveSuiteMetrics]
) -> pd.DataFrame:
    """
    Aggregate metrics by NIST security level.
    
    This is an EXPLICIT aggregation - only called when user requests it.
    """
    df = suites_to_dataframe(suites)
    
    if df.empty:
        return pd.DataFrame()
    
    agg_cols = {
        "handshake.handshake_total_duration_ms": ["mean", "std", "count"],
        "power_energy.power_avg_w": ["mean", "std"],
        "power_energy.energy_total_j": ["mean"],
    }
    
    available_cols = {c: agg for c, agg in agg_cols.items() if c in df.columns}
    
    if not available_cols:
        return pd.DataFrame()
    
    return df.groupby("crypto_identity.suite_security_level").agg(available_cols)


# =============================================================================
# SCHEMA DEFINITION
# =============================================================================

def generate_schema_definition() -> List[SchemaField]:
    """Generate the full schema definition with metadata."""
    schema = []
    
    # This is a simplified version - in production would be auto-generated
    categories = {
        "run_context": [
            ("run_id", "string", "Unique run identifier"),
            ("suite_id", "string", "Suite identifier"),
            ("suite_index", "int", "Suite order within run"),
        ],
        "crypto_identity": [
            ("kem_algorithm", "string", "KEM algorithm name"),
            ("sig_algorithm", "string", "Signature algorithm name"),
            ("aead_algorithm", "string", "AEAD algorithm name"),
            ("suite_security_level", "string", "NIST security level (L1-L5)"),
        ],
        "handshake": [
            ("handshake_total_duration_ms", "float", "Total handshake time"),
            ("handshake_success", "bool", "Whether handshake succeeded"),
        ],
        "power_energy": [
            ("power_avg_w", "float", "Average power consumption"),
            ("power_peak_w", "float", "Peak power consumption"),
            ("energy_total_j", "float", "Total energy consumed"),
        ],
        "validation": [
            ("benchmark_pass_fail", "string", "Overall benchmark result"),
            ("success_rate_percent", "float", "Percentage of successful operations"),
        ],
    }
    
    for category, fields in categories.items():
        for field_name, field_type, description in fields:
            full_path = f"{category}.{field_name}"
            schema.append(SchemaField(
                name=field_name,
                category=category,
                type=field_type,
                unit=get_field_unit(field_name),
                reliability=get_field_reliability(full_path),
                description=description
            ))
    
    return schema
