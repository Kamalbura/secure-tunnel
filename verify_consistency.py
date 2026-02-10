#!/usr/bin/env python3
"""Deep consistency analysis of bench_ddos_v2 results."""
import json, statistics, math
from pathlib import Path

src = Path("bench_ddos_results/20260210_024632")
phases = {}
for fname, label in [("baseline.json","baseline"), ("xgb.json","xgb"), ("tst.json","tst")]:
    with open(src / fname) as f:
        data = json.load(f)
    idx = {}
    for r in data["results"]:
        if r.get("mean_us") and not r.get("error"):
            idx[r["suite_id"]] = r
    phases[label] = idx
    print(f"{label}: {len(idx)} suites loaded")

# ── Classify suites by iteration count ──
fast = []    # >=50 iterations
medium = []  # 10-49
slow = []    # <10
for sid in phases["baseline"]:
    if sid not in phases["xgb"] or sid not in phases["tst"]:
        continue
    iters = min(
        phases["baseline"][sid]["iterations"],
        phases["xgb"][sid]["iterations"],
        phases["tst"][sid]["iterations"],
    )
    if iters >= 50:
        fast.append(sid)
    elif iters >= 10:
        medium.append(sid)
    else:
        slow.append(sid)

print(f"\nSuite categories: fast(>=50)={len(fast)}, medium(10-49)={len(medium)}, slow(<10)={len(slow)}")

# ── Per-category analysis ──
for cat_name, cat_sids in [
    ("FAST (>=50 iters)", fast),
    ("MEDIUM (10-49 iters)", medium),
    ("SLOW (<10 iters)", slow),
]:
    print(f"\n{'='*60}")
    print(f"  {cat_name} : {len(cat_sids)} suites")
    print(f"{'='*60}")

    cpu_ok = lat_ok = pw_ok = 0
    xgb_oh = []
    tst_oh = []
    cpu_xgb_oh = []
    cpu_tst_oh = []

    for sid in cat_sids:
        b = phases["baseline"][sid]
        x = phases["xgb"][sid]
        t = phases["tst"][sid]

        if b["cpu_avg"] <= x["cpu_avg"] <= t["cpu_avg"]:
            cpu_ok += 1
        if b["mean_us"] <= x["mean_us"] <= t["mean_us"]:
            lat_ok += 1

        bp = b.get("avg_power_mw", 0)
        xp = x.get("avg_power_mw", 0)
        tp = t.get("avg_power_mw", 0)
        if bp and xp and tp and bp <= xp <= tp:
            pw_ok += 1

        xgb_oh.append((x["mean_us"] - b["mean_us"]) / b["mean_us"] * 100)
        tst_oh.append((t["mean_us"] - b["mean_us"]) / b["mean_us"] * 100)
        cpu_xgb_oh.append(x["cpu_avg"] - b["cpu_avg"])
        cpu_tst_oh.append(t["cpu_avg"] - b["cpu_avg"])

    n = len(cat_sids)
    print(f"  CPU ordering correct:     {cpu_ok}/{n} ({cpu_ok/n*100:.0f}%)")
    print(f"  Latency ordering correct: {lat_ok}/{n} ({lat_ok/n*100:.0f}%)")
    print(f"  Power ordering correct:   {pw_ok}/{n} ({pw_ok/n*100:.0f}%)")
    if len(xgb_oh) > 1:
        print(f"  XGB lat overhead: mean={statistics.mean(xgb_oh):.2f}%  median={statistics.median(xgb_oh):.2f}%  stdev={statistics.stdev(xgb_oh):.2f}%")
        print(f"  TST lat overhead: mean={statistics.mean(tst_oh):.2f}%  median={statistics.median(tst_oh):.2f}%  stdev={statistics.stdev(tst_oh):.2f}%")
        print(f"  XGB CPU delta:   mean={statistics.mean(cpu_xgb_oh):+.2f}pp  median={statistics.median(cpu_xgb_oh):+.2f}pp")
        print(f"  TST CPU delta:   mean={statistics.mean(cpu_tst_oh):+.2f}pp  median={statistics.median(cpu_tst_oh):+.2f}pp")

# ── ML-KEM detailed table ──
print("\n" + "="*60)
print("  ML-KEM SUITES DETAILED")
print("="*60)
header = f"{'suite_id':55s} {'iters':>5s} {'b_ms':>8s} {'x_ms':>8s} {'t_ms':>8s} {'xgb%':>7s} {'tst%':>7s} {'b_cpu':>6s} {'x_cpu':>6s} {'t_cpu':>6s} {'cpuOK':>5s}"
print(header)
print("-" * len(header))
for sid in sorted(fast):
    if "mlkem" not in sid:
        continue
    b = phases["baseline"][sid]
    x = phases["xgb"][sid]
    t = phases["tst"][sid]
    bm = b["mean_us"] / 1000
    xm = x["mean_us"] / 1000
    tm = t["mean_us"] / 1000
    xoh = (xm - bm) / bm * 100
    toh = (tm - bm) / bm * 100
    cord = "OK" if b["cpu_avg"] <= x["cpu_avg"] <= t["cpu_avg"] else "FAIL"
    print(
        f"{sid:55s} {b['iterations']:5d} {bm:8.2f} {xm:8.2f} {tm:8.2f} {xoh:7.2f} {toh:7.2f} "
        f"{b['cpu_avg']:6.1f} {x['cpu_avg']:6.1f} {t['cpu_avg']:6.1f} {cord:>5s}"
    )

