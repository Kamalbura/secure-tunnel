import json, pathlib
p = pathlib.Path(r"c:\Users\burak\ptojects\secure-tunnel\logs\benchmarks\analysis_metrics\observed_summary.json")
summary = json.load(p.open("r", encoding="utf-8"))["summary"]

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

null_expected_keys = {k for k in summary.keys() if any(k.startswith(p) for p in null_expected_prefixes)}
null_expected_keys.update({
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
})

mismatches = []
for k, s in summary.items():
    if k in null_expected_keys and s.get("all_zero"):
        mismatches.append(k)

print("MISMATCH_ZERO_FOR_NULL")
for k in sorted(mismatches):
    print(k)
