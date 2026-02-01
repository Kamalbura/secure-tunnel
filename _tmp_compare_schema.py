import json, re, sys
from pathlib import Path
from dataclasses import fields

sys.path.insert(0, "c:/Users/burak/ptojects/secure-tunnel")
from core import metrics_schema as ms

# build schema keys
def collect_keys(prefix, cls):
    return [f"{prefix}.{f.name}" for f in fields(cls)]

schema_keys = set()
for prefix, cls in [
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
]:
    schema_keys.update(collect_keys(prefix, cls))

# load observed keys from latest epoch

dir_path = Path("c:/Users/burak/ptojects/secure-tunnel/logs/benchmarks/comprehensive")
pattern = re.compile(r"20260122_174341")
files = [p for p in dir_path.glob("*_drone.json") if pattern.search(p.name)]


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
for f in files:
    data = json.loads(f.read_text(encoding="utf-8"))
    observed.update(flatten(data).keys())

extra = sorted(observed - schema_keys)
missing = sorted(schema_keys - observed)

print("SCHEMA_KEYS", len(schema_keys))
print("OBSERVED_KEYS", len(observed))
print("EXTRA_KEYS", len(extra))
print("MISSING_KEYS", len(missing))
print("EXTRA_START")
for k in extra:
    print(k)
print("EXTRA_END")
print("MISSING_START")
for k in missing:
    print(k)
print("MISSING_END")
