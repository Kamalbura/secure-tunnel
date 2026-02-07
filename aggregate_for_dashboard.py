#!/usr/bin/env python3
"""
aggregate_for_dashboard.py

Reads the comprehensive drone + GCS JSON pairs from:
    logs/benchmarks/live_run_{run_id}/comprehensive/

Merges each drone+GCS pair into a single combined JSON per suite,
then copies both the individual files and combined files into the
dashboard ingest folder:
    logs/benchmarks/runs/no-ddos/

Also produces a GCS JSONL validation file (gcs_suite_metrics.jsonl)
that the dashboard ingest can merge for latency/system/mavlink data.

Usage:
    python aggregate_for_dashboard.py --run-id 20260207_144051
    python aggregate_for_dashboard.py --run-id 20260207_144051 --scenario no-ddos
"""

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List

ROOT = Path(__file__).resolve().parent
LOGS_DIR = ROOT / "logs" / "benchmarks"


def safe_get(d: dict, *keys, default=None):
    """Nested dict get with fallback."""
    for k in keys:
        if isinstance(d, dict):
            d = d.get(k)
        else:
            return default
    return d if d is not None else default


def merge_drone_gcs(drone: Dict[str, Any], gcs: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge drone-side and GCS-side comprehensive metrics into a single
    combined record. The drone side is authoritative for most fields;
    the GCS side fills in GCS-specific metrics.
    """
    merged = json.loads(json.dumps(drone))  # deep copy

    # --- run_context: fill GCS host info from GCS file if missing ---
    rc = merged.setdefault("run_context", {})
    gcs_rc = gcs.get("run_context", {})
    if not rc.get("gcs_hostname"):
        rc["gcs_hostname"] = gcs_rc.get("gcs_hostname")
    if not rc.get("gcs_ip"):
        rc["gcs_ip"] = gcs_rc.get("gcs_ip")
    if not rc.get("python_env_gcs"):
        rc["python_env_gcs"] = gcs_rc.get("python_env_gcs")
    if not rc.get("kernel_version_gcs"):
        rc["kernel_version_gcs"] = gcs_rc.get("kernel_version_gcs")

    # --- system_gcs: replace with GCS-reported values (they labeled it system_drone in their file) ---
    gcs_sys = gcs.get("system_drone", {})
    if gcs_sys and gcs_sys.get("cpu_usage_avg_percent") is not None:
        merged["system_gcs"] = {
            "cpu_usage_avg_percent": gcs_sys.get("cpu_usage_avg_percent"),
            "cpu_usage_peak_percent": gcs_sys.get("cpu_usage_peak_percent"),
            "cpu_freq_mhz": gcs_sys.get("cpu_freq_mhz"),
            "memory_rss_mb": gcs_sys.get("memory_rss_mb"),
            "memory_vms_mb": gcs_sys.get("memory_vms_mb"),
            "thread_count": gcs_sys.get("thread_count"),
            "temperature_c": gcs_sys.get("temperature_c"),
            "uptime_s": gcs_sys.get("uptime_s"),
            "load_avg_1m": gcs_sys.get("load_avg_1m"),
            "load_avg_5m": gcs_sys.get("load_avg_5m"),
            "load_avg_15m": gcs_sys.get("load_avg_15m"),
        }

    # --- mavproxy_gcs: merge GCS MAVLink stats ---
    gcs_mavgcs = gcs.get("mavproxy_gcs", {})
    if gcs_mavgcs:
        mg = merged.setdefault("mavproxy_gcs", {})
        if mg.get("mavproxy_gcs_total_msgs_received") is None:
            mg["mavproxy_gcs_total_msgs_received"] = gcs_mavgcs.get("mavproxy_gcs_total_msgs_received")
        if mg.get("mavproxy_gcs_seq_gap_count") is None:
            mg["mavproxy_gcs_seq_gap_count"] = gcs_mavgcs.get("mavproxy_gcs_seq_gap_count")

    # --- handshake: pick the larger/more complete value ---
    gcs_hs = gcs.get("handshake", {})
    merged_hs = merged.setdefault("handshake", {})
    gcs_duration = gcs_hs.get("handshake_total_duration_ms")
    drone_duration = merged_hs.get("handshake_total_duration_ms")
    # GCS sees more total time (network + crypto); prefer it if both exist
    if gcs_duration and drone_duration:
        merged_hs["handshake_gcs_duration_ms"] = gcs_duration
        merged_hs["handshake_drone_duration_ms"] = drone_duration

    # --- observability from GCS ---
    gcs_obs = gcs.get("observability", {})
    if gcs_obs.get("log_sample_count"):
        merged.setdefault("observability_gcs", gcs_obs)

    # --- mavlink_integrity: merge if drone side lacks it ---
    gcs_mi = gcs.get("mavlink_integrity", {})
    mi = merged.setdefault("mavlink_integrity", {})
    for field in [
        "mavlink_sysid", "mavlink_compid", "mavlink_protocol_version",
        "mavlink_packet_crc_error_count", "mavlink_decode_error_count",
        "mavlink_msg_drop_count", "mavlink_out_of_order_count",
        "mavlink_duplicate_count", "mavlink_message_latency_avg_ms",
    ]:
        if mi.get(field) is None and gcs_mi.get(field) is not None:
            mi[field] = gcs_mi[field]

    return merged


def build_gcs_jsonl_entry(gcs: Dict[str, Any], suite_id: str, run_id: str) -> Dict[str, Any]:
    """Build a GCS JSONL entry from the GCS comprehensive file."""
    entry: Dict[str, Any] = {
        "run_id": run_id,
        "suite_id": suite_id,
        "suite": suite_id,
    }

    # system_gcs (GCS reports its own system as "system_drone" in its file)
    gcs_sys = gcs.get("system_drone", {})
    if gcs_sys and gcs_sys.get("cpu_usage_avg_percent") is not None:
        entry["system_gcs"] = gcs_sys

    # latency_jitter
    lj = gcs.get("latency_jitter", {})
    if lj:
        entry["latency_jitter"] = lj

    # mavlink_validation from GCS mavproxy_gcs
    mg = gcs.get("mavproxy_gcs", {})
    if mg:
        entry["mavlink_validation"] = {
            "total_msgs_received": mg.get("mavproxy_gcs_total_msgs_received"),
            "seq_gap_count": mg.get("mavproxy_gcs_seq_gap_count"),
        }

    return entry


def aggregate_run(run_id: str, scenario: str = "no-ddos") -> dict:
    """
    Aggregate a single benchmark run for dashboard consumption.
    
    Returns a summary dict with counts and paths.
    """
    src_dir = LOGS_DIR / f"live_run_{run_id}" / "comprehensive"
    dst_dir = LOGS_DIR / "runs" / scenario
    dst_dir.mkdir(parents=True, exist_ok=True)

    if not src_dir.exists():
        print(f"ERROR: Source directory not found: {src_dir}")
        sys.exit(1)

    # Discover all files
    all_files = list(src_dir.glob("*.json"))
    drone_files = {}
    gcs_files = {}

    for f in all_files:
        stem = f.stem
        if stem.endswith("_drone"):
            key = stem.rsplit("_drone", 1)[0]
            drone_files[key] = f
        elif stem.endswith("_gcs"):
            key = stem.rsplit("_gcs", 1)[0]
            gcs_files[key] = f

    print(f"Source: {src_dir}")
    print(f"  Drone files: {len(drone_files)}")
    print(f"  GCS files:   {len(gcs_files)}")

    # Track stats
    merged_count = 0
    drone_only_count = 0
    gcs_only_count = 0
    errors = []
    gcs_jsonl_entries = []

    # Merge matching pairs
    all_keys = sorted(set(list(drone_files.keys()) + list(gcs_files.keys())))

    for key in all_keys:
        drone_path = drone_files.get(key)
        gcs_path = gcs_files.get(key)

        try:
            drone_data = None
            gcs_data = None

            if drone_path:
                with open(drone_path, "r", encoding="utf-8") as f:
                    drone_data = json.load(f)
            if gcs_path:
                with open(gcs_path, "r", encoding="utf-8") as f:
                    gcs_data = json.load(f)

            if drone_data and gcs_data:
                # Merge both sides
                combined = merge_drone_gcs(drone_data, gcs_data)
                merged_count += 1

                # Build GCS JSONL entry
                suite_id = combined.get("run_context", {}).get("suite_id", "")
                rid = combined.get("run_context", {}).get("run_id", run_id)
                gcs_jsonl_entries.append(build_gcs_jsonl_entry(gcs_data, suite_id, rid))
            elif drone_data:
                combined = drone_data
                drone_only_count += 1
            else:
                combined = gcs_data
                gcs_only_count += 1

            # Write the drone file (dashboard expects _drone.json)
            out_name = f"{key}_drone.json"
            out_path = dst_dir / out_name
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(combined, f, indent=2)

            # Also write the GCS file if it exists (dashboard can pair them)
            if gcs_data:
                gcs_out_name = f"{key}_gcs.json"
                gcs_out_path = dst_dir / gcs_out_name
                with open(gcs_out_path, "w", encoding="utf-8") as f:
                    json.dump(gcs_data, f, indent=2)

        except Exception as e:
            errors.append((key, str(e)))
            print(f"  ERROR: {key}: {e}")

    # Write GCS JSONL for dashboard ingest merge
    gcs_jsonl_path = dst_dir / "gcs_suite_metrics.jsonl"
    with open(gcs_jsonl_path, "w", encoding="utf-8") as f:
        for entry in gcs_jsonl_entries:
            f.write(json.dumps(entry) + "\n")

    # Copy the benchmark summary
    summary_src = LOGS_DIR / f"live_run_{run_id}" / f"benchmark_summary_{run_id}.json"
    if summary_src.exists():
        shutil.copy2(summary_src, dst_dir / f"benchmark_summary_{run_id}.json")

    summary = {
        "run_id": run_id,
        "scenario": scenario,
        "destination": str(dst_dir),
        "total_suites": len(all_keys),
        "merged_drone_gcs": merged_count,
        "drone_only": drone_only_count,
        "gcs_only": gcs_only_count,
        "gcs_jsonl_entries": len(gcs_jsonl_entries),
        "errors": len(errors),
        "error_details": errors,
    }

    return summary


def main():
    parser = argparse.ArgumentParser(description="Aggregate benchmark metrics for dashboard")
    parser.add_argument("--run-id", required=True, help="Benchmark run ID (e.g., 20260207_144051)")
    parser.add_argument("--scenario", default="no-ddos",
                        choices=["no-ddos", "ddos-xgboost", "ddos-txt"],
                        help="Dashboard scenario folder (default: no-ddos)")
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"  PQC Benchmark → Dashboard Aggregator")
    print(f"{'='*60}")
    print(f"  Run ID:   {args.run_id}")
    print(f"  Scenario: {args.scenario}")
    print(f"{'='*60}\n")

    result = aggregate_run(args.run_id, args.scenario)

    print(f"\n{'='*60}")
    print(f"  Aggregation Complete")
    print(f"{'='*60}")
    print(f"  Destination: {result['destination']}")
    print(f"  Total suites:        {result['total_suites']}")
    print(f"  Merged (drone+GCS):  {result['merged_drone_gcs']}")
    print(f"  Drone-only:          {result['drone_only']}")
    print(f"  GCS-only:            {result['gcs_only']}")
    print(f"  GCS JSONL entries:   {result['gcs_jsonl_entries']}")
    print(f"  Errors:              {result['errors']}")
    print(f"{'='*60}\n")

    if result['errors'] > 0:
        print("  Error details:")
        for key, err in result['error_details']:
            print(f"    {key}: {err}")
        print()

    # Validate — check final file count in destination
    dst = Path(result['destination'])
    drone_count = len(list(dst.glob("*_drone.json")))
    gcs_count = len(list(dst.glob("*_gcs.json")))
    jsonl_exists = (dst / "gcs_suite_metrics.jsonl").exists()

    print(f"  Validation:")
    print(f"    _drone.json files in {dst.name}/: {drone_count}")
    print(f"    _gcs.json files in {dst.name}/:   {gcs_count}")
    print(f"    gcs_suite_metrics.jsonl:           {'YES' if jsonl_exists else 'NO'}")
    print(f"\n  Dashboard ready: .\start-dashboard.ps1\n")

    return 0 if result['errors'] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
