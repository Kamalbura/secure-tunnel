#!/usr/bin/env python3
"""
Verify comprehensive metrics output files.

Usage:
  python verify_metrics_output.py <path-to-json-or-jsonl>
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

REQUIRED_FIELDS: List[Tuple[str, ...]] = [
    ("run_context", "run_id"),
    ("run_context", "suite_id"),
    ("run_context", "clock_offset_ms"),
    ("crypto_identity", "kem_algorithm"),
    ("crypto_identity", "sig_algorithm"),
    ("crypto_identity", "aead_algorithm"),
    ("handshake", "handshake_success"),
    ("data_plane", "ptx_in"),
    ("data_plane", "enc_out"),
    ("data_plane", "bytes_sent"),
    ("data_plane", "bytes_received"),
    ("data_plane", "goodput_mbps"),
    ("data_plane", "wire_rate_mbps"),
    ("rekey", "rekey_attempts"),
    ("rekey", "rekey_success"),
    ("rekey", "rekey_failure"),
    ("control_plane", "policy_name"),
    ("control_plane", "policy_suite_index"),
    ("control_plane", "policy_total_suites"),
    ("power_energy", "voltage_avg_v"),
    ("power_energy", "current_avg_a"),
]


def _get_path(data: Dict[str, Any], path: Tuple[str, ...]) -> Any:
    cur: Any = data
    for part in path:
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def _iter_records(path: Path) -> Iterable[Dict[str, Any]]:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    if text.startswith("{"):
        return [json.loads(text)]
    records = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        records.append(json.loads(line))
    return records


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python verify_metrics_output.py <path>")
        return 2

    path = Path(sys.argv[1])
    if not path.exists():
        print(f"Path not found: {path}")
        return 2

    records = list(_iter_records(path))
    if not records:
        print("No records found.")
        return 1

    missing_total = 0
    for idx, rec in enumerate(records, start=1):
        missing = []
        for field_path in REQUIRED_FIELDS:
            if _get_path(rec, field_path) is None:
                missing.append(".".join(field_path))
        if missing:
            missing_total += len(missing)
            print(f"Record {idx}: missing {len(missing)} fields")
            for entry in missing:
                print(f"  - {entry}")

    if missing_total == 0:
        print("All required fields present.")
        return 0

    print(f"Total missing fields: {missing_total}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
