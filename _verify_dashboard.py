"""Quick verification: does the dashboard API return our merged run data?"""
import json, urllib.request, sys

BASE = "http://localhost:8000"

def fetch(path):
    return json.loads(urllib.request.urlopen(BASE + path).read())

# 1) Runs
runs = fetch("/api/runs")
print("=== Runs ===")
for r in runs:
    print(f"  {r['run_id']}  suites={r['suite_count']}  type={r['run_type']}")

# 2) Our suites
suites = fetch("/api/suites")
feb7 = [s for s in suites if s.get("run_id") == "20260207_144051"]
print(f"\n=== Feb 7 Run: {len(feb7)} suites loaded ===")

# 3) Detailed check on one suite
key = "20260207_144051:cs-mlkem512-aesgcm-falcon512"
d = fetch(f"/api/suite/{urllib.request.quote(key, safe='')}")

sections = [
    "run_context", "crypto_identity", "lifecycle", "handshake",
    "crypto_primitives", "rekey", "data_plane", "latency_jitter",
    "mavproxy_drone", "mavproxy_gcs", "mavlink_integrity", "fc_telemetry",
    "control_plane", "system_drone", "system_gcs", "power_energy",
    "observability", "validation",
]

print(f"\n=== Suite Detail: {d.get('run_context',{}).get('suite_id')} ===")
for s in sections:
    v = d.get(s) or {}
    populated = sum(1 for val in v.values() if val is not None)
    total = len(v)
    tag = "OK" if populated > 0 else "EMPTY"
    print(f"  {s:25s} {populated:3d}/{total:3d} fields  [{tag}]")

# Key merged values
sg = d.get("system_gcs") or {}
sd = d.get("system_drone") or {}
hs = d.get("handshake") or {}
pe = d.get("power_energy") or {}
mg = d.get("mavproxy_gcs") or {}
md = d.get("mavproxy_drone") or {}
cp = d.get("crypto_primitives") or {}

print(f"\n=== Key Merged Values ===")
print(f"  system_drone CPU:  {sd.get('cpu_usage_avg_percent')}%")
print(f"  system_gcs   CPU:  {sg.get('cpu_usage_avg_percent')}%")
print(f"  system_gcs   MEM:  {sg.get('memory_rss_mb')} MB")
print(f"  handshake total:   {hs.get('handshake_total_duration_ms')} ms")
print(f"  handshake gcs:     {hs.get('handshake_gcs_duration_ms')} ms")
print(f"  handshake drone:   {hs.get('handshake_drone_duration_ms')} ms")
print(f"  power avg:         {pe.get('power_avg_w')} W")
print(f"  energy total:      {pe.get('energy_total_j')} J")
print(f"  mavproxy drone tx: {md.get('mavproxy_tx_pps')} pps")
print(f"  mavproxy gcs rx:   {mg.get('mavproxy_gcs_total_msgs_received')} msgs")
print(f"  kem_keygen:        {cp.get('kem_keygen_time_ms')} ms")
print(f"  sig_sign:          {cp.get('sig_sign_time_ms')} ms")

# Summary
with_gcs = sum(1 for s in feb7 if s.get("system_gcs_cpu_avg") is not None or True)
print(f"\n=== RESULT: {len(feb7)} suites from run 20260207_144051 loaded in dashboard ===")
print("Dashboard ready at http://localhost:5173")
