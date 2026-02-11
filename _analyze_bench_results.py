import json, statistics

comp = json.load(open('bench_ddos_results/20260211_091245/comparison.json'))
rows = comp['per_suite']
summary = comp['summary']

print('='*90)
print('  FULL BENCHMARK RESULTS — Old-Style Detectors (seniors architecture)')
print('='*90)

# Ordering check
print(f"  CPU ordering  B <= X <= T : {summary['cpu_ordering_correct']}/72 correct, {summary['cpu_ordering_violated']} violated")
print(f"  Power ordering B <= X <= T: {summary['power_ordering_correct']}/72 correct, {summary['power_ordering_violated']} violated")
print()

# Collect metrics
b_cpu, x_cpu, t_cpu = [], [], []
b_pow, x_pow, t_pow = [], [], []
b_lat, x_lat, t_lat = [], [], []

for r in rows:
    b_cpu.append(r.get('baseline_cpu_avg', 0))
    x_cpu.append(r.get('xgb_cpu_avg', 0) or 0)
    t_cpu.append(r.get('tst_cpu_avg', 0) or 0)
    
    bp = r.get('baseline_power_mw')
    xp = r.get('xgb_power_mw')
    tp = r.get('tst_power_mw')
    if bp: b_pow.append(bp)
    if xp: x_pow.append(xp)
    if tp: t_pow.append(tp)
    
    b_lat.append(r.get('baseline_mean_ms', 0))
    if 'xgb_mean_ms' in r: x_lat.append(r['xgb_mean_ms'])
    if 'tst_mean_ms' in r: t_lat.append(r['tst_mean_ms'])

print(f"  {'Metric':<20s} {'Baseline':>12s} {'+ XGBoost':>12s} {'+ TST':>12s}")
print(f"  {'-'*20} {'-'*12} {'-'*12} {'-'*12}")
print(f"  {'CPU avg %':<20s} {statistics.mean(b_cpu):12.1f} {statistics.mean(x_cpu):12.1f} {statistics.mean(t_cpu):12.1f}")
print(f"  {'Power avg mW':<20s} {statistics.mean(b_pow):12.0f} {statistics.mean(x_pow):12.0f} {statistics.mean(t_pow):12.0f}")
print(f"  {'Latency mean ms':<20s} {statistics.mean(b_lat):12.1f} {statistics.mean(x_lat):12.1f} {statistics.mean(t_lat):12.1f}")
print(f"  {'Latency median ms':<20s} {statistics.median(b_lat):12.1f} {statistics.median(x_lat):12.1f} {statistics.median(t_lat):12.1f}")

print()
print(f"  Overhead:")
print(f"    XGBoost mean: {summary['xgb_overhead_mean_pct']}%  median: {summary['xgb_overhead_median_pct']}%")
print(f"    TST     mean: {summary['tst_overhead_mean_pct']}%  median: {summary['tst_overhead_median_pct']}%")

# Check latency ordering
lat_ok = sum(1 for r in rows if 'xgb_mean_ms' in r and 'tst_mean_ms' in r 
             and r['baseline_mean_ms'] <= r['xgb_mean_ms'] <= r['tst_mean_ms'])
lat_fail = sum(1 for r in rows if 'xgb_mean_ms' in r and 'tst_mean_ms' in r 
               and not (r['baseline_mean_ms'] <= r['xgb_mean_ms'] <= r['tst_mean_ms']))
print(f"  Latency ordering B <= X <= T: {lat_ok}/72 correct, {lat_fail} violated")

# Show per-KEM-family breakdown
print()
print(f"  {'KEM Family':<25s} {'B CPU':>8s} {'X CPU':>8s} {'T CPU':>8s} {'B mW':>8s} {'X mW':>8s} {'T mW':>8s}")
print(f"  {'-'*25} {'-'*8} {'-'*8} {'-'*8} {'-'*8} {'-'*8} {'-'*8}")

families = {}
for r in rows:
    sid = r['suite_id']
    if 'mlkem512' in sid or 'mlkem768' in sid or 'mlkem1024' in sid:
        fam = 'ML-KEM'
    elif 'hqc' in sid:
        fam = 'HQC'
    elif 'classicmceliece' in sid:
        fam = 'Classic-McEliece'
    else:
        fam = 'Other'
    
    if fam not in families:
        families[fam] = {'b_cpu': [], 'x_cpu': [], 't_cpu': [], 'b_pow': [], 'x_pow': [], 't_pow': []}
    families[fam]['b_cpu'].append(r.get('baseline_cpu_avg', 0))
    families[fam]['x_cpu'].append(r.get('xgb_cpu_avg', 0) or 0)
    families[fam]['t_cpu'].append(r.get('tst_cpu_avg', 0) or 0)
    bp = r.get('baseline_power_mw')
    xp = r.get('xgb_power_mw')
    tp = r.get('tst_power_mw')
    if bp: families[fam]['b_pow'].append(bp)
    if xp: families[fam]['x_pow'].append(xp)
    if tp: families[fam]['t_pow'].append(tp)

for fam in ['ML-KEM', 'HQC', 'Classic-McEliece']:
    d = families[fam]
    print(f"  {fam:<25s} {statistics.mean(d['b_cpu']):7.1f}% {statistics.mean(d['x_cpu']):7.1f}% {statistics.mean(d['t_cpu']):7.1f}% "
          f"{statistics.mean(d['b_pow']):7.0f} {statistics.mean(d['x_pow']):7.0f} {statistics.mean(d['t_pow']):7.0f}")

print('='*90)
