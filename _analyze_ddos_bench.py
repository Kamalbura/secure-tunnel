#!/usr/bin/env python3
"""Quick analysis of bench_ddos_overhead results."""
import json, pathlib, statistics

RESULTS = pathlib.Path("bench_ddos_results/20260209_090851")
comp = json.loads((RESULTS / "comparison.json").read_text())
base = json.loads((RESULTS / "baseline.json").read_text())
xgb  = json.loads((RESULTS / "xgb.json").read_text())
tst  = json.loads((RESULTS / "tst.json").read_text())

# Build iteration map
base_iters = {s["suite_id"]: s["iterations"] for s in base["results"]}
xgb_iters  = {s["suite_id"]: s["iterations"] for s in xgb["results"]}
tst_iters  = {s["suite_id"]: s["iterations"] for s in tst["results"]}

print("=" * 100)
print("PER-SUITE RESULTS  (sorted by baseline latency)")
print("=" * 100)
print(f"{'Suite':<58} {'Base ms':>9} {'#B':>4} {'XGB ms':>9} {'#X':>4} {'TST ms':>9} {'#T':>4} {'XGB%':>7} {'TST%':>7}")
print("-" * 100)

suites = sorted(comp["per_suite"], key=lambda s: s["baseline_mean_ms"])
for s in suites:
    sid = s["suite_id"]
    bi = base_iters.get(sid, 0)
    xi = xgb_iters.get(sid, 0)
    ti = tst_iters.get(sid, 0)
    xp = s.get("xgb_overhead_pct")
    tp = s.get("tst_overhead_pct")
    xpstr = f"{xp:+.2f}%" if xp is not None else "N/A"
    tpstr = f"{tp:+.2f}%" if tp is not None else "N/A"
    print(f"{sid:<58} {s['baseline_mean_ms']:9.1f} {bi:4d} {s.get('xgb_mean_ms',0):9.1f} {xi:4d} {s.get('tst_mean_ms',0):9.1f} {ti:4d} {xpstr:>7} {tpstr:>7}")

print()
print("=" * 100)
print("AGGREGATE SUMMARY")
print("=" * 100)

# Split by reliability: >=5 iterations in all 3 phases
reliable = []
unreliable = []
for s in comp["per_suite"]:
    sid = s["suite_id"]
    if base_iters.get(sid,0) >= 5 and xgb_iters.get(sid,0) >= 5 and tst_iters.get(sid,0) >= 5:
        reliable.append(s)
    else:
        unreliable.append(s)

print(f"\nReliable suites (>=5 iters in all phases): {len(reliable)}")
print(f"Unreliable suites (<5 iters in some phase): {len(unreliable)}")

if reliable:
    xgb_pcts = [s["xgb_overhead_pct"] for s in reliable if s.get("xgb_overhead_pct") is not None]
    tst_pcts = [s["tst_overhead_pct"] for s in reliable if s.get("tst_overhead_pct") is not None]
    
    print(f"\n--- RELIABLE SUITES ONLY ---")
    print(f"  XGBoost overhead: mean={statistics.mean(xgb_pcts):+.2f}%  median={statistics.median(xgb_pcts):+.2f}%  "
          f"stdev={statistics.stdev(xgb_pcts):.2f}%  min={min(xgb_pcts):+.2f}%  max={max(xgb_pcts):+.2f}%")
    print(f"  TST     overhead: mean={statistics.mean(tst_pcts):+.2f}%  median={statistics.median(tst_pcts):+.2f}%  "
          f"stdev={statistics.stdev(tst_pcts):.2f}%  min={min(tst_pcts):+.2f}%  max={max(tst_pcts):+.2f}%")

# Group by KEM family
from collections import defaultdict
by_kem = defaultdict(list)
by_sig = defaultdict(list)
for s in comp["per_suite"]:
    sid = s["suite_id"].replace("cs-", "")
    parts = sid.split("-")
    kem = parts[0]
    # find sig (last part)
    for known_sig in ["falcon512", "falcon1024", "mldsa44", "mldsa65", "mldsa87", "sphincs128s", "sphincs192s", "sphincs256s"]:
        if sid.endswith(known_sig):
            sig = known_sig
            break
    else:
        sig = "unknown"
    by_kem[kem].append(s)
    by_sig[sig].append(s)

print(f"\n--- BY KEM FAMILY ---")
for kem in sorted(by_kem.keys()):
    entries = by_kem[kem]
    xpcts = [e["xgb_overhead_pct"] for e in entries if e.get("xgb_overhead_pct") is not None]
    tpcts = [e["tst_overhead_pct"] for e in entries if e.get("tst_overhead_pct") is not None]
    print(f"  {kem:<25} ({len(entries):2d} suites)  XGB: {statistics.mean(xpcts):+6.2f}%  TST: {statistics.mean(tpcts):+6.2f}%")

print(f"\n--- BY SIGNATURE FAMILY ---")
for sig in sorted(by_sig.keys()):
    entries = by_sig[sig]
    xpcts = [e["xgb_overhead_pct"] for e in entries if e.get("xgb_overhead_pct") is not None]
    tpcts = [e["tst_overhead_pct"] for e in entries if e.get("tst_overhead_pct") is not None]
    print(f"  {sig:<25} ({len(entries):2d} suites)  XGB: {statistics.mean(xpcts):+6.2f}%  TST: {statistics.mean(tpcts):+6.2f}%")

# Overall (all 72)
all_xgb = [s["xgb_overhead_pct"] for s in comp["per_suite"] if s.get("xgb_overhead_pct") is not None]
all_tst = [s["tst_overhead_pct"] for s in comp["per_suite"] if s.get("tst_overhead_pct") is not None]
print(f"\n--- ALL 72 SUITES ---")
print(f"  XGBoost: mean={statistics.mean(all_xgb):+.2f}%  median={statistics.median(all_xgb):+.2f}%  stdev={statistics.stdev(all_xgb):.2f}%")
print(f"  TST    : mean={statistics.mean(all_tst):+.2f}%  median={statistics.median(all_tst):+.2f}%  stdev={statistics.stdev(all_tst):.2f}%")
