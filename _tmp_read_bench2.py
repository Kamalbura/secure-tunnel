#!/usr/bin/env python3
"""Inspect bench_ddos_results – all three runs."""
import json, statistics

SRC = "bench_ddos_results/20260209_090851"

# 1. Show file structures
for fname in ["config", "baseline", "xgb", "tst", "comparison"]:
    d = json.load(open(f"{SRC}/{fname}.json"))
    print(f"\n{'='*70}")
    print(f"=== {fname}.json ===")
    if isinstance(d, dict):
        print(f"  top-level keys: {list(d.keys())}")
        for k, v in d.items():
            if k == "results" and isinstance(v, dict):
                print(f"  results: {len(v)} suites")
                fk = list(v.keys())[0]
                print(f"  first suite key: {fk}")
                print(f"  first suite fields: {list(v[fk].keys())}")
                print(f"  first suite data:\n{json.dumps(v[fk], indent=2)}")
            elif k == "per_suite" and isinstance(v, dict):
                print(f"  per_suite: {len(v)} entries")
                fk = list(v.keys())[0]
                print(f"  first entry: {fk}")
                print(f"  first entry data:\n{json.dumps(v[fk], indent=2)}")
            elif k == "summary" and isinstance(v, dict):
                print(f"  summary:\n{json.dumps(v, indent=2)}")
            elif k == "suite_list" and isinstance(v, list):
                print(f"  suite_list: {len(v)} items, first 3: {v[:3]}")
            elif isinstance(v, (str, int, float, bool)):
                print(f"  {k}: {v}")
            elif isinstance(v, dict):
                print(f"  {k}: dict with {len(v)} keys")
            elif isinstance(v, list):
                print(f"  {k}: list with {len(v)} items")

# 2. Detailed cross-run comparison
print("\n\n" + "="*80)
print("DETAILED CROSS-RUN METRIC COMPARISON")
print("="*80)

baseline = json.load(open(f"{SRC}/baseline.json"))["results"]
xgb_data = json.load(open(f"{SRC}/xgb.json"))["results"]
tst_data = json.load(open(f"{SRC}/tst.json"))["results"]

# Discover all metric fields from first suite
first_b = list(baseline.values())[0]
metric_fields = [k for k in first_b.keys() if isinstance(first_b[k], (int, float))]
print(f"\nNumeric metric fields: {metric_fields}")

# Collect per-metric stats
for field in metric_fields:
    b_vals = [baseline[s].get(field, 0) for s in baseline if isinstance(baseline[s].get(field, 0), (int, float))]
    x_vals = [xgb_data[s].get(field, 0) for s in xgb_data if isinstance(xgb_data[s].get(field, 0), (int, float))]
    t_vals = [tst_data[s].get(field, 0) for s in tst_data if isinstance(tst_data[s].get(field, 0), (int, float))]
    
    if not b_vals:
        continue
    
    b_mean = statistics.mean(b_vals)
    x_mean = statistics.mean(x_vals) if x_vals else 0
    t_mean = statistics.mean(t_vals) if t_vals else 0
    
    print(f"\n--- {field} ---")
    print(f"  Baseline: mean={b_mean:.4f}, median={statistics.median(b_vals):.4f}, min={min(b_vals):.4f}, max={max(b_vals):.4f}")
    print(f"  XGBoost:  mean={x_mean:.4f}, median={statistics.median(x_vals):.4f}, min={min(x_vals):.4f}, max={max(x_vals):.4f}")
    print(f"  TST:      mean={t_mean:.4f}, median={statistics.median(t_vals):.4f}, min={min(t_vals):.4f}, max={max(t_vals):.4f}")
    if b_mean > 0:
        print(f"  XGB overhead: {(x_mean/b_mean - 1)*100:+.2f}%")
        print(f"  TST overhead: {(t_mean/b_mean - 1)*100:+.2f}%")

# 3. Per-suite table (first 10 + last 5)
print("\n\n" + "="*80)
print("PER-SUITE COMPARISON (sample)")
print("="*80)

sorted_suites = sorted(baseline.keys())
sample = sorted_suites[:5] + sorted_suites[-5:]

for sid in sample:
    b = baseline.get(sid, {})
    x = xgb_data.get(sid, {})
    t = tst_data.get(sid, {})
    print(f"\n  {sid}:")
    for field in metric_fields:
        bv = b.get(field, "N/A")
        xv = x.get(field, "N/A")
        tv = t.get(field, "N/A")
        if isinstance(bv, float):
            print(f"    {field:<30} B={bv:>12.4f}  X={xv:>12.4f}  T={tv:>12.4f}")
        else:
            print(f"    {field:<30} B={bv}  X={xv}  T={tv}")

# 4. Print comparison.json summary
print("\n\n" + "="*80)
print("PRE-COMPUTED COMPARISON SUMMARY (comparison.json)")
print("="*80)
comp = json.load(open(f"{SRC}/comparison.json"))
print(json.dumps(comp.get("summary", {}), indent=2))

# Show 3 per_suite examples
if "per_suite" in comp:
    ps = comp["per_suite"]
    print(f"\nPer-suite comparison entries: {len(ps)}")
    for i, (k, v) in enumerate(ps.items()):
        if i >= 3:
            break
        print(f"\n  {k}:")
        print(f"  {json.dumps(v, indent=4)}")
