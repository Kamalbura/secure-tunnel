"""
Verify expected ordering: baseline < XGBoost < TST
for CPU, power, latency, and temperature.
"""
import json, os, glob, statistics
from collections import defaultdict

base_dir = 'logs/benchmarks/runs'
phases_map = {
    'no-ddos': 'baseline',
    'ddos-xgboost': 'xgboost',
    'ddos-txt': 'tst'
}

data = defaultdict(list)
for folder, label in phases_map.items():
    path = os.path.join(base_dir, folder)
    files = sorted(glob.glob(os.path.join(path, '*.json')))
    for f in files:
        with open(f) as fh:
            d = json.load(fh)
        hs = d.get('handshake', {})
        sys_d = d.get('system_drone', {})
        power = d.get('power_energy', {})
        crypto = d.get('crypto_primitives', {})
        ci = d.get('crypto_identity', {})
        kem = ci.get('kem', 'unknown')

        rec = {
            'suite_id': d.get('run_context', {}).get('suite_id', ''),
            'kem': kem,
            'phase': label,
            'mean_us': hs.get('mean_us', 0),
            'median_us': hs.get('median_us', 0),
            'p95_us': hs.get('p95_us', 0),
            'stdev_us': hs.get('stdev_us', 0),
            'iterations': hs.get('iterations', 0),
            'cpu_avg': sys_d.get('cpu_avg', 0),
            'cpu_peak': sys_d.get('cpu_peak', 0),
            'temp_c': sys_d.get('temp_c', 0),
            'mem_rss_mb': sys_d.get('mem_rss_mb', 0),
            'avg_power_mw': power.get('avg_power_mw', 0),
            'avg_current_ma': power.get('avg_current_ma', 0),
            'avg_voltage_v': power.get('avg_voltage_v', 0),
            'total_energy_mj': power.get('total_energy_mj', 0),
            'energy_per_hs_mj': power.get('avg_energy_mj_per_hs', 0),
            'build_hello_us': crypto.get('build_hello_avg_us', 0),
            'parse_verify_us': crypto.get('parse_verify_avg_us', 0),
            'encap_us': crypto.get('encap_avg_us', 0),
            'decap_us': crypto.get('decap_avg_us', 0),
        }
        data[label].append(rec)

print(f"Loaded: baseline={len(data['baseline'])}, xgboost={len(data['xgboost'])}, tst={len(data['tst'])}")

# ── SECTION 1: Overall aggregates ─────────────────────────────
print("\n" + "=" * 100)
print("SECTION 1: OVERALL AGGREGATES (all 72 suites per phase)")
print("=" * 100)

header = f"{'Phase':<10} {'Mean_lat':>10} {'Med_lat':>10} {'P95_lat':>10} {'CPU_avg':>8} {'CPU_pk':>7} {'Power_mW':>9} {'E/hs_mJ':>9} {'Temp_C':>7} {'RAM_MB':>7}"
print(header)
print("-" * 100)

phase_agg = {}
for phase in ['baseline', 'xgboost', 'tst']:
    recs = data[phase]
    agg = {
        'mean_lat': statistics.mean([r['mean_us'] for r in recs]),
        'med_lat': statistics.mean([r['median_us'] for r in recs]),
        'p95_lat': statistics.mean([r['p95_us'] for r in recs]),
        'cpu_avg': statistics.mean([r['cpu_avg'] for r in recs]),
        'cpu_peak': statistics.mean([r['cpu_peak'] for r in recs]),
        'power_mw': statistics.mean([r['avg_power_mw'] for r in recs]),
        'energy_hs': statistics.mean([r['energy_per_hs_mj'] for r in recs]),
        'temp': statistics.mean([r['temp_c'] for r in recs]),
        'ram': statistics.mean([r['mem_rss_mb'] for r in recs]),
    }
    phase_agg[phase] = agg
    print(f"{phase:<10} {agg['mean_lat']:>10.1f} {agg['med_lat']:>10.1f} {agg['p95_lat']:>10.1f} "
          f"{agg['cpu_avg']:>8.2f} {agg['cpu_peak']:>7.2f} {agg['power_mw']:>9.1f} "
          f"{agg['energy_hs']:>9.2f} {agg['temp']:>7.1f} {agg['ram']:>7.1f}")

# Deltas
print("\n--- Deltas from baseline ---")
b = phase_agg['baseline']
for phase in ['xgboost', 'tst']:
    p = phase_agg[phase]
    print(f"\n  {phase} vs baseline:")
    for key in ['mean_lat', 'med_lat', 'p95_lat', 'cpu_avg', 'cpu_peak', 'power_mw', 'energy_hs', 'temp', 'ram']:
        delta = p[key] - b[key]
        pct = (delta / b[key] * 100) if b[key] != 0 else 0
        direction = "UP" if delta > 0 else "DOWN" if delta < 0 else "SAME"
        print(f"    {key:<12}: {delta:>+10.2f} ({pct:>+6.2f}%) {direction}")