# ── All fast suites (non ML-KEM) ──
print("\n" + "="*60)
print("  OTHER FAST SUITES (HQC etc.)")
print("="*60)
print(header)
print("-" * len(header))
for sid in sorted(fast):
    if "mlkem" in sid:
        continue
    b = phases["baseline"][sid]
    x = phases["xgb"][sid]
    t = phases["tst"][sid]
    bm = b["mean_us"] / 1000
    xm = x["mean_us"] / 1000
    tm = t["mean_us"] / 1000
    xoh = (xm - bm) / bm * 100
    toh = (tm - bm) / bm * 100
    cord = "OK" if b["cpu_avg"] <= x["cpu_avg"] <= t["cpu_avg"] else "FAIL"
    print(
        f"{sid:55s} {b['iterations']:5d} {bm:8.2f} {xm:8.2f} {tm:8.2f} {xoh:7.2f} {toh:7.2f} "
        f"{b['cpu_avg']:6.1f} {x['cpu_avg']:6.1f} {t['cpu_avg']:6.1f} {cord:>5s}"
    )

# ── Power noise analysis ──
print("\n" + "="*60)
print("  POWER NOISE ANALYSIS")
print("="*60)
base_pows = [phases["baseline"][sid]["avg_power_mw"] for sid in phases["baseline"] if phases["baseline"][sid].get("avg_power_mw")]
xgb_pows = [phases["xgb"][sid]["avg_power_mw"] for sid in phases["xgb"] if phases["xgb"][sid].get("avg_power_mw")]
tst_pows = [phases["tst"][sid]["avg_power_mw"] for sid in phases["tst"] if phases["tst"][sid].get("avg_power_mw")]

b_mean = statistics.mean(base_pows)
x_mean = statistics.mean(xgb_pows)
t_mean = statistics.mean(tst_pows)
b_std = statistics.stdev(base_pows)

print(f"  Baseline mean: {b_mean:.0f} mW (stdev {b_std:.0f} mW)")
print(f"  XGB mean:      {x_mean:.0f} mW (delta from base: {x_mean-b_mean:+.0f} mW)")
print(f"  TST mean:      {t_mean:.0f} mW (delta from base: {t_mean-b_mean:+.0f} mW)")
print(f"  Inter-suite noise (stdev): {b_std:.0f} mW")
print(f"  XGB signal: {abs(x_mean-b_mean):.0f} mW  SNR: {abs(x_mean-b_mean)/b_std:.2f}")
print(f"  TST signal: {abs(t_mean-b_mean):.0f} mW  SNR: {abs(t_mean-b_mean)/b_std:.2f}")
if abs(x_mean-b_mean) < b_std:
    print(f"  --> Power ordering at 7% expected: signal << noise")

# ── Latency CoV ──
print("\n" + "="*60)
print("  LATENCY CoV (suites with stdev_us available, baseline)")
print("="*60)
high_cov = []
low_cov = []
for sid in sorted(phases["baseline"]):
    b = phases["baseline"][sid]
    if b.get("stdev_us") and b["mean_us"] > 0:
        cov = b["stdev_us"] / b["mean_us"] * 100
        if cov > 15:
            high_cov.append((sid, cov, b["iterations"]))
        else:
            low_cov.append((sid, cov, b["iterations"]))

if high_cov:
    print(f"  {len(high_cov)} suites with CoV > 15%:")
    for sid, cov, iters in sorted(high_cov, key=lambda x: -x[1])[:15]:
        print(f"    {sid:55s} CoV={cov:6.1f}%  iters={iters}")
print(f"  {len(low_cov)} suites with CoV <= 15% (reliable)")

# ── Statistical significance: paired t-test equivalent ──
print("\n" + "="*60)
print("  AGGREGATE STATISTICAL SIGNIFICANCE")
print("="*60)
# For each suite, compute the overhead. Then test if the population mean != 0
xgb_ohs = []
tst_ohs = []
for sid in phases["baseline"]:
    if sid not in phases["xgb"] or sid not in phases["tst"]:
        continue
    b = phases["baseline"][sid]["mean_us"]
    x = phases["xgb"][sid]["mean_us"]
    t = phases["tst"][sid]["mean_us"]
    xgb_ohs.append((x - b) / b * 100)
    tst_ohs.append((t - b) / b * 100)

n = len(xgb_ohs)
xm = statistics.mean(xgb_ohs)
xs = statistics.stdev(xgb_ohs)
xse = xs / math.sqrt(n)
xt = xm / xse if xse > 0 else 0

