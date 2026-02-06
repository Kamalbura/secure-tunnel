#!/usr/bin/env python3
"""Analyze comprehensive benchmark metrics from all suite files."""
import json
import os
from pathlib import Path
from collections import defaultdict

analysis_dir = Path(r'C:\Users\burak\ptojects\secure-tunnel\_tmp_analysis')
files = sorted(analysis_dir.glob('*.json'))

print(f'=== COMPREHENSIVE METRICS ANALYSIS: {len(files)} FILES ===\n')

# Parse all files
suites = []
for f in files:
    try:
        with open(f) as fp:
            d = json.load(fp)
            suites.append({
                'file': f.name,
                'suite': d['run_context']['suite_id'],
                'kem': d['crypto_identity']['kem_algorithm'],
                'kem_family': d['crypto_identity']['kem_family'],
                'sig': d['crypto_identity']['sig_algorithm'],
                'sig_family': d['crypto_identity']['sig_family'],
                'aead': d['crypto_identity']['aead_algorithm'],
                'nist_level': d['crypto_identity']['suite_security_level'],
                'handshake_ms': d['handshake']['protocol_handshake_duration_ms'],
                'e2e_handshake_ms': d['handshake']['end_to_end_handshake_duration_ms'],
                'handshake_success': d['handshake']['handshake_success'],
                'ptx_in': d['data_plane']['ptx_in'],
                'ptx_out': d['data_plane']['ptx_out'],
                'packets_sent': d['data_plane']['packets_sent'],
                'throughput_mbps': d['data_plane']['achieved_throughput_mbps'],
                'power_w': d['power_energy']['power_avg_w'],
                'power_peak_w': d['power_energy']['power_peak_w'],
                'energy_j': d['power_energy']['energy_total_j'],
                'energy_per_handshake_j': d['power_energy']['energy_per_handshake_j'],
                'cpu_avg': d['system_drone']['cpu_usage_avg_percent'],
                'cpu_peak': d['system_drone']['cpu_usage_peak_percent'],
                'temp_c': d['system_drone']['temperature_c'],
                'memory_mb': d['system_drone']['memory_rss_mb'],
                'mav_msgs': d['mavproxy_drone']['mavproxy_drone_total_msgs_received'],
                'heartbeat_ms': d['mavproxy_drone']['mavproxy_drone_heartbeat_interval_ms'],
                'heartbeat_loss': d['mavproxy_drone']['mavproxy_drone_heartbeat_loss_count'],
                'duration_ms': d['lifecycle']['suite_active_duration_ms'],
                'pass_fail': d['validation']['benchmark_pass_fail'],
            })
    except Exception as e:
        print(f'  ERROR parsing {f.name}: {e}')

# Group by KEM family
print('=' * 70)
print('1. HANDSHAKE TIMES BY KEM FAMILY')
print('=' * 70)
kem_stats = defaultdict(list)
for s in suites:
    if s['handshake_ms']:
        kem_stats[s['kem_family']].append(s['handshake_ms'])

for fam, times in sorted(kem_stats.items()):
    avg = sum(times)/len(times)
    mn, mx = min(times), max(times)
    print(f'  {fam:20s}: avg={avg:8.2f}ms  min={mn:8.2f}ms  max={mx:8.2f}ms  (n={len(times)})')

# Group by SIG family
print()
print('=' * 70)
print('2. HANDSHAKE TIMES BY SIGNATURE FAMILY')
print('=' * 70)
sig_stats = defaultdict(list)
for s in suites:
    if s['handshake_ms']:
        sig_stats[s['sig_family']].append(s['handshake_ms'])

for fam, times in sorted(sig_stats.items()):
    avg = sum(times)/len(times)
    mn, mx = min(times), max(times)
    print(f'  {fam:20s}: avg={avg:8.2f}ms  min={mn:8.2f}ms  max={mx:8.2f}ms  (n={len(times)})')

# Group by AEAD
print()
print('=' * 70)
print('3. HANDSHAKE TIMES BY AEAD CIPHER')
print('=' * 70)
aead_stats = defaultdict(list)
for s in suites:
    if s['handshake_ms']:
        aead_stats[s['aead']].append(s['handshake_ms'])

for aead, times in sorted(aead_stats.items()):
    avg = sum(times)/len(times)
    print(f'  {aead:20s}: avg={avg:8.2f}ms  (n={len(times)})')

# Power Analysis
print()
print('=' * 70)
print('4. POWER & ENERGY BY KEM FAMILY')
print('=' * 70)
power_stats = defaultdict(list)
energy_stats = defaultdict(list)
for s in suites:
    if s['power_w'] is not None:
        power_stats[s['kem_family']].append(s['power_w'])
    if s['energy_per_handshake_j'] is not None:
        energy_stats[s['kem_family']].append(s['energy_per_handshake_j'])

for fam in sorted(power_stats.keys()):
    p = power_stats[fam]
    e = energy_stats[fam]
    p_avg = sum(p)/len(p) if p else 0
    e_avg = sum(e)/len(e) if e else 0
    print(f'  {fam:20s}: power_avg={p_avg:.2f}W  energy_per_hs={e_avg:.2f}J')

# CPU/Temp Analysis
print()
print('=' * 70)
print('5. CPU & TEMPERATURE BY KEM FAMILY')
print('=' * 70)
cpu_stats = defaultdict(list)
temp_stats = defaultdict(list)
for s in suites:
    cpu_stats[s['kem_family']].append(s['cpu_avg'])
    temp_stats[s['kem_family']].append(s['temp_c'])