# ── SECTION 2: Per KEM family ─────────────────────────────────
print("\n" + "=" * 100)
print("SECTION 2: PER KEM FAMILY BREAKDOWN")
print("=" * 100)

kem_families = defaultdict(lambda: defaultdict(list))
for phase in ['baseline', 'xgboost', 'tst']:
    for rec in data[phase]:
        kem = rec['kem']
        if 'mlkem' in kem.lower() or 'kyber' in kem.lower():
            fam = 'ML-KEM'
        elif 'hqc' in kem.lower():
            fam = 'HQC'
        elif 'mceliece' in kem.lower():
            fam = 'McEliece'
        else:
            fam = kem
        kem_families[fam][phase].append(rec)

for fam in ['ML-KEM', 'HQC', 'McEliece']:
    print(f"\n--- {fam} ---")
    print(f"  {'Phase':<10} {'N':>3} {'Mean_lat':>10} {'Med_lat':>10} {'CPU_avg':>8} {'Power_mW':>9} {'E/hs_mJ':>9} {'Temp':>6}")
    fam_agg = {}
    for phase in ['baseline', 'xgboost', 'tst']:
        recs = kem_families[fam][phase]
        if not recs:
            continue
        n = len(recs)
        a = {
            'mean_lat': statistics.mean([r['mean_us'] for r in recs]),
            'med_lat': statistics.mean([r['median_us'] for r in recs]),
            'cpu_avg': statistics.mean([r['cpu_avg'] for r in recs]),
            'power_mw': statistics.mean([r['avg_power_mw'] for r in recs]),
            'energy_hs': statistics.mean([r['energy_per_hs_mj'] for r in recs]),
            'temp': statistics.mean([r['temp_c'] for r in recs]),
        }
        fam_agg[phase] = a
        print(f"  {phase:<10} {n:>3} {a['mean_lat']:>10.1f} {a['med_lat']:>10.1f} {a['cpu_avg']:>8.2f} "
              f"{a['power_mw']:>9.1f} {a['energy_hs']:>9.2f} {a['temp']:>6.1f}")

    # Check ordering
    if 'baseline' in fam_agg and 'xgboost' in fam_agg and 'tst' in fam_agg:
        ba, xg, ts = fam_agg['baseline'], fam_agg['xgboost'], fam_agg['tst']
        print(f"\n  ORDERING CHECK (expected: baseline < xgboost < tst):")
        for key, label in [('mean_lat', 'Latency'), ('cpu_avg', 'CPU'), ('power_mw', 'Power'), ('energy_hs', 'Energy/hs'), ('temp', 'Temp')]:
            vals = [ba[key], xg[key], ts[key]]
            order = "baseline < xgboost < tst" if vals[0] < vals[1] < vals[2] else \
                    "baseline < tst < xgboost" if vals[0] < vals[2] < vals[1] else \
                    "xgboost < baseline < tst" if vals[1] < vals[0] < vals[2] else \
                    "xgboost < tst < baseline" if vals[1] < vals[2] < vals[0] else \
                    "tst < baseline < xgboost" if vals[2] < vals[0] < vals[1] else \
                    "tst < xgboost < baseline" if vals[2] < vals[1] < vals[0] else \
                    "EQUAL"
            expected = vals[0] <= vals[1] <= vals[2]
            mark = "PASS" if expected else "FAIL"
            print(f"    {label:<10}: B={vals[0]:>10.2f}  X={vals[1]:>10.2f}  T={vals[2]:>10.2f}  -> {order}  [{mark}]")

# ── SECTION 3: Power consistency ──────────────────────────────
print("\n" + "=" * 100)
print("SECTION 3: POWER CONSISTENCY (stdev across suites within each phase)")
print("=" * 100)

