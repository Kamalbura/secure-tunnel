"""Check clock offsets across suites."""
import json, os

src = 'logs/benchmarks/runs/no-ddos'
offsets = []
for f in sorted(os.listdir(src)):
    if '20260207' not in f or not f.endswith('_drone.json'):
        continue
    try:
        d = json.load(open(os.path.join(src, f)))
        off = d.get('run_context', {}).get('clock_offset_ms')
        suite = d.get('run_context', {}).get('suite_id', f)
        if off is not None:
            offsets.append((suite, off))
    except:
        pass

print(f"Suites with clock offset data: {len(offsets)}")
if offsets:
    vals = [o[1] for o in offsets]
    print(f"  Min offset:  {min(vals):.3f} ms")
    print(f"  Max offset:  {max(vals):.3f} ms")
    print(f"  Range:       {max(vals)-min(vals):.3f} ms")
    print(f"\nFirst 10:")
    for suite, off in offsets[:10]:
        print(f"  {off:>10.3f} ms  {suite}")
    unique = list(set(f"{v:.3f}" for v in vals))
    print(f"\nUnique offset values: {len(unique)}")
    for u in sorted(unique)[:10]:
        count = sum(1 for v in vals if f"{v:.3f}" == u)
        print(f"  {u} ms  ({count} suites)")
