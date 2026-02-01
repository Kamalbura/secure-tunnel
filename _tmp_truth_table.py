import csv, sys
from dataclasses import fields
from typing import get_args
from pathlib import Path

root = Path("c:/Users/burak/ptojects/secure-tunnel")
sys.path.insert(0, str(root))
from core import metrics_schema as ms

categories = [
    ("run_context", ms.RunContextMetrics),
    ("crypto_identity", ms.SuiteCryptoIdentity),
    ("lifecycle", ms.SuiteLifecycleTimeline),
    ("handshake", ms.HandshakeMetrics),
    ("crypto_primitives", ms.CryptoPrimitiveBreakdown),
    ("rekey", ms.RekeyMetrics),
    ("data_plane", ms.DataPlaneMetrics),
    ("latency_jitter", ms.LatencyJitterMetrics),
    ("mavproxy_drone", ms.MavProxyDroneMetrics),
    ("mavproxy_gcs", ms.MavProxyGcsMetrics),
    ("mavlink_integrity", ms.MavLinkIntegrityMetrics),
    ("fc_telemetry", ms.FlightControllerTelemetry),
    ("control_plane", ms.ControlPlaneMetrics),
    ("system_drone", ms.SystemResourcesDrone),
    ("system_gcs", ms.SystemResourcesGcs),
    ("power_energy", ms.PowerEnergyMetrics),
    ("observability", ms.ObservabilityMetrics),
    ("validation", ms.ValidationMetrics),
]

origin_map = {
    "run_context": "MetricsAggregator.start_suite()/finalize_suite()",
    "crypto_identity": "MetricsAggregator.start_suite()",
    "lifecycle": "MetricsAggregator.start_suite()/record_handshake_end()/finalize_suite()",
    "handshake": "MetricsAggregator.record_handshake_start()/record_handshake_end()/record_crypto_primitives()",
    "crypto_primitives": "MetricsAggregator.record_crypto_primitives()",
    "rekey": "MetricsAggregator.record_data_plane_metrics()/finalize_suite()",
    "data_plane": "MetricsAggregator.record_data_plane_metrics()/finalize_suite()",
    "latency_jitter": "MetricsAggregator.finalize_suite() via MavLinkMetricsCollector",
    "mavproxy_drone": "MetricsAggregator.finalize_suite() via MavLinkMetricsCollector",
    "mavproxy_gcs": "MetricsAggregator._merge_peer_data() or gcs collector",
    "mavlink_integrity": "MetricsAggregator.finalize_suite() via MavLinkMetricsCollector",
    "fc_telemetry": "MetricsAggregator.finalize_suite() via MavLinkMetricsCollector",
    "control_plane": "MetricsAggregator.record_control_plane_metrics()",
    "system_drone": "MetricsAggregator.finalize_suite() from SystemCollector samples",
    "system_gcs": "MetricsAggregator._merge_peer_data() (optional)",
    "power_energy": "MetricsAggregator.finalize_suite() from PowerCollector",
    "observability": "MetricsAggregator.finalize_suite()",
    "validation": "MetricsAggregator.finalize_suite()",
}

phase_map = {
    "run_context": "start/end",
    "crypto_identity": "start",
    "lifecycle": "start/handshake/end",
    "handshake": "handshake",
    "crypto_primitives": "handshake",
    "rekey": "data_plane/end",
    "data_plane": "data_plane/end",
    "latency_jitter": "end",
    "mavproxy_drone": "end",
    "mavproxy_gcs": "end",
    "mavlink_integrity": "end",
    "fc_telemetry": "end",
    "control_plane": "control_plane",
    "system_drone": "sampling/end",
    "system_gcs": "merge/end",
    "power_energy": "sampling/end",
    "observability": "end",
    "validation": "end",
}

side_map = {
    "run_context": "DRONE+GCS",
    "crypto_identity": "DRONE+GCS",
    "lifecycle": "DRONE+GCS",
    "handshake": "DRONE+GCS",
    "crypto_primitives": "DRONE",
    "rekey": "DRONE",
    "data_plane": "DRONE",
    "latency_jitter": "DRONE (authoritative), GCS optional",
    "mavproxy_drone": "DRONE",
    "mavproxy_gcs": "GCS (validation)",
    "mavlink_integrity": "DRONE",
    "fc_telemetry": "DRONE",
    "control_plane": "DRONE+GCS",
    "system_drone": "DRONE",
    "system_gcs": "GCS optional",
    "power_energy": "DRONE",
    "observability": "DRONE",
    "validation": "DRONE",
}

# Keys explicitly nulled when missing (from MetricsAggregator.finalize_suite)
null_expected_prefixes = {
    "crypto_primitives.",
    "data_plane.",
    "rekey.",
    "power_energy.",
    "system_drone.",
    "observability.",
    "validation.",
    "latency_jitter.",
}

null_expected_exact = {
    "run_context.gcs_hostname",
    "run_context.gcs_ip",
    "run_context.python_env_gcs",
    "run_context.git_commit_hash",
    "run_context.drone_hostname",
    "run_context.drone_ip",
    "run_context.python_env_drone",
    "run_context.kernel_version_gcs",
    "run_context.kernel_version_drone",
    "run_context.liboqs_version",
}

out_dir = root / "logs" / "benchmarks" / "analysis_metrics"
out_dir.mkdir(parents=True, exist_ok=True)
path = out_dir / "metrics_truth_table.csv"

with path.open("w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=[
        "metric_key",
        "category",
        "type_hint",
        "origin_function",
        "trigger",
        "nullable_expected",
        "zero_valid",
        "side",
        "lifecycle_phase",
    ])
    writer.writeheader()
    for category, cls in categories:
        for field in fields(cls):
            type_hint = str(field.type)
            origin = origin_map.get(category, "")
            trigger = origin
            phase = phase_map.get(category, "")
            side = side_map.get(category, "")
            args = get_args(field.type)
            nullable = any(a is type(None) for a in args)
            key = f"{category}.{field.name}"
            if key in null_expected_exact or any(key.startswith(p) for p in null_expected_prefixes):
                zero_valid = "no (null when missing)"
            else:
                zero_valid = "unknown"
            writer.writerow({
                "metric_key": key,
                "category": category,
                "type_hint": type_hint,
                "origin_function": origin,
                "trigger": trigger,
                "nullable_expected": str(nullable),
                "zero_valid": zero_valid,
                "side": side,
                "lifecycle_phase": phase,
            })

print(str(path))
