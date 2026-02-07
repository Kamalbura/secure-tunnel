"""Handshake timing forensic analysis."""
import json

f1 = 'logs/benchmarks/live_run_20260207_144051/comprehensive/20260207_144051_cs-mlkem512-aesgcm-falcon512_drone.json'
f2 = 'logs/benchmarks/live_run_20260207_144051/comprehensive/20260207_144051_cs-mlkem512-aesgcm-falcon512_gcs.json'
d = json.load(open(f1))
g = json.load(open(f2))

print('=== DRONE handshake ===')
hs = d['handshake']
for k, v in hs.items():
    print(f'  {k}: {v}')

print('\n=== GCS handshake ===')
ghs = g['handshake']
for k, v in ghs.items():
    print(f'  {k}: {v}')

print('\n=== DRONE lifecycle ===')
lc = d.get('lifecycle', {})
for k, v in lc.items():
    print(f'  {k}: {v}')

print('\n=== GCS lifecycle ===')
glc = g.get('lifecycle', {})
for k, v in glc.items():
    print(f'  {k}: {v}')

print('\n=== DRONE run_context (clock) ===')
rc = d.get('run_context', {})
for key in ['clock_offset_ms', 'run_start_time_wall', 'drone_hostname', 'gcs_hostname']:
    print(f'  {key}: {rc.get(key)}')

print('\n=== GCS run_context (clock) ===')
grc = g.get('run_context', {})
for key in ['clock_offset_ms', 'run_start_time_wall', 'gcs_hostname', 'drone_hostname']:
    print(f'  {key}: {grc.get(key)}')

print('\n=== DRONE crypto_primitives ===')
cp = d.get('crypto_primitives', {})
for k, v in cp.items():
    print(f'  {k}: {v}')

print('\n=== Comparison: drone_total vs GCS_total ===')
dt = hs.get('handshake_total_duration_ms', 0)
gt = ghs.get('handshake_total_duration_ms', 0)
diff = dt - gt
print(f'  Drone total:  {dt:.3f} ms')
print(f'  GCS total:    {gt:.3f} ms')
print(f'  Difference:   {diff:.3f} ms  (drone sees {diff:.0f}ms more)')
print(f'  GCS is ~{gt:.0f}ms which is suspiciously close to 2000ms')