for fam in sorted(cpu_stats.keys()):
    c = cpu_stats[fam]
    t = temp_stats[fam]
    print(f'  {fam:20s}: cpu_avg={sum(c)/len(c):.1f}%  temp_avg={sum(t)/len(t):.1f}C')

# MAVLink Health
print()
print('=' * 70)
print('6. MAVLINK TELEMETRY HEALTH')
print('=' * 70)
total_hb_loss = sum(s['heartbeat_loss'] for s in suites)
avg_hb_interval = sum(s['heartbeat_ms'] for s in suites) / len(suites)
avg_mav_msgs = sum(s['mav_msgs'] for s in suites) / len(suites)
print(f'  Total heartbeat losses: {total_hb_loss}')
print(f'  Avg heartbeat interval: {avg_hb_interval:.2f}ms (target: 1000ms)')
print(f'  Avg MAVLink msgs/suite: {avg_mav_msgs:.0f}')

# Fastest & Slowest
print()
print('=' * 70)
print('7. TOP 10 FASTEST HANDSHAKES')
print('=' * 70)
fastest = sorted([s for s in suites if s['handshake_ms']], key=lambda x: x['handshake_ms'])[:10]
for i, s in enumerate(fastest, 1):
    suite_name = s['suite']
    hs = s['handshake_ms']
    print(f'  {i:2d}. {suite_name:55s} {hs:8.2f}ms')

print()
print('=' * 70)
print('8. TOP 10 SLOWEST HANDSHAKES')
print('=' * 70)
slowest = sorted([s for s in suites if s['handshake_ms']], key=lambda x: -x['handshake_ms'])[:10]
for i, s in enumerate(slowest, 1):
    suite_name = s['suite']
    hs = s['handshake_ms']
    print(f'  {i:2d}. {suite_name:55s} {hs:8.2f}ms')

# Validation Summary
print()
print('=' * 70)
print('9. VALIDATION SUMMARY')
print('=' * 70)
pass_count = sum(1 for s in suites if s['pass_fail'] == 'PASS')
fail_count = sum(1 for s in suites if s['pass_fail'] == 'FAIL')
print(f'  PASS: {pass_count}')
print(f'  FAIL: {fail_count}')
print(f'  Total: {len(suites)}')

# NIST Level Breakdown
print()
print('=' * 70)
print('10. BY NIST SECURITY LEVEL')
print('=' * 70)
level_stats = defaultdict(list)
for s in suites:
    if s['handshake_ms']:
        level_stats[s['nist_level']].append(s['handshake_ms'])

for level, times in sorted(level_stats.items()):
    avg = sum(times)/len(times)
    print(f'  {level}: avg={avg:8.2f}ms  (n={len(times)})')

# Data Plane Summary
print()
print('=' * 70)
print('11. DATA PLANE STATISTICS')
print('=' * 70)
ptx_in_vals = [s['ptx_in'] for s in suites if s['ptx_in'] is not None]
ptx_out_vals = [s['ptx_out'] for s in suites if s['ptx_out'] is not None]
throughput_vals = [s['throughput_mbps'] for s in suites if s['throughput_mbps'] is not None]
total_ptx_in = sum(ptx_in_vals) if ptx_in_vals else 0
total_ptx_out = sum(ptx_out_vals) if ptx_out_vals else 0
avg_throughput = sum(throughput_vals)/len(throughput_vals) if throughput_vals else 0
print(f'  Total packets IN (from FC): {total_ptx_in:,}')
print(f'  Total packets OUT (to GCS): {total_ptx_out:,}')
print(f'  Avg throughput: {avg_throughput:.4f} Mbps')

# Energy Summary
print()
print('=' * 70)
print('12. ENERGY CONSUMPTION SUMMARY')
print('=' * 70)
energy_vals = [s['energy_j'] for s in suites if s['energy_j'] is not None]
power_vals = [s['power_w'] for s in suites if s['power_w'] is not None]
peak_vals = [s['power_peak_w'] for s in suites if s['power_peak_w'] is not None]
total_energy = sum(energy_vals) if energy_vals else 0
avg_power = sum(power_vals)/len(power_vals) if power_vals else 0
peak_power = max(peak_vals) if peak_vals else 0
print(f'  Total energy consumed: {total_energy:.2f} J ({total_energy/3600:.4f} Wh)')
print(f'  Average power draw: {avg_power:.2f} W')
print(f'  Peak power observed: {peak_power:.2f} W')

# Sliding Window Analysis (10 suites at a time)
print()
print('=' * 70)
print('13. SLIDING WINDOW ANALYSIS (10 suites per window)')
print('=' * 70)
window_size = 10
for i in range(0, len(suites), window_size):
    window = suites[i:i+window_size]
    if not window:
        break
    hs_times = [s['handshake_ms'] for s in window if s['handshake_ms']]
    powers = [s['power_w'] for s in window if s['power_w'] is not None]
    temps = [s['temp_c'] for s in window if s['temp_c'] is not None]
    avg_hs = sum(hs_times)/len(hs_times) if hs_times else 0
    avg_pwr = sum(powers)/len(powers) if powers else 0
    avg_tmp = sum(temps)/len(temps) if temps else 0
    first_suite = window[0]['suite'][:25]
    last_suite = window[-1]['suite'][:25]
    print(f'  Window {i//window_size + 1:2d} [{first_suite}...]: hs_avg={avg_hs:7.1f}ms  power={avg_pwr:.2f}W  temp={avg_tmp:.1f}C')

print()
print('=' * 70)
print('ANALYSIS COMPLETE')
print('=' * 70)