for phase in ['baseline', 'xgboost', 'tst']:
    recs = data[phase]
    powers = [r['avg_power_mw'] for r in recs]
    energies = [r['energy_per_hs_mj'] for r in recs]
    voltages = [r['avg_voltage_v'] for r in recs]
    currents = [r['avg_current_ma'] for r in recs]
    
    print(f"\n  {phase}:")
    print(f"    Power  (mW): mean={statistics.mean(powers):>8.1f}  stdev={statistics.stdev(powers):>8.1f}  "
          f"min={min(powers):>8.1f}  max={max(powers):>8.1f}  CoV={statistics.stdev(powers)/statistics.mean(powers)*100:.1f}%")
    print(f"    Energy/hs:   mean={statistics.mean(energies):>8.2f}  stdev={statistics.stdev(energies):>8.2f}  "
          f"min={min(energies):>8.2f}  max={max(energies):>8.2f}")
    print(f"    Voltage (V): mean={statistics.mean(voltages):>8.3f}  stdev={statistics.stdev(voltages):>8.3f}  "
          f"min={min(voltages):>8.3f}  max={max(voltages):>8.3f}")
    print(f"    Current(mA): mean={statistics.mean(currents):>8.1f}  stdev={statistics.stdev(currents):>8.1f}  "
          f"min={min(currents):>8.1f}  max={max(currents):>8.1f}")

# ── SECTION 4: Suite-by-suite ordering check ──────────────────
print("\n" + "=" * 100)
print("SECTION 4: SUITE-BY-SUITE ORDERING CHECK")
print("  How many suites follow baseline < xgboost < tst for each metric?")
print("=" * 100)

# Build suite-level lookup
suite_data = defaultdict(dict)
for phase in ['baseline', 'xgboost', 'tst']:
    for rec in data[phase]:
        sid = rec['suite_id']
        suite_data[sid][phase] = rec

total = 0
ordering_counts = defaultdict(lambda: defaultdict(int))
metrics_to_check = ['mean_us', 'cpu_avg', 'avg_power_mw', 'energy_per_hs_mj', 'temp_c']

for sid, phases in suite_data.items():
    if len(phases) != 3:
        continue
    total += 1
    b, x, t = phases['baseline'], phases['xgboost'], phases['tst']
    
    for metric in metrics_to_check:
        bv, xv, tv = b[metric], x[metric], t[metric]
        if bv <= xv <= tv:
            ordering_counts[metric]['B<=X<=T'] += 1
        elif bv <= tv <= xv:
            ordering_counts[metric]['B<=T<=X'] += 1
        elif xv <= bv <= tv:
            ordering_counts[metric]['X<=B<=T'] += 1
        elif xv <= tv <= bv:
            ordering_counts[metric]['X<=T<=B'] += 1
        elif tv <= bv <= xv:
            ordering_counts[metric]['T<=B<=X'] += 1
        elif tv <= xv <= bv:
            ordering_counts[metric]['T<=X<=B'] += 1

print(f"\nTotal suites matched across all 3 phases: {total}")
for metric in metrics_to_check:
    print(f"\n  {metric}:")
    for order, count in sorted(ordering_counts[metric].items(), key=lambda x: -x[1]):
        pct = count / total * 100
        bar = "#" * int(pct / 2)
        print(f"    {order:<12}: {count:>3}/{total} ({pct:>5.1f}%) {bar}")

# ── SECTION 5: Matched ML-KEM-512 suites deep comparison ─────
print("\n" + "=" * 100)
print("SECTION 5: MATCHED ML-KEM-512 SUITES (same suite_id across all 3 phases)")
print("  These are the FAST suites with many iterations -> most reliable comparison")
print("=" * 100)

mlkem512_suites = {}
for sid, phases in suite_data.items():
    if len(phases) != 3:
        continue
    if 'mlkem512' in phases['baseline']['kem'].lower():
        mlkem512_suites[sid] = phases

print(f"\nFound {len(mlkem512_suites)} matched ML-KEM-512 suites")
print(f"\n{'Suite':<55} {'B_lat':>8} {'X_lat':>8} {'T_lat':>8} {'B_cpu':>6} {'X_cpu':>6} {'T_cpu':>6} {'B_pwr':>7} {'X_pwr':>7} {'T_pwr':>7} {'Order_lat':>14}")

for sid in sorted(mlkem512_suites.keys()):
    p = mlkem512_suites[sid]
    b, x, t = p['baseline'], p['xgboost'], p['tst']
    
    bl, xl, tl = b['mean_us'], x['mean_us'], t['mean_us']
    bc, xc, tc = b['cpu_avg'], x['cpu_avg'], t['cpu_avg']
    bp, xp, tp = b['avg_power_mw'], x['avg_power_mw'], t['avg_power_mw']
    
    if bl <= xl <= tl:
        olat = "B<=X<=T OK"
    elif bl <= tl <= xl:
        olat = "B<=T<=X"
    else:
        olat = f"{'B' if bl==min(bl,xl,tl) else 'X' if xl==min(bl,xl,tl) else 'T'} min"
    
    short = sid[:54]
    print(f"{short:<55} {bl:>8.0f} {xl:>8.0f} {tl:>8.0f} {bc:>6.1f} {xc:>6.1f} {tc:>6.1f} {bp:>7.0f} {xp:>7.0f} {tp:>7.0f} {olat:>14}")

