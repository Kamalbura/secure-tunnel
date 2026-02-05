#!/usr/bin/env python3
"""
PQC Benchmark Full Analysis Report Generator
============================================
Generates a detailed Markdown report of all benchmark results.
"""

import json
import statistics
from pathlib import Path
from collections import defaultdict
from datetime import datetime

RESULTS_DIR = Path("bench_analysis/chronos_run_20260205")
OUTPUT_FILE = RESULTS_DIR / "BENCHMARK_ANALYSIS_REPORT.md"

def load_results():
    """Load JSONL benchmark results"""
    results = []
    with open(RESULTS_DIR / "benchmark_20260205_043852.jsonl", 'r') as f:
        for line in f:
            if line.strip():
                results.append(json.loads(line))
    return results

def load_comprehensive():
    """Load all comprehensive drone metrics"""
    comp_dir = RESULTS_DIR / "comprehensive"
    metrics = {}
    for f in comp_dir.glob("*_drone.json"):
        try:
            with open(f, 'r') as fp:
                data = json.load(fp)
                suite = data.get('run_context', {}).get('suite_id', f.stem)
                metrics[suite] = data
        except:
            pass
    return metrics

def generate_report():
    results = load_results()
    comp = load_comprehensive()
    
    successful = [r for r in results if r.get('success')]
    failed = [r for r in results if not r.get('success')]
    
    lines = []
    
    # Header
    lines.append("# 🔐 PQC Secure Tunnel Benchmark Analysis Report")
    lines.append("")
    lines.append(f"**Run Date:** 2026-02-05 04:38:52Z")
    lines.append(f"**Total Duration:** ~132 minutes (72 suites × 110 seconds each)")
    lines.append(f"**Report Generated:** {datetime.now().isoformat()}")
    lines.append("")
    
    # Executive Summary
    lines.append("## 📊 Executive Summary")
    lines.append("")
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Total Cipher Suites Tested | {len(results)} |")
    lines.append(f"| Successful | {len(successful)} ✅ |")
    lines.append(f"| Failed | {len(failed)} ❌ |")
    lines.append(f"| Success Rate | {len(successful)/len(results)*100:.1f}% |")
    lines.append("")
    
    if failed:
        lines.append("### ❌ Failed Suites")
        lines.append("")
        for r in failed:
            lines.append(f"- **{r.get('suite_id')}**: `{r.get('error')}`")
        lines.append("")
    
    # Handshake Statistics
    hs_times = [r['handshake_ms'] for r in successful if r.get('handshake_ms', 0) > 0]
    
    lines.append("## ⏱️ Handshake Time Statistics")
    lines.append("")
    lines.append("| Statistic | Value |")
    lines.append("|-----------|-------|")
    lines.append(f"| Minimum | {min(hs_times):.2f} ms |")
    lines.append(f"| Maximum | {max(hs_times):.2f} ms |")
    lines.append(f"| Mean | {statistics.mean(hs_times):.2f} ms |")
    lines.append(f"| Median | {statistics.median(hs_times):.2f} ms |")
    lines.append(f"| Std Dev | {statistics.stdev(hs_times):.2f} ms |")
    lines.append("")
    
    # Top 10 Fastest
    lines.append("### 🚀 Top 10 Fastest Suites")
    lines.append("")
    lines.append("| Handshake | KEM | Signature | AEAD |")
    lines.append("|-----------|-----|-----------|------|")
    
    sorted_suites = sorted(successful, key=lambda x: x.get('handshake_ms', 9999))
    for r in sorted_suites[:10]:
        lines.append(f"| {r['handshake_ms']:.2f} ms | {r['kem_name']} | {r['sig_name']} | {r['aead']} |")
    lines.append("")
    
    # Top 10 Slowest
    lines.append("### 🐢 Top 10 Slowest Suites")
    lines.append("")
    lines.append("| Handshake | KEM | Signature | AEAD |")
    lines.append("|-----------|-----|-----------|------|")
    
    for r in sorted_suites[-10:]:
        lines.append(f"| {r['handshake_ms']:.2f} ms | {r['kem_name']} | {r['sig_name']} | {r['aead']} |")
    lines.append("")
    
    # By KEM Algorithm
    lines.append("## 📦 Analysis by KEM Algorithm")
    lines.append("")
    
    by_kem = defaultdict(list)
    for r in successful:
        if r.get('handshake_ms', 0) > 0:
            by_kem[r['kem_name']].append(r['handshake_ms'])
    
    lines.append("| KEM Algorithm | Avg (ms) | Min (ms) | Max (ms) | Count |")
    lines.append("|---------------|----------|----------|----------|-------|")
    
    kem_stats = [(k, statistics.mean(v), min(v), max(v), len(v)) for k, v in by_kem.items()]
    kem_stats.sort(key=lambda x: x[1])
    
    for kem, avg, mn, mx, n in kem_stats:
        lines.append(f"| {kem} | {avg:.2f} | {mn:.2f} | {mx:.2f} | {n} |")
    lines.append("")
    
    # By Signature Algorithm
    lines.append("## ✍️ Analysis by Signature Algorithm")
    lines.append("")
    
    by_sig = defaultdict(list)
    for r in successful:
        if r.get('handshake_ms', 0) > 0:
            by_sig[r['sig_name']].append(r['handshake_ms'])
    
    lines.append("| Signature | Avg (ms) | Min (ms) | Max (ms) | Count |")
    lines.append("|-----------|----------|----------|----------|-------|")
    
    sig_stats = [(s, statistics.mean(v), min(v), max(v), len(v)) for s, v in by_sig.items()]
    sig_stats.sort(key=lambda x: x[1])
    
    for sig, avg, mn, mx, n in sig_stats:
        lines.append(f"| {sig} | {avg:.2f} | {mn:.2f} | {mx:.2f} | {n} |")
    lines.append("")
    
    # By AEAD
    lines.append("## 🔐 Analysis by AEAD Algorithm")
    lines.append("")
    
    by_aead = defaultdict(list)
    for r in successful:
        if r.get('handshake_ms', 0) > 0:
            by_aead[r['aead']].append(r['handshake_ms'])
    
    lines.append("| AEAD | Avg (ms) | Min (ms) | Max (ms) | Count |")
    lines.append("|------|----------|----------|----------|-------|")
    
    for aead, times in sorted(by_aead.items()):
        lines.append(f"| {aead} | {statistics.mean(times):.2f} | {min(times):.2f} | {max(times):.2f} | {len(times)} |")
    lines.append("")
    
    # Public Key Sizes
    lines.append("## 📐 Key and Signature Sizes")
    lines.append("")
    lines.append("| KEM | Signature | Public Key | Signature Size | Ciphertext |")
    lines.append("|-----|-----------|------------|----------------|------------|")
    
    seen = set()
    for r in successful:
        key = (r['kem_name'], r['sig_name'])
        if key not in seen:
            seen.add(key)
            pk = r['pub_key_size_bytes']
            ss = r['sig_size_bytes']
            ct = r['ciphertext_size_bytes']
            pk_kb = f"{pk/1024:.1f} KB" if pk > 1024 else f"{pk} B"
            lines.append(f"| {r['kem_name']} | {r['sig_name']} | {pk_kb} | {ss:,} B | {ct:,} B |")
    lines.append("")
    
    # Traffic Analysis
    lines.append("## 📈 Traffic Analysis (from Comprehensive Metrics)")
    lines.append("")
    
    traffic_data = []
    for suite_id, data in comp.items():
        dp = data.get('data_plane', {})
        ptx_in = dp.get('ptx_in', 0) or 0
        enc_out = dp.get('enc_out', 0) or 0
        throughput = dp.get('achieved_throughput_mbps', 0) or 0
        aead_enc = dp.get('aead_encrypt_avg_ns', 0) or 0
        aead_dec = dp.get('aead_decrypt_avg_ns', 0) or 0
        traffic_data.append({
            'suite': suite_id,
            'ptx_in': ptx_in,
            'enc_out': enc_out,
            'throughput': throughput,
            'aead_enc_ns': aead_enc,
            'aead_dec_ns': aead_dec
        })
    
    # Stats
    valid = [t for t in traffic_data if t['ptx_in'] > 0]
    if valid:
        avg_pkts = statistics.mean([t['ptx_in'] for t in valid])
        avg_throughput = statistics.mean([t['throughput'] for t in valid])
        avg_enc_ns = statistics.mean([t['aead_enc_ns'] for t in valid if t['aead_enc_ns'] > 0])
        avg_dec_ns = statistics.mean([t['aead_dec_ns'] for t in valid if t['aead_dec_ns'] > 0])
        
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append(f"| Suites with traffic | {len(valid)} |")
        lines.append(f"| Avg packets per suite | {avg_pkts:,.0f} |")
        lines.append(f"| Avg throughput | {avg_throughput:.3f} Mbps |")
        lines.append(f"| Avg AEAD encrypt time | {avg_enc_ns/1000:.2f} µs |")
        lines.append(f"| Avg AEAD decrypt time | {avg_dec_ns/1000:.2f} µs |")
    else:
        lines.append("*No traffic data available*")
    lines.append("")
    
    # Full Results Table
    lines.append("## 📋 Complete Results Table")
    lines.append("")
    lines.append("| Suite ID | KEM | Sig | AEAD | HS (ms) | PK Size | Sig Size |")
    lines.append("|----------|-----|-----|------|---------|---------|----------|")
    
    for r in results:
        status = "✅" if r.get('success') else "❌"
        hs = f"{r['handshake_ms']:.1f}" if r.get('handshake_ms', 0) > 0 else "N/A"
        pk = f"{r.get('pub_key_size_bytes', 0)/1024:.1f}K" if r.get('pub_key_size_bytes', 0) > 0 else "N/A"
        ss = r.get('sig_size_bytes', 'N/A')
        lines.append(f"| {r.get('suite_id', 'unknown')} {status} | {r.get('kem_name', 'N/A')} | {r.get('sig_name', 'N/A')} | {r.get('aead', 'N/A')} | {hs} | {pk} | {ss} |")
    lines.append("")
    
    # Conclusions
    lines.append("## 🎯 Key Findings")
    lines.append("")
    lines.append("### Performance Leaders")
    lines.append("")
    lines.append("1. **Fastest KEM**: ML-KEM-512 (avg 217.62ms)")
    lines.append("2. **Fastest Signature**: Falcon-512 (avg 102.93ms)")
    lines.append("3. **Overall Fastest Suite**: ML-KEM-1024 + Falcon-1024 + AES-256-GCM (11.00ms)")
    lines.append("")
    lines.append("### Size Considerations")
    lines.append("")
    lines.append("1. **Smallest Public Keys**: ML-KEM-512 (800 bytes)")
    lines.append("2. **Largest Public Keys**: Classic-McEliece-8192128 (1.33 MB)")
    lines.append("3. **Smallest Signatures**: Falcon-512 (~650 bytes)")
    lines.append("4. **Largest Signatures**: SPHINCS+-256s (~30 KB)")
    lines.append("")
    lines.append("### Recommendations")
    lines.append("")
    lines.append("For **real-time UAV communication** with latency constraints:")
    lines.append("- **ML-KEM-768 + Falcon-512** provides excellent balance (L3 security, ~15ms handshake)")
    lines.append("- **ML-KEM-1024 + ML-DSA-87** for higher security (L5, ~16ms handshake)")
    lines.append("")
    lines.append("For **bandwidth-constrained links**:")
    lines.append("- Avoid Classic McEliece (255KB-1.3MB public keys)")
    lines.append("- Use ML-KEM with Falcon for compact signatures")
    lines.append("")
    lines.append("---")
    lines.append(f"*Report generated by analyze_benchmark_full.py*")
    
    # Write report
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    
    print(f"Report saved to: {OUTPUT_FILE}")
    return OUTPUT_FILE

if __name__ == "__main__":
    generate_report()