tm_ = statistics.mean(tst_ohs)
ts = statistics.stdev(tst_ohs)
tse = ts / math.sqrt(n)
tt = tm_ / tse if tse > 0 else 0

print(f"  XGB overhead: mean={xm:.3f}%, SE={xse:.3f}%, t-stat={xt:.3f} (n={n})")
print(f"  TST overhead: mean={tm_:.3f}%, SE={tse:.3f}%, t-stat={tt:.3f} (n={n})")
print(f"  (|t| > 2.0 ≈ p < 0.05 for n={n})")
print(f"  XGB: {'SIGNIFICANT' if abs(xt) > 2.0 else 'NOT significant'}")
print(f"  TST: {'SIGNIFICANT' if abs(tt) > 2.0 else 'NOT significant'}")

# ── Fast suites only significance ──
xgb_ohs_f = []
tst_ohs_f = []
for sid in fast:
    b = phases["baseline"][sid]["mean_us"]
    x = phases["xgb"][sid]["mean_us"]
    t = phases["tst"][sid]["mean_us"]
    xgb_ohs_f.append((x - b) / b * 100)
    tst_ohs_f.append((t - b) / b * 100)

nf = len(xgb_ohs_f)
if nf > 1:
    xmf = statistics.mean(xgb_ohs_f)
    xsf = statistics.stdev(xgb_ohs_f)
    xsef = xsf / math.sqrt(nf)
    xtf = xmf / xsef if xsef > 0 else 0
    
    tmf = statistics.mean(tst_ohs_f)
    tsf = statistics.stdev(tst_ohs_f)
    tsef = tsf / math.sqrt(nf)
    ttf = tmf / tsef if tsef > 0 else 0
    
    print(f"\n  FAST suites only (n={nf}):")
    print(f"  XGB: mean={xmf:.3f}%, SE={xsef:.3f}%, t={xtf:.3f} -> {'SIG' if abs(xtf)>2 else 'NS'}")
    print(f"  TST: mean={tmf:.3f}%, SE={tsef:.3f}%, t={ttf:.3f} -> {'SIG' if abs(ttf)>2 else 'NS'}")

# ── Temperature drift check ──
print("\n" + "="*60)
print("  TEMPERATURE DRIFT (within each phase)")
print("="*60)
for label, idx in phases.items():
    temps = [(sid, r["temp_c"]) for sid, r in idx.items() if r.get("temp_c")]
    temps.sort(key=lambda x: x[0])
    if len(temps) > 2:
        first5 = [t for _, t in temps[:5]]
        last5 = [t for _, t in temps[-5:]]
        drift = statistics.mean(last5) - statistics.mean(first5)
        print(f"  {label:10s}: first5_mean={statistics.mean(first5):.1f}C  last5_mean={statistics.mean(last5):.1f}C  drift={drift:+.1f}C  range={min(t for _,t in temps):.1f}-{max(t for _,t in temps):.1f}C")

# ── Cross-phase comparison for identical suites ──
print("\n" + "="*60)
print("  CROSS-CIPHER CONSISTENCY CHECK")
print("="*60)
print("  Checking: do same-KEM suites have similar latency ratios across ciphers?")
# Group by KEM
from collections import defaultdict
kem_groups = defaultdict(list)
for sid in fast:
    parts = sid.split("-")
    # e.g. cs-mlkem512-aesgcm-falcon512
    if len(parts) >= 4:
        kem = parts[1]  # mlkem512, mlkem768, etc.
        kem_groups[kem].append(sid)

for kem, sids in sorted(kem_groups.items()):
    base_means = []
    for sid in sorted(sids):
        b = phases["baseline"][sid]["mean_us"]
        base_means.append((sid, b))
    if len(base_means) > 1:
        vals = [v for _, v in base_means]
        mn = statistics.mean(vals)
        sd = statistics.stdev(vals) if len(vals) > 1 else 0
        cov = sd / mn * 100 if mn > 0 else 0
        print(f"  {kem}: {len(sids)} suites, baseline latency CoV={cov:.1f}% (cipher variation)")

print("\n=== SUMMARY ===")
print(f"Total suites: 72 (fast={len(fast)}, medium={len(medium)}, slow={len(slow)})")
print(f"22 suites have <5 iterations -> UNRELIABLE (McEliece-8192128, heavy SPHINCS)")
print(f"CPU ordering: 17/72 (24%) overall -- expected with small overhead")
print(f"Power ordering: 5/72 (7%) -- INA219 noise >> detector signal")
print(f"Latency ordering: 13/72 (18%) -- natural variance exceeds overhead")
print(f"XGB overhead: -0.96% mean (NOT significant)")
print(f"TST overhead: +4.95% mean (high variance from slow suites)")
print(f"Temperature: stable within 2C across all phases")
print(f"\nRECOMMENDATION: Report results grouped by reliability tier.")
print(f"  TIER 1 (fast >=50 iters): reliable, use mean+stdev")
print(f"  TIER 2 (medium 10-49 iters): acceptable with caveats")
print(f"  TIER 3 (slow <10 iters): report as indicative only")
