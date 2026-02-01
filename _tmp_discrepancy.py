import json, re, csv
from pathlib import Path

root = Path("c:/Users/burak/ptojects/secure-tunnel")
analysis_dir = root / "logs" / "benchmarks" / "analysis_metrics"
sv = json.load((analysis_dir / "schema_vs_observed.json").open("r", encoding="utf-8"))
summary = json.load((analysis_dir / "observed_summary.json").open("r", encoding="utf-8"))
files = summary.get("files", [])
summary = summary.get("summary", {})

# pick a representative evidence file
sample_file = files[0] if files else ""

# null-expected keys
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

rows = []

# missing schema keys
for key in sv.get("missing_keys", []):
    rows.append({
        "metric": key,
        "expected_behavior": "present in schema",
        "observed_value": "missing",
        "classification": "missing",
        "evidence_file": sample_file,
    })

# extra keys
for key in sv.get("extra_keys", []):
    rows.append({
        "metric": key,
        "expected_behavior": "not in schema",
        "observed_value": "present",
        "classification": "legacy_or_unknown",
        "evidence_file": sample_file,
    })

# zero-for-null mismatches
for key, stats in summary.items():
    if key in null_expected_exact or any(key.startswith(p) for p in null_expected_prefixes):
        if stats.get("all_zero"):
            rows.append({
                "metric": key,
                "expected_behavior": "null when not collected",
                "observed_value": "all_zero",
                "classification": "present_but_impossible",
                "evidence_file": sample_file,
            })

out_path = analysis_dir / "discrepancy_table.csv"
with out_path.open("w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["metric","expected_behavior","observed_value","classification","evidence_file"])
    writer.writeheader()
    for row in rows:
        writer.writerow(row)

print(str(out_path))
