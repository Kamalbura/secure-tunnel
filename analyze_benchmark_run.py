#!/usr/bin/env python3
"""Analyze PQC Benchmark Run Results"""

import json
import statistics
from pathlib import Path
from collections import defaultdict

RESULTS_DIR = Path("bench_analysis/chronos_run_20260205")

def load_results():
    """Load all benchmark results from JSONL"""
    results = []
    jsonl_file = RESULTS_DIR / "benchmark_20260205_043852.jsonl"
    with open(jsonl_file, 'r') as f:
        for line in f:
            if line.strip():
                results.append(json.loads(line))
    return results

def load_comprehensive_metrics():
    """Load all comprehensive metrics files"""
    comp_dir = RESULTS_DIR / "comprehensive"
    metrics = {}
    for f in comp_dir.glob("*_drone.json"):
        with open(f, 'r') as fp:
            data = json.load(fp)
            suite_id = data.get('benchmark_context', {}).get('suite_id', f.stem)
            metrics[suite_id] = data
    return metrics

def analyze():
    results = load_results()
    
    print("=" * 70)
    print("        PQC SECURE TUNNEL BENCHMARK ANALYSIS")
    print("        Run: 2026-02-05 04:38:52Z")
    print("=" * 70)
    
    successful = [r for r in results if r.get('success')]
    failed = [r for r in results if not r.get('success')]
    
    print(f"\n📊 OVERALL SUMMARY")
    print(f"   Total Suites Tested: {len(results)}")
    print(f"   Successful:          {len(successful)} ✅")
    print(f"   Failed:              {len(failed)} ❌")
    
    if failed:
        print(f"\n❌ FAILED SUITES:")
        for r in failed:
            print(f"   • {r.get('suite_id')}: {r.get('error')}")
    
    # Handshake time analysis
    hs_data = [(r['suite_id'], r['handshake_ms'], r['kem_name'], r['sig_name'], r['aead']) 
               for r in successful if r.get('handshake_ms', 0) > 0]
    
    all_hs = [h[1] for h in hs_data]
    
    print(f"\n⏱️  HANDSHAKE TIME STATISTICS")
    print(f"   Minimum:  {min(all_hs):.2f} ms")
    print(f"   Maximum:  {max(all_hs):.2f} ms")
    print(f"   Average:  {statistics.mean(all_hs):.2f} ms")
    print(f"   Median:   {statistics.median(all_hs):.2f} ms")
    print(f"   Std Dev:  {statistics.stdev(all_hs):.2f} ms")
    
    # Sort by handshake time
    hs_data.sort(key=lambda x: x[1])
    
    print(f"\n🚀 TOP 10 FASTEST SUITES:")
    for suite, hs, kem, sig, aead in hs_data[:10]:
        print(f"   {hs:8.2f} ms - {kem} + {sig} + {aead}")
    
    print(f"\n🐢 TOP 10 SLOWEST SUITES:")
    for suite, hs, kem, sig, aead in hs_data[-10:]:
        print(f"   {hs:8.2f} ms - {kem} + {sig} + {aead}")
    
    # Group by KEM
    print(f"\n📦 HANDSHAKE TIME BY KEM ALGORITHM:")
    by_kem = defaultdict(list)
    for suite, hs, kem, sig, aead in hs_data:
        by_kem[kem].append(hs)
    
    kem_stats = []
    for kem, times in sorted(by_kem.items()):
        avg = statistics.mean(times)
        kem_stats.append((kem, avg, min(times), max(times), len(times)))
    
    kem_stats.sort(key=lambda x: x[1])
    for kem, avg, mn, mx, n in kem_stats:
        print(f"   {kem}:")
        print(f"      avg={avg:.2f}ms  min={mn:.2f}ms  max={mx:.2f}ms  (n={n})")
    
    # Group by Signature
    print(f"\n✍️  HANDSHAKE TIME BY SIGNATURE ALGORITHM:")
    by_sig = defaultdict(list)
    for suite, hs, kem, sig, aead in hs_data:
        by_sig[sig].append(hs)
    
    sig_stats = []
    for sig, times in sorted(by_sig.items()):
        avg = statistics.mean(times)
        sig_stats.append((sig, avg, min(times), max(times), len(times)))
    
    sig_stats.sort(key=lambda x: x[1])
    for sig, avg, mn, mx, n in sig_stats:
        print(f"   {sig}:")
        print(f"      avg={avg:.2f}ms  min={mn:.2f}ms  max={mx:.2f}ms  (n={n})")
    
    # Group by AEAD
    print(f"\n🔐 HANDSHAKE TIME BY AEAD ALGORITHM:")
    by_aead = defaultdict(list)
    for suite, hs, kem, sig, aead in hs_data:
        by_aead[aead].append(hs)
    
    for aead, times in sorted(by_aead.items()):
        avg = statistics.mean(times)
        print(f"   {aead}: avg={avg:.2f}ms  min={min(times):.2f}ms  max={max(times):.2f}ms  (n={len(times)})")
    
    # Key/Signature sizes
    print(f"\n📐 PUBLIC KEY & SIGNATURE SIZES:")
    size_data = [(r['kem_name'], r['sig_name'], r['pub_key_size_bytes'], r['sig_size_bytes'], r['ciphertext_size_bytes'])
                 for r in successful]
    
    # Unique combos
    seen = set()
    for kem, sig, pk, ss, ct in size_data:
        key = (kem, sig)
        if key not in seen:
            seen.add(key)
            print(f"   {kem} + {sig}:")
            print(f"      Public Key: {pk:,} bytes ({pk/1024:.1f} KB)")
            print(f"      Signature:  {ss:,} bytes")
            print(f"      Ciphertext: {ct:,} bytes")
    
    # Load comprehensive metrics for traffic analysis
    print(f"\n" + "=" * 70)
    print("        DETAILED TRAFFIC ANALYSIS")
    print("=" * 70)
    
    try:
        comp_metrics = load_comprehensive_metrics()
        print(f"\n   Loaded {len(comp_metrics)} comprehensive metrics files")
        
        # Analyze a sample
        traffic_stats = []
        for suite_id, data in comp_metrics.items():
            proxy = data.get('proxy', {})
            ptx_in = proxy.get('ptx_in', 0) or 0
            enc_out = proxy.get('enc_out', 0) or 0
            traffic_stats.append((suite_id, ptx_in, enc_out))
        
        traffic_stats.sort(key=lambda x: x[1], reverse=True)
        
        with_traffic = [(s, p, e) for s, p, e in traffic_stats if p > 0]
        no_traffic = [(s, p, e) for s, p, e in traffic_stats if p == 0]
        
        print(f"\n   Suites WITH traffic: {len(with_traffic)}")
        print(f"   Suites WITHOUT traffic: {len(no_traffic)}")
        
        if with_traffic:
            print(f"\n   📈 TOP TRAFFIC SUITES (by ptx_in):")
            for suite, ptx, enc in with_traffic[:5]:
                print(f"      {suite}: ptx_in={ptx:,} enc_out={enc:,}")
        
    except Exception as e:
        print(f"   Warning: Could not load comprehensive metrics: {e}")
    
    print(f"\n" + "=" * 70)
    print("        END OF ANALYSIS")
    print("=" * 70)

if __name__ == "__main__":
    analyze()
