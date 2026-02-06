#!/usr/bin/env python3
"""Deep analysis of benchmark runs"""
import json
from pathlib import Path
from collections import defaultdict
import statistics

def analyze_completed_run():
    print("=" * 70)
    print("    METRICS ANALYSIS: COMPLETED RUN 20260205_043852")
    print("=" * 70)
    
    # Load results
    results = [json.loads(l) for l in open('bench_analysis/chronos_run_20260205/benchmark_20260205_043852.jsonl') if l.strip()]
    
    print(f"\n📊 TOTAL SUITES: {len(results)}")
    print(f"   Success: {sum(1 for r in results if r.get('success'))}")
    print(f"   Failed:  {sum(1 for r in results if not r.get('success'))}")
    
    # The one failure
    failed = [r for r in results if not r.get('success')]
    if failed:
        print(f"\n❌ FAILURES:")
        for f in failed:
            print(f"   {f.get('suite_id')}: {f.get('error')}")
    
    # Analyze by algorithm
    by_kem = defaultdict(lambda: {'success': 0, 'fail': 0, 'hs': []})
    by_sig = defaultdict(lambda: {'success': 0, 'fail': 0, 'hs': []})
    by_aead = defaultdict(lambda: {'success': 0, 'fail': 0, 'hs': []})
    
    for r in results:
        kem = r.get('kem_name', 'unknown')
        sig = r.get('sig_name', 'unknown')
        aead = r.get('aead', 'unknown')
        
        if r.get('success'):
            by_kem[kem]['success'] += 1
            by_sig[sig]['success'] += 1
            by_aead[aead]['success'] += 1
            if r.get('handshake_ms', 0) > 0:
                by_kem[kem]['hs'].append(r['handshake_ms'])
                by_sig[sig]['hs'].append(r['handshake_ms'])
                by_aead[aead]['hs'].append(r['handshake_ms'])
        else:
            by_kem[kem]['fail'] += 1
            by_sig[sig]['fail'] += 1
            by_aead[aead]['fail'] += 1
    
    print("\n📦 KEM ALGORITHM PERFORMANCE:")
    kem_list = [(k, d) for k, d in by_kem.items()]
    kem_list.sort(key=lambda x: statistics.mean(x[1]['hs']) if x[1]['hs'] else 9999)
    for k, d in kem_list:
        avg = statistics.mean(d['hs']) if d['hs'] else 0
        status = "✅" if d['fail'] == 0 else "⚠️"
        print(f"   {status} {k}: {d['success']}/{d['success']+d['fail']} | avg={avg:.1f}ms")
    
    print("\n✍️ SIGNATURE ALGORITHM PERFORMANCE:")
    sig_list = [(s, d) for s, d in by_sig.items()]
    sig_list.sort(key=lambda x: statistics.mean(x[1]['hs']) if x[1]['hs'] else 9999)
    for s, d in sig_list:
        avg = statistics.mean(d['hs']) if d['hs'] else 0
        status = "✅" if d['fail'] == 0 else "⚠️"
        print(f"   {status} {s}: {d['success']}/{d['success']+d['fail']} | avg={avg:.1f}ms")
    
    print("\n🔐 AEAD ALGORITHM PERFORMANCE:")
    for a, d in sorted(by_aead.items()):
        avg = statistics.mean(d['hs']) if d['hs'] else 0
        status = "✅" if d['fail'] == 0 else "⚠️"
        print(f"   {status} {a}: {d['success']}/{d['success']+d['fail']} | avg={avg:.1f}ms")
    
    # Analyze comprehensive metrics
    print("\n" + "=" * 70)
    print("    COMPREHENSIVE METRICS ANALYSIS")
    print("=" * 70)
    
    comp_dir = Path('bench_analysis/chronos_run_20260205/comprehensive')
    files = list(comp_dir.glob('*_drone.json'))
    print(f"\n   Metrics files: {len(files)}")
    
    # Aggregate data plane stats
    data_plane_stats = {'ptx_in': [], 'throughput': [], 'aead_enc_ns': [], 'aead_dec_ns': []}
    power_stats = {'power_avg': [], 'energy_per_hs': []}
    system_stats = {'cpu_avg': [], 'temp': []}
    
    for f in files:
        with open(f) as fp:
            data = json.load(fp)
            
            dp = data.get('data_plane', {})
            if dp.get('ptx_in', 0):
                data_plane_stats['ptx_in'].append(dp['ptx_in'])
            if dp.get('achieved_throughput_mbps', 0):
                data_plane_stats['throughput'].append(dp['achieved_throughput_mbps'])
            if dp.get('aead_encrypt_avg_ns', 0):
                data_plane_stats['aead_enc_ns'].append(dp['aead_encrypt_avg_ns'])
            if dp.get('aead_decrypt_avg_ns', 0):
                data_plane_stats['aead_dec_ns'].append(dp['aead_decrypt_avg_ns'])
            
            pw = data.get('power_energy', {})
            if pw.get('power_avg_w', 0):
                power_stats['power_avg'].append(pw['power_avg_w'])
            if pw.get('energy_per_handshake_j', 0):
                power_stats['energy_per_hs'].append(pw['energy_per_handshake_j'])
            
            sys = data.get('system_drone', {})
            if sys.get('cpu_usage_avg_percent', 0):
                system_stats['cpu_avg'].append(sys['cpu_usage_avg_percent'])
            if sys.get('temperature_c', 0):
                system_stats['temp'].append(sys['temperature_c'])
    
    print("\n📈 DATA PLANE METRICS:")
    if data_plane_stats['ptx_in']:
        print(f"   Packets per suite: avg={statistics.mean(data_plane_stats['ptx_in']):.0f}, min={min(data_plane_stats['ptx_in'])}, max={max(data_plane_stats['ptx_in'])}")
    if data_plane_stats['throughput']:
        print(f"   Throughput: avg={statistics.mean(data_plane_stats['throughput']):.3f} Mbps")
    if data_plane_stats['aead_enc_ns']:
        print(f"   AEAD encrypt: avg={statistics.mean(data_plane_stats['aead_enc_ns'])/1000:.1f} µs")
    if data_plane_stats['aead_dec_ns']:
        print(f"   AEAD decrypt: avg={statistics.mean(data_plane_stats['aead_dec_ns'])/1000:.1f} µs")
    
    print("\n⚡ POWER METRICS:")
    if power_stats['power_avg']:
        print(f"   Average power: {statistics.mean(power_stats['power_avg']):.2f} W")
    if power_stats['energy_per_hs']:
        print(f"   Energy per handshake: avg={statistics.mean(power_stats['energy_per_hs']):.2f} J")
    
    print("\n🖥️ SYSTEM METRICS:")
    if system_stats['cpu_avg']:
        print(f"   CPU usage: avg={statistics.mean(system_stats['cpu_avg']):.1f}%")
    if system_stats['temp']:
        print(f"   Temperature: avg={statistics.mean(system_stats['temp']):.1f}°C, max={max(system_stats['temp']):.1f}°C")
    
    print("\n" + "=" * 70)
    print("    END ANALYSIS")
    print("=" * 70)

if __name__ == "__main__":
    analyze_completed_run()
