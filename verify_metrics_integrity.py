#!/usr/bin/env python3
"""
Verify metrics integrity for comprehensive suite outputs.

Checks:
- Forbidden schema-only fields are absent
- MAVLink/MAVProxy counters reset per suite
- Handshake duration present when success is true

Usage:
  python verify_metrics_integrity.py <path-to-json-or-directory>
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

FORBIDDEN_KEYS = {
    # Removed categories/fields
    "latency_jitter",
    "system_gcs",
    "handshake_rtt_ms",
    "hkdf_extract_time_ms",
    "hkdf_expand_time_ms",
    "suite_traffic_start_time",
    "suite_traffic_end_time",
    "suite_rekey_start_time",
    "suite_rekey_end_time",
    "suite_blackout_count",
    "suite_blackout_total_ms",
    "mavproxy_gcs_tx_pps",
    "mavproxy_gcs_rx_pps",
    "mavproxy_gcs_total_msgs_sent",
    "mavproxy_gcs_msg_type_counts",
    "mavproxy_gcs_heartbeat_interval_ms",
    "mavproxy_gcs_heartbeat_loss_count",
    "mavproxy_gcs_reconnect_count",
    "mavproxy_gcs_cmd_sent_count",
    "mavproxy_gcs_cmd_ack_received_count",
    "mavproxy_gcs_cmd_ack_latency_avg_ms",
    "mavproxy_gcs_cmd_ack_latency_p95_ms",
    "mavproxy_gcs_stream_rate_hz",
    "mavproxy_gcs_log_path",
    "mavproxy_drone_reconnect_count",
    "mavproxy_drone_log_path",
    "mavlink_message_latency_p95_ms",
    "fc_gps_fix_type",
    "fc_gps_satellites",
    "fc_altitude_m",
    "fc_groundspeed_mps",
    "thermal_throttle_events",
    "disk_usage_percent",
    "network_rx_bytes",
    "network_tx_bytes",
    "energy_per_rekey_j",
    "energy_per_second_j",
    "power_samples",
    "log_drop_count",
    "trace_file_path",
    "power_trace_file_path",
    "traffic_trace_file_path",
    "termination_reason",
    "data_completeness_percent",
    "schema_validation_errors",
    "kem_parameter_set",
    "sig_parameter_set",
    "aead_mode",
    "suite_tier",
    "suite_order_index",
}


def _iter_records(path: Path) -> Iterable[Dict[str, Any]]:
    if path.is_dir():
        for p in sorted(path.glob("*.json")):
            try:
                yield json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue
        return
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return
    if text.startswith("{"):
        yield json.loads(text)
        return
    for line in text.splitlines():
        line = line.strip()
        if line:
            yield json.loads(line)


def _walk_keys(obj: Any, found: List[Tuple[str, str]] , prefix: str = "") -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            path = f"{prefix}.{k}" if prefix else k
            if k in FORBIDDEN_KEYS or path in FORBIDDEN_KEYS:
                found.append((path, k))
            _walk_keys(v, found, path)
    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            _walk_keys(item, found, f"{prefix}[{idx}]")


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python verify_metrics_integrity.py <path>")
        return 2

    target = Path(sys.argv[1])
    if not target.exists():
        print(f"Path not found: {target}")
        return 2

    records = list(_iter_records(target))
    if not records:
        print("No records found.")
        return 1

    errors = 0

    # Forbidden fields check
    for idx, rec in enumerate(records, start=1):
        found: List[Tuple[str, str]] = []
        _walk_keys(rec, found)
        if found:
            errors += len(found)
            print(f"Record {idx}: forbidden fields present:")
            for path, _ in found:
                print(f"  - {path}")

    # Per-suite reset checks (by run_id, suite_index)
    by_run: Dict[str, List[Dict[str, Any]]] = {}
    for rec in records:
        rc = rec.get("run_context", {})
        run_id = rc.get("run_id", "unknown")
        by_run.setdefault(run_id, []).append(rec)

    for run_id, suites in by_run.items():
        suites_sorted = sorted(suites, key=lambda r: r.get("run_context", {}).get("suite_index", 0))
        last_start = None
        for idx, rec in enumerate(suites_sorted):
            mav = rec.get("mavproxy_drone", {})
            start_time = mav.get("mavproxy_drone_start_time", 0.0)
            end_time = mav.get("mavproxy_drone_end_time", 0.0)
            if start_time and end_time and end_time < start_time:
                errors += 1
                print(f"Run {run_id} suite[{idx}]: mavproxy start_time > end_time")
            if last_start is not None and start_time == last_start and start_time != 0:
                errors += 1
                print(f"Run {run_id} suite[{idx}]: mavproxy start_time did not reset")
            last_start = start_time

        # Handshake integrity
        for idx, rec in enumerate(suites_sorted):
            hs = rec.get("handshake", {})
            if hs.get("handshake_success") and (hs.get("handshake_total_duration_ms", 0) or 0) <= 0:
                errors += 1
                print(f"Run {run_id} suite[{idx}]: handshake_success but duration is 0")

    if errors == 0:
        print("Integrity checks passed.")
        return 0

    print(f"Integrity checks failed: {errors} issue(s)")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
