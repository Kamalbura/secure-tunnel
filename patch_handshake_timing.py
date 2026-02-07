#!/usr/bin/env python3
"""
patch_handshake_timing.py

Patches existing benchmark JSON files to replace the inflated
handshake_total_duration_ms (which includes orchestration overhead)
with the proxy's protocol_handshake_duration_ms (ground truth from
time.perf_counter_ns inside core/handshake.py).

This corrects data for:
  1) Source comprehensive files: logs/benchmarks/live_run_*/comprehensive/
  2) Dashboard files:           logs/benchmarks/runs/no-ddos/

Usage:
    python patch_handshake_timing.py --run-id 20260207_144051
    python patch_handshake_timing.py --run-id 20260207_144051 --dry-run
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOGS = ROOT / "logs" / "benchmarks"


def patch_file(path: Path, dry_run: bool = False) -> dict:
    """
    Patch a single JSON file.  Returns a dict with the result.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, ValueError) as e:
        return {"file": path.name, "status": "skipped", "reason": f"invalid JSON: {e}"}

    hs = data.get("handshake", {})
    protocol_ms = hs.get("protocol_handshake_duration_ms")
    old_total = hs.get("handshake_total_duration_ms")

    # Also check crypto_primitives for rekey_ms / handshake_total_ns
    # in case protocol_handshake_duration_ms was not populated
    if protocol_ms is None:
        cp = data.get("crypto_primitives", {})
        rekey = cp.get("rekey_ms")
        if isinstance(rekey, (int, float)) and rekey > 0:
            protocol_ms = rekey
        else:
            total_ns = cp.get("handshake_total_ns")
            if isinstance(total_ns, (int, float)) and total_ns > 0:
                protocol_ms = total_ns / 1_000_000.0

    if not isinstance(protocol_ms, (int, float)) or protocol_ms <= 0:
        return {
            "file": path.name,
            "status": "skipped",
            "reason": "no protocol_handshake_duration_ms found",
        }

    if old_total is not None and abs(old_total - protocol_ms) < 0.01:
        return {
            "file": path.name,
            "status": "already_correct",
            "value_ms": round(protocol_ms, 3),
        }

    # Apply patch
    hs["handshake_total_duration_ms"] = float(protocol_ms)
    hs["end_to_end_handshake_duration_ms"] = float(protocol_ms)
    hs["protocol_handshake_duration_ms"] = float(protocol_ms)

    # Preserve original value for audit trail
    if old_total is not None:
        hs["_original_scheduler_duration_ms"] = float(old_total)

    data["handshake"] = hs

    if not dry_run:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    return {
        "file": path.name,
        "status": "patched",
        "old_ms": round(old_total, 1) if old_total else None,
        "new_ms": round(protocol_ms, 3),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Patch handshake timing in benchmark JSONs"
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--scenario", default="no-ddos")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would change without writing")
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"  Handshake Timing Patcher")
    print(f"  {'(DRY RUN)' if args.dry_run else '(LIVE WRITE)'}")
    print(f"{'='*60}")

    # Collect all directories to patch
    dirs_to_patch = []
    src_dir = LOGS / f"live_run_{args.run_id}" / "comprehensive"
    if src_dir.exists():
        dirs_to_patch.append(("source", src_dir))
    dash_dir = LOGS / "runs" / args.scenario
    if dash_dir.exists():
        dirs_to_patch.append(("dashboard", dash_dir))

    if not dirs_to_patch:
        print("  ERROR: No directories found to patch.")
        return 1

    total_patched = 0
    total_skipped = 0
    total_correct = 0

    for label, d in dirs_to_patch:
        json_files = sorted(d.glob("*.json"))
        print(f"\n  [{label}] {d}")
        print(f"  JSON files found: {len(json_files)}")

        for jf in json_files:
            # Skip non-suite files (benchmark_summary, etc.)
            if "benchmark_summary" in jf.name:
                continue
            result = patch_file(jf, dry_run=args.dry_run)
            status = result["status"]
            if status == "patched":
                total_patched += 1
                print(f"    PATCHED {result['file']}: "
                      f"{result['old_ms']}ms -> {result['new_ms']}ms")
            elif status == "already_correct":
                total_correct += 1
            else:
                total_skipped += 1

    print(f"\n{'='*60}")
    print(f"  Summary")
    print(f"{'='*60}")
    print(f"  Patched:          {total_patched}")
    print(f"  Already correct:  {total_correct}")
    print(f"  Skipped:          {total_skipped}")
    print(f"{'='*60}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
