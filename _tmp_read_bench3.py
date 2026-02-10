#!/usr/bin/env python3
"""Inspect bench_ddos_results – v3 (results are lists)."""
import json, statistics

SRC = "bench_ddos_results/20260209_090851"

# 1. Show first result item structure
baseline = json.load(open(f"{SRC}/baseline.json"))
xgb_data = json.load(open(f"{SRC}/xgb.json"))
tst_data = json.load(open(f"{SRC}/tst.json"))

b_results = baseline["results"]
x_results = xgb_data["results"]
t_results = tst_data["results"]

print("=== STRUCTURE OF A SINGLE RESULT ITEM ===")
print(f"Type: {type(b_results[0])}")
print(f"Keys: {list(b_results[0].keys()) if isinstance(b_results[0], dict) else 'N/A'}")
print(f"Full first item:\n{json.dumps(b_results[0], indent=2)}")

# 2. Build lookup by suite_id
def make_lookup(results):
    return {r["suite_id"]: r for r in results}

b_map = make_lookup(b_results)
x_map = make_lookup(x_results)
t_map = make_lookup(t_results)

# 3. Discover numeric fields
first = b_results[0]
numeric_fields = [k for k, v in first.items() if isinstance(v, (int, float)) and k != "suite_id"]
print(f"\n\nNumeric fields: {numeric_fields}")

# 4. Per-metric cross-run stats
print("\n" + "="*80)
print("CROSS-RUN METRIC COMPARISON (72 suites)")
print("="*80)

overhead_summary = {}

for field in numeric_fields:
    b_vals = [b_map[s].get(field, 0) for s in b_map]
    x_vals = [x_map[s].get(field, 0) for s in x_map]
    t_vals = [t_map[s].get(field, 0) for s in t_map]
    
    b_mean = statistics.mean(b_vals)
    x_mean = statistics.mean(x_vals)
    t_mean = statistics.mean(t_vals)
    
    print(f"\n--- {field} ---")
    print(f"  Baseline: mean={b_mean:.4f}, median={statistics.median(b_vals):.4f}, stdev={statistics.stdev(b_vals):.4f}, min={min(b_vals):.4f}, max={max(b_vals):.4f}")
    print(f"  XGBoost:  mean={x_mean:.4f}, median={statistics.median(x_vals):.4f}, stdev={statistics.stdev(x_vals):.4f}, min={min(x_vals):.4f}, max={max(x_vals):.4f}")
    print(f"  TST:      mean={t_mean:.4f}, median={statistics.median(t_vals):.4f}, stdev={statistics.stdev(t_vals):.4f}, min={min(t_vals):.4f}, max={max(t_vals):.4f}")
    
    if b_mean > 0:
        xo = (x_mean / b_mean - 1) * 100
        to = (t_mean / b_mean - 1) * 100
        print(f"  XGB vs Baseline: {xo:+.2f}%")
        print(f"  TST vs Baseline: {to:+.2f}%")
        overhead_summary[field] = {"xgb_pct": xo, "tst_pct": to}

# 5. Per-suite table
print("\n\n" + "="*80)
print("PER-SUITE DETAIL TABLE (all 72)")
print("="*80)

sorted_ids = sorted(b_map.keys())
# pick the most important fields for display
key_fields = [f for f in numeric_fields if any(k in f for k in ["handshake", "throughput", "cpu", "mem", "rss", "latency", "duration"])]
if not key_fields:
    key_fields = numeric_fields[:6]

header = f"{'Suite':<55}"
for f in key_fields:
    header += f" {'B-'+f[:8]:>10} {'X-'+f[:8]:>10} {'T-'+f[:8]:>10}"
print(header)
print("-" * len(header))

for sid in sorted_ids:
    b = b_map[sid]
    x = x_map[sid]
    t = t_map[sid]
    row = f"{sid:<55}"
    for f in key_fields:
        row += f" {b.get(f,0):>10.2f} {x.get(f,0):>10.2f} {t.get(f,0):>10.2f}"
    print(row)

# 6. comparison.json
print("\n\n" + "="*80)
print("COMPARISON.JSON SUMMARY")
print("="*80)
comp = json.load(open(f"{SRC}/comparison.json"))
print(json.dumps(comp["summary"], indent=2))

per_suite = comp["per_suite"]
print(f"\nPer-suite entries: {len(per_suite)}")
# Show 3 examples
for i, item in enumerate(per_suite[:3]):
    print(f"\n  Entry {i}:")
    print(f"  {json.dumps(item, indent=4)}")

# 7. Final overhead summary
print("\n\n" + "="*80)
print("OVERHEAD SUMMARY TABLE")
print("="*80)
print(f"{'Metric':<35} {'XGB vs Baseline':>18} {'TST vs Baseline':>18}")
print("-" * 75)
for field, vals in overhead_summary.items():
    print(f"{field:<35} {vals['xgb_pct']:>+17.2f}% {vals['tst_pct']:>+17.2f}%")
