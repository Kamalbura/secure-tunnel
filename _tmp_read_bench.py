#!/usr/bin/env python3
"""Quick script to inspect bench_ddos_results."""
import json, statistics

SRC = "bench_ddos_results/20260209_090851"

# 1. Read all files
for fname in ["config", "baseline", "xgb", "tst", "comparison"]:
    path = f"{SRC}/{fname}.json"
    d = json.load(open(path))
    if isinstance(d, dict):
        print(f"\n{'='*60}")
        print(f"=== {fname}.json === top-level keys: {list(d.keys())}")
        if "meta" in d:
            print(f"  meta: {json.dumps(d['meta'], indent=2)}")
        if "suites" in d and isinstance(d["suites"], dict):
            suites = d["suites"]
            print(f"  suites count: {len(suites)}")
            # Show first suite in detail
            first_key = list(suites.keys())[0]
            first_val = suites[first_key]
            print(f"  first suite: {first_key}")
            print(f"  first suite keys: {list(first_val.keys())}")
            print(f"  first suite detail: {json.dumps(first_val, indent=2)}")
        elif "suites" in d:
            print(f"  suites (scalar): {d['suites']}")
    else:
        print(f"\n=== {fname}.json === type={type(d).__name__}, len={len(d)}")

# 2. Compare key metrics across 3 runs
print("\n" + "="*80)
print("CROSS-RUN COMPARISON: Key Metrics per Suite")
print("="*80)

baseline = json.load(open(f"{SRC}/baseline.json"))["suites"]
xgb = json.load(open(f"{SRC}/xgb.json"))["suites"]
tst = json.load(open(f"{SRC}/tst.json"))["suites"]

all_hs_baseline = []
all_hs_xgb = []
all_hs_tst = []
all_tp_baseline = []
all_tp_xgb = []
all_tp_tst = []
all_cpu_baseline = []
all_cpu_xgb = []
all_cpu_tst = []

print(f"\n{'Suite ID':<55} {'Baseline HS(ms)':>15} {'XGB HS(ms)':>12} {'TST HS(ms)':>12} {'B tp(KB/s)':>10} {'X tp(KB/s)':>10} {'T tp(KB/s)':>10}")
print("-"*130)

for sid in sorted(baseline.keys()):
    b = baseline[sid]
    x = xgb.get(sid, {})
    t = tst.get(sid, {})
    
    b_hs = b.get("handshake_ms", 0)
    x_hs = x.get("handshake_ms", 0)
    t_hs = t.get("handshake_ms", 0)
    
    b_tp = b.get("throughput_kbps", 0)
    x_tp = x.get("throughput_kbps", 0)
    t_tp = t.get("throughput_kbps", 0)
    
    b_cpu = b.get("cpu_percent", 0)
    x_cpu = x.get("cpu_percent", 0)
    t_cpu = t.get("cpu_percent", 0)
    
    all_hs_baseline.append(b_hs)
    all_hs_xgb.append(x_hs)
    all_hs_tst.append(t_hs)
    all_tp_baseline.append(b_tp)
    all_tp_xgb.append(x_tp)
    all_tp_tst.append(t_tp)
    all_cpu_baseline.append(b_cpu)
    all_cpu_xgb.append(x_cpu)
    all_cpu_tst.append(t_cpu)
    
    print(f"{sid:<55} {b_hs:>15.2f} {x_hs:>12.2f} {t_hs:>12.2f} {b_tp:>10.2f} {x_tp:>10.2f} {t_tp:>10.2f}")

# 3. Summary statistics
print("\n" + "="*80)
print("SUMMARY STATISTICS")
print("="*80)

def stats(name, vals):
    if not vals or all(v == 0 for v in vals):
        return f"  {name}: all zero or empty"
    return f"  {name}: mean={statistics.mean(vals):.2f}, median={statistics.median(vals):.2f}, min={min(vals):.2f}, max={max(vals):.2f}, stdev={statistics.stdev(vals):.2f}"

print("\nHandshake Duration (ms):")
print(stats("Baseline", all_hs_baseline))
print(stats("XGBoost ", all_hs_xgb))
print(stats("TST     ", all_hs_tst))

print("\nThroughput (KB/s):")
print(stats("Baseline", all_tp_baseline))
print(stats("XGBoost ", all_tp_xgb))
print(stats("TST     ", all_tp_tst))

print("\nCPU Usage (%):")
print(stats("Baseline", all_cpu_baseline))
print(stats("XGBoost ", all_cpu_xgb))
print(stats("TST     ", all_cpu_tst))

# 4. Overhead calculations
print("\n" + "="*80)
print("OVERHEAD ANALYSIS (vs Baseline)")
print("="*80)

if all_hs_baseline and statistics.mean(all_hs_baseline) > 0:
    b_mean = statistics.mean(all_hs_baseline)
    x_mean = statistics.mean(all_hs_xgb)
    t_mean = statistics.mean(all_hs_tst)
    print(f"\nHandshake overhead:")
    print(f"  XGBoost vs Baseline: {x_mean - b_mean:+.2f} ms ({(x_mean/b_mean - 1)*100:+.1f}%)")
    print(f"  TST vs Baseline:     {t_mean - b_mean:+.2f} ms ({(t_mean/b_mean - 1)*100:+.1f}%)")

if all_tp_baseline and statistics.mean(all_tp_baseline) > 0:
    b_mean = statistics.mean(all_tp_baseline)
    x_mean = statistics.mean(all_tp_xgb)
    t_mean = statistics.mean(all_tp_tst)
    print(f"\nThroughput overhead:")
    print(f"  XGBoost vs Baseline: {x_mean - b_mean:+.2f} KB/s ({(x_mean/b_mean - 1)*100:+.1f}%)")
    print(f"  TST vs Baseline:     {t_mean - b_mean:+.2f} KB/s ({(t_mean/b_mean - 1)*100:+.1f}%)")

if all_cpu_baseline and statistics.mean(all_cpu_baseline) > 0:
    b_mean = statistics.mean(all_cpu_baseline)
    x_mean = statistics.mean(all_cpu_xgb)
    t_mean = statistics.mean(all_cpu_tst)
    print(f"\nCPU overhead:")
    print(f"  XGBoost vs Baseline: {x_mean - b_mean:+.2f}% ({(x_mean/b_mean - 1)*100:+.1f}%)")
    print(f"  TST vs Baseline:     {t_mean - b_mean:+.2f}% ({(t_mean/b_mean - 1)*100:+.1f}%)")

# 5. Read comparison.json
print("\n" + "="*80)
print("COMPARISON.JSON (pre-computed analysis)")
print("="*80)
comp = json.load(open(f"{SRC}/comparison.json"))
print(json.dumps(comp, indent=2)[:3000])
