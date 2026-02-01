import json, re, sys, csv, ast
from pathlib import Path
from dataclasses import fields

root = Path("c:/Users/burak/ptojects/secure-tunnel")

# Load core schema keys
sys.path.insert(0, str(root))
from core import metrics_schema as ms

def collect_schema_keys():
    schema_keys = set()
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
    for prefix, cls in categories:
        for f in fields(cls):
            schema_keys.add(f"{prefix}.{f.name}")
    return schema_keys

schema_keys = collect_schema_keys()

# Load observed JSONs (latest timestamp)
comp_dir = root / "logs" / "benchmarks" / "comprehensive"
pattern = re.compile(r"20260122_174341")
files = [p for p in comp_dir.glob("*_drone.json") if pattern.search(p.name)]

def flatten(d, prefix=""):
    out = {}
    if isinstance(d, dict):
        for k, v in d.items():
            key = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                out.update(flatten(v, key))
            else:
                out[key] = v
    else:
        out[prefix] = d
    return out

observed = set()
file_flat = {}
for f in files:
    data = json.loads(f.read_text(encoding="utf-8"))
    flat = flatten(data)
    file_flat[f.name] = flat
    observed.update(flat.keys())

# Summary stats
summary = {}
for key in sorted(observed):
    types = {}
    null_count = 0
    zero_count = 0
    nonzero_count = 0
    missing_count = 0
    for fname, flat in file_flat.items():
        if key not in flat:
            missing_count += 1
            continue
        v = flat[key]
        if v is None:
            null_count += 1
        else:
            t = type(v).__name__
            types[t] = types.get(t, 0) + 1
            if isinstance(v, (int, float)):
                if v == 0:
                    zero_count += 1
                else:
                    nonzero_count += 1
    summary[key] = {
        "missing": missing_count,
        "null": null_count,
        "zero": zero_count,
        "nonzero": nonzero_count,
        "types": ",".join(sorted(types.keys())),
        "all_zero": (zero_count == len(files) and null_count == 0 and nonzero_count == 0),
    }

# Backend model keys via AST (avoid pydantic import)
models_path = root / "dashboard" / "backend" / "models.py"
source = models_path.read_text(encoding="utf-8")
module = ast.parse(source)

class_fields = {}
for node in module.body:
    if isinstance(node, ast.ClassDef):
        fields_list = []
        for stmt in node.body:
            if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                fields_list.append((stmt.target.id, ast.get_source_segment(source, stmt.annotation) or ""))
        class_fields[node.name] = fields_list

MODEL_CLASS_NAMES = set(class_fields.keys())


def is_model(name):
    return name in MODEL_CLASS_NAMES


def extract_type_name(ann: str):
    ann = ann.replace("Optional[", "").replace("]", "")
    ann = ann.replace("Field(", "")
    return ann.strip()

backend_keys = set()

def walk_model(prefix, class_name):
    for field_name, ann in class_fields.get(class_name, []):
        type_name = extract_type_name(ann)
        key = f"{prefix}.{field_name}" if prefix else field_name
        if is_model(type_name):
            walk_model(key, type_name)
        else:
            backend_keys.add(key)

walk_model("", "ComprehensiveSuiteMetrics")

# Frontend usage keys (regex over TS/TSX)
frontend_dir = root / "dashboard" / "frontend" / "src"
frontend_keys = set()
pattern_suite = re.compile(r"\b(suite|comparisonSuiteA|comparisonSuiteB)\.(\w+(?:\.\w+)*)")
for path in frontend_dir.rglob("*.ts*"):
    text = path.read_text(encoding="utf-8")
    for match in pattern_suite.finditer(text):
        frontend_keys.add(match.group(2))

# Null-expected keys (from aggregator nulling rules)
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

null_expected_keys = {k for k in schema_keys if any(k.startswith(p) for p in null_expected_prefixes)}
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

# Build matrix
matrix_rows = []
for key in sorted(schema_keys):
    raw_present = key in observed
    backend_present = key in backend_keys
    frontend_used = key in frontend_keys
    all_zero = summary.get(key, {}).get("all_zero", False)
    classification = None
    if not raw_present:
        classification = "BROKEN"
    elif not backend_present:
        classification = "BROKEN"
    elif frontend_used:
        if key in null_expected_keys and all_zero:
            classification = "MISLEADING"
        else:
            classification = "CONSISTENT"
    else:
        classification = "UNUSED"
    matrix_rows.append({
        "metric_key": key,
        "raw_json": "present" if raw_present else "missing",
        "backend_model": "present" if backend_present else "missing",
        "frontend": "used" if frontend_used else "unused",
        "all_zero": bool(all_zero),
        "classification": classification,
    })

out_dir = root / "logs" / "benchmarks" / "analysis_metrics"
out_dir.mkdir(parents=True, exist_ok=True)

with (out_dir / "observed_summary.json").open("w", encoding="utf-8") as f:
    json.dump({"files": [p.name for p in files], "summary": summary}, f, indent=2)

with (out_dir / "schema_vs_observed.json").open("w", encoding="utf-8") as f:
    json.dump({
        "schema_keys": sorted(schema_keys),
        "observed_keys": sorted(observed),
        "extra_keys": sorted(observed - schema_keys),
        "missing_keys": sorted(schema_keys - observed),
    }, f, indent=2)

with (out_dir / "consistency_matrix.csv").open("w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["metric_key","raw_json","backend_model","frontend","all_zero","classification"])
    writer.writeheader()
    for row in matrix_rows:
        writer.writerow(row)

print(str(out_dir))