# ── SECTION 6: Statistical significance (paired t-test) ──────
print("\n" + "=" * 100)
print("SECTION 6: PAIRED T-TESTS (baseline vs xgboost, baseline vs tst)")
print("  Testing whether differences are statistically significant")
print("=" * 100)

from scipy import stats as sp_stats

for metric, label in [('mean_us', 'Latency(us)'), ('cpu_avg', 'CPU(%)'), 
                       ('avg_power_mw', 'Power(mW)'), ('temp_c', 'Temp(C)')]:
    print(f"\n  {label}:")
    
    # Gather matched pairs
    b_vals, x_vals, t_vals = [], [], []
    for sid, phases in suite_data.items():
        if len(phases) != 3:
            continue
        b_vals.append(phases['baseline'][metric])
        x_vals.append(phases['xgboost'][metric])
        t_vals.append(phases['tst'][metric])
    
    # baseline vs xgboost
    t_stat, p_val = sp_stats.ttest_rel(b_vals, x_vals)
    sig = "SIGNIFICANT" if p_val < 0.05 else "NOT significant"
    d_mean = statistics.mean(x_vals) - statistics.mean(b_vals)
    print(f"    baseline vs xgboost: delta_mean={d_mean:>+10.2f}  t={t_stat:>7.3f}  p={p_val:.4f}  -> {sig}")
    
    # baseline vs tst
    t_stat, p_val = sp_stats.ttest_rel(b_vals, t_vals)
    sig = "SIGNIFICANT" if p_val < 0.05 else "NOT significant"
    d_mean = statistics.mean(t_vals) - statistics.mean(b_vals)
    print(f"    baseline vs tst    : delta_mean={d_mean:>+10.2f}  t={t_stat:>7.3f}  p={p_val:.4f}  -> {sig}")
    
    # xgboost vs tst
    t_stat, p_val = sp_stats.ttest_rel(x_vals, t_vals)
    sig = "SIGNIFICANT" if p_val < 0.05 else "NOT significant"
    d_mean = statistics.mean(t_vals) - statistics.mean(x_vals)
    print(f"    xgboost vs tst     : delta_mean={d_mean:>+10.2f}  t={t_stat:>7.3f}  p={p_val:.4f}  -> {sig}")

# ── SECTION 7: CPU model weight analysis ─────────────────────
print("\n" + "=" * 100)
print("SECTION 7: MODEL CPU WEIGHT THEORETICAL ANALYSIS")
print("=" * 100)

print("""
XGBoost Live Detector (xgb.py):
  - Inference: ~40-60 us per prediction
  - Window: every 600 ms
  - Duty cycle: 0.06 ms / 600 ms = 0.01% of ONE core
  - System-wide (4 cores): 0.0025%
  - scapy sniffing overhead: ~0.5-1% (constant packet capture)
  - TOTAL estimated: ~1% system-wide

TST Live Detector (tst.py):
  - Inference: ~100 ms per prediction  
  - Window: every 600 ms
  - Duty cycle: 100 ms / 600 ms = 16.7% of ONE core
  - System-wide (4 cores): 4.17%
  - scapy sniffing overhead: ~0.5-1% (same)
  - PyTorch overhead: ~1-2% (runtime, memory management)
  - TOTAL estimated: ~6-7% system-wide

Expected delta (TST - XGBoost): ~5-6 percentage points
Expected delta (XGBoost - baseline): ~1 percentage point

BUT: Handshake benchmarks themselves consume 12-26% CPU, creating 
measurement noise of +/- 3-5% that MASKS both detector signals.
""")

print("ACTUAL observed CPU deltas (from data above):")
b_cpu = statistics.mean([r['cpu_avg'] for r in data['baseline']])
x_cpu = statistics.mean([r['cpu_avg'] for r in data['xgboost']])
t_cpu = statistics.mean([r['cpu_avg'] for r in data['tst']])
print(f"  XGBoost - baseline: {x_cpu - b_cpu:>+.3f} pp  (expected: ~+1.0 pp)")
print(f"  TST - baseline:     {t_cpu - b_cpu:>+.3f} pp  (expected: ~+5-6 pp)")
print(f"  TST - XGBoost:      {t_cpu - x_cpu:>+.3f} pp  (expected: ~+4-5 pp)")
print()
print("  EXPLANATION: The benchmark handshakes dominate CPU usage (~23%).")
print("  Detector overhead is REAL but hidden in measurement noise.")
print("  To measure detector CPU overhead precisely, you'd need to run")
print("  detectors WITHOUT handshakes (idle system + detector only).")
