#!/usr/bin/env python3
"""
COMPLETE 72-SUITE ANALYSIS - PQC Benchmark Run
Merges benchmark_results.json (72 suites) with comprehensive files (45 suites)
Run ID: live_run_20260205_145749
"""
import json
import csv
import statistics
from pathlib import Path
from collections import defaultdict

RUN_DIR = Path(__file__).parent
RESULTS_JSON = RUN_DIR / "benchmark_results_20260205_145749.json"
RESULTS_CSV = RUN_DIR / "benchmark_results_20260205_145749.csv"
COMPREHENSIVE_DIR = RUN_DIR / "comprehensive"


def load_benchmark_results():
    """Load the main benchmark results (72 suites)."""
    with open(RESULTS_JSON) as f:
        data = json.load(f)
    return data


def load_comprehensive_files():
    """Load all comprehensive metric files into a dict by suite_id."""
    comp_data = {}
    for f in COMPREHENSIVE_DIR.glob("*.json"):
        try:
            with open(f) as fp:
                d = json.load(fp)
                suite_id = d.get('run_context', {}).get('suite_id', '')
                if suite_id:
                    comp_data[suite_id] = d
        except:
            pass
    return comp_data


def print_header(title):
    print()
    print("=" * 80)
    print(f" {title}")
    print("=" * 80)


def main():
    print("=" * 80)
    print(" COMPLETE 72-SUITE PQC BENCHMARK ANALYSIS")
    print(" Run ID: live_run_20260205_145749")
    print(" Date: 2026-02-05 14:57:49 - 17:10:30 UTC")
    print("=" * 80)
    
    # Load data
    results = load_benchmark_results()
    comp_data = load_comprehensive_files()
    
    suites = results['suites']
    print(f"\nTotal suites in benchmark_results.json: {len(suites)}")
    print(f"Comprehensive files available: {len(comp_data)}")
    
    # =========================================================================
    # SECTION 1: COMPLETE HANDSHAKE TABLE
    # =========================================================================
    print_header("1. COMPLETE HANDSHAKE PERFORMANCE (ALL 72 SUITES)")
    
    print(f"\n{'#':>3} {'Suite':<55} {'HS(ms)':>10} {'Success':>8}")
    print("-" * 80)
    
    sorted_suites = sorted(suites, key=lambda x: x['handshake_ms'])
    for i, s in enumerate(sorted_suites, 1):
        suite = s['suite_id'][:53]
        hs = s['handshake_ms']
        success = "OK" if s['success'] else "FAIL"
        print(f"{i:3d} {suite:<55} {hs:10.2f} {success:>8}")
    
    # =========================================================================
    # SECTION 2: BY KEM FAMILY
    # =========================================================================
    print_header("2. HANDSHAKE BY KEM FAMILY (72 SUITES)")
    
    kem_groups = defaultdict(list)
    for s in suites:
        kem_name = s['kem_name']
        if 'McEliece-348864' in kem_name:
            family = 'Classic-McEliece-348864'
        elif 'McEliece-460896' in kem_name:
            family = 'Classic-McEliece-460896'
        elif 'McEliece-8192128' in kem_name:
            family = 'Classic-McEliece-8192128'
        elif 'HQC-128' in kem_name:
            family = 'HQC-128'
        elif 'HQC-192' in kem_name:
            family = 'HQC-192'
        elif 'HQC-256' in kem_name:
            family = 'HQC-256'
        elif 'ML-KEM-512' in kem_name:
            family = 'ML-KEM-512'
        elif 'ML-KEM-768' in kem_name:
            family = 'ML-KEM-768'
        elif 'ML-KEM-1024' in kem_name:
            family = 'ML-KEM-1024'
        else:
            family = kem_name
        kem_groups[family].append(s['handshake_ms'])
    
    print(f"\n{'KEM Family':<25} {'Avg(ms)':>10} {'Min(ms)':>10} {'Max(ms)':>10} {'n':>5}")
    print("-" * 65)
    for fam in sorted(kem_groups.keys()):
        times = kem_groups[fam]
        avg = statistics.mean(times)
        mn = min(times)
        mx = max(times)
        print(f"{fam:<25} {avg:10.2f} {mn:10.2f} {mx:10.2f} {len(times):5d}")
    
    # Aggregate by KEM type
    print("\n[Aggregated by KEM Type]")
    kem_type_groups = defaultdict(list)
    for s in suites:
        kem_name = s['kem_name']
        if 'McEliece' in kem_name:
            kem_type = 'Classic-McEliece'
        elif 'HQC' in kem_name:
            kem_type = 'HQC'
        elif 'ML-KEM' in kem_name:
            kem_type = 'ML-KEM'
        else:
            kem_type = kem_name
        kem_type_groups[kem_type].append(s['handshake_ms'])
    
    print(f"\n{'KEM Type':<20} {'Avg(ms)':>10} {'Min(ms)':>10} {'Max(ms)':>10} {'n':>5}")
    print("-" * 60)
    for fam in sorted(kem_type_groups.keys()):
        times = kem_type_groups[fam]
        avg = statistics.mean(times)
        mn = min(times)
        mx = max(times)
        print(f"{fam:<20} {avg:10.2f} {mn:10.2f} {mx:10.2f} {len(times):5d}")
    
    # =========================================================================
    # SECTION 3: BY SIGNATURE FAMILY
    # =========================================================================
    print_header("3. HANDSHAKE BY SIGNATURE FAMILY (72 SUITES)")
    
    sig_groups = defaultdict(list)
    for s in suites:
        sig_name = s['sig_name']
        if 'Falcon-512' in sig_name:
            family = 'Falcon-512'
        elif 'Falcon-1024' in sig_name:
            family = 'Falcon-1024'
        elif 'ML-DSA-44' in sig_name:
            family = 'ML-DSA-44'
        elif 'ML-DSA-65' in sig_name:
            family = 'ML-DSA-65'
        elif 'ML-DSA-87' in sig_name:
            family = 'ML-DSA-87'
        elif 'SPHINCS+-SHA2-128s' in sig_name or 'sphincs128s' in sig_name.lower():
            family = 'SPHINCS+-128s'
        elif 'SPHINCS+-SHA2-192s' in sig_name or 'sphincs192s' in sig_name.lower():
            family = 'SPHINCS+-192s'
        elif 'SPHINCS+-SHA2-256s' in sig_name or 'sphincs256s' in sig_name.lower():
            family = 'SPHINCS+-256s'
        else:
            family = sig_name
        sig_groups[family].append(s['handshake_ms'])
    
    print(f"\n{'SIG Family':<20} {'Avg(ms)':>10} {'Min(ms)':>10} {'Max(ms)':>10} {'n':>5}")
    print("-" * 55)
    for fam in sorted(sig_groups.keys()):
        times = sig_groups[fam]
        avg = statistics.mean(times)
        mn = min(times)
        mx = max(times)
        print(f"{fam:<20} {avg:10.2f} {mn:10.2f} {mx:10.2f} {len(times):5d}")
    
    # Aggregate by SIG type
    print("\n[Aggregated by SIG Type]")
    sig_type_groups = defaultdict(list)
    for s in suites:
        sig_name = s['sig_name']
        if 'Falcon' in sig_name:
            sig_type = 'Falcon'
        elif 'ML-DSA' in sig_name:
            sig_type = 'ML-DSA'
        elif 'SPHINCS' in sig_name:
            sig_type = 'SPHINCS+'
        else:
            sig_type = sig_name
        sig_type_groups[sig_type].append(s['handshake_ms'])
    
    print(f"\n{'SIG Type':<15} {'Avg(ms)':>10} {'Min(ms)':>10} {'Max(ms)':>10} {'n':>5}")
    print("-" * 50)
    for fam in sorted(sig_type_groups.keys()):
        times = sig_type_groups[fam]
        avg = statistics.mean(times)
        mn = min(times)
        mx = max(times)
        print(f"{fam:<15} {avg:10.2f} {mn:10.2f} {mx:10.2f} {len(times):5d}")
    
    # =========================================================================
    # SECTION 4: BY AEAD CIPHER
    # =========================================================================
    print_header("4. HANDSHAKE BY AEAD CIPHER (72 SUITES)")
    
    aead_groups = defaultdict(list)
    for s in suites:
        aead_groups[s['aead']].append(s['handshake_ms'])
    
    print(f"\n{'AEAD':<22} {'Avg(ms)':>10} {'Min(ms)':>10} {'Max(ms)':>10} {'n':>5}")
    print("-" * 60)
    for aead in sorted(aead_groups.keys()):
        times = aead_groups[aead]
        avg = statistics.mean(times)
        mn = min(times)
        mx = max(times)
        print(f"{aead:<22} {avg:10.2f} {mn:10.2f} {mx:10.2f} {len(times):5d}")
    
    # =========================================================================
    # SECTION 5: BY NIST LEVEL
    # =========================================================================
    print_header("5. HANDSHAKE BY NIST SECURITY LEVEL (72 SUITES)")
    
    level_groups = defaultdict(list)
    for s in suites:
        level_groups[s['nist_level']].append(s['handshake_ms'])
    
    print(f"\n{'Level':<10} {'Avg(ms)':>10} {'Min(ms)':>10} {'Max(ms)':>10} {'n':>5}")
    print("-" * 50)
    for level in sorted(level_groups.keys()):
        times = level_groups[level]
        avg = statistics.mean(times)
        mn = min(times)
        mx = max(times)
        print(f"{level:<10} {avg:10.2f} {mn:10.2f} {mx:10.2f} {len(times):5d}")
    
    # =========================================================================
    # SECTION 6: TOP/BOTTOM PERFORMERS
    # =========================================================================
    print_header("6. TOP 10 FASTEST & SLOWEST")
    
    print("\n[TOP 10 FASTEST]")
    for i, s in enumerate(sorted_suites[:10], 1):
        print(f"  {i:2d}. {s['suite_id']:<55} {s['handshake_ms']:8.2f}ms")
    
    print("\n[TOP 10 SLOWEST]")
    for i, s in enumerate(sorted_suites[-10:][::-1], 1):
        print(f"  {i:2d}. {s['suite_id']:<55} {s['handshake_ms']:8.2f}ms")
    
    # =========================================================================
    # SECTION 7: CRYPTO PRIMITIVE SIZES
    # =========================================================================
    print_header("7. CRYPTO PRIMITIVE SIZES")
    
    print("\n[Public Key Sizes by KEM]")
    pk_by_kem = defaultdict(set)
    for s in suites:
        pk_by_kem[s['kem_name']].add(s['pub_key_size_bytes'])
    
    for kem in sorted(pk_by_kem.keys()):
        sizes = pk_by_kem[kem]
        print(f"  {kem:<30}: {sorted(sizes)} bytes")
    
    print("\n[Ciphertext Sizes by KEM]")
    ct_by_kem = defaultdict(set)
    for s in suites:
        ct_by_kem[s['kem_name']].add(s['ciphertext_size_bytes'])
    
    for kem in sorted(ct_by_kem.keys()):
        sizes = ct_by_kem[kem]
        print(f"  {kem:<30}: {sorted(sizes)} bytes")
    
    print("\n[Signature Sizes by SIG]")
    sig_by_sig = defaultdict(set)
    for s in suites:
        sig_by_sig[s['sig_name']].add(s['sig_size_bytes'])
    
    for sig in sorted(sig_by_sig.keys()):
        sizes = sig_by_sig[sig]
        print(f"  {sig:<25}: {sorted(sizes)} bytes")
    
    # =========================================================================
    # SECTION 8: CROSS-DIMENSIONAL MATRIX
    # =========================================================================
    print_header("8. KEM × SIG HANDSHAKE MATRIX (avg ms)")
    
    kem_types = sorted(set(
        'McEliece' if 'McEliece' in s['kem_name'] else
        'HQC' if 'HQC' in s['kem_name'] else
        'ML-KEM' for s in suites
    ))
    sig_types = sorted(set(
        'Falcon' if 'Falcon' in s['sig_name'] else
        'ML-DSA' if 'ML-DSA' in s['sig_name'] else
        'SPHINCS+' for s in suites
    ))
    
    matrix = defaultdict(lambda: defaultdict(list))
    for s in suites:
        kem = 'McEliece' if 'McEliece' in s['kem_name'] else 'HQC' if 'HQC' in s['kem_name'] else 'ML-KEM'
        sig = 'Falcon' if 'Falcon' in s['sig_name'] else 'ML-DSA' if 'ML-DSA' in s['sig_name'] else 'SPHINCS+'
        matrix[kem][sig].append(s['handshake_ms'])
    
    print(f"\n{'':12}" + "".join(f"{s:>12}" for s in sig_types))
    for kem in kem_types:
        row = f"{kem:12}"
        for sig in sig_types:
            times = matrix[kem][sig]
            if times:
                avg = statistics.mean(times)
                row += f"{avg:12.1f}"
            else:
                row += "        -   "
        print(row)
    
    # =========================================================================
    # SECTION 9: VALIDATION SUMMARY
    # =========================================================================
    print_header("9. VALIDATION SUMMARY")
    
    success_count = sum(1 for s in suites if s['success'])
    fail_count = sum(1 for s in suites if not s['success'])
    
    print(f"\n  Total Suites: {len(suites)}")
    print(f"  Success: {success_count}")
    print(f"  Fail: {fail_count}")
    
    if fail_count > 0:
        print(f"\n  Error Messages:")
        errors = defaultdict(int)
        for s in suites:
            if not s['success']:
                errors[s['error_message']] += 1
        for err, count in errors.items():
            print(f"    - {err}: {count}")
    
    # =========================================================================
    # SECTION 10: COMPREHENSIVE METRICS SUMMARY (from detailed files)
    # =========================================================================
    print_header("10. COMPREHENSIVE METRICS SUMMARY (from 45 detailed files)")
    
    if comp_data:
        # Power/Energy
        power_vals = []
        energy_vals = []
        temp_vals = []
        cpu_vals = []
        
        for suite_id, d in comp_data.items():
            pwr = d.get('power_energy', {}).get('power_avg_w')
            if pwr:
                power_vals.append(pwr)
            energy = d.get('power_energy', {}).get('energy_total_j')
            if energy:
                energy_vals.append(energy)
            temp = d.get('system_drone', {}).get('temperature_c')
            if temp:
                temp_vals.append(temp)
            cpu = d.get('system_drone', {}).get('cpu_usage_avg_percent')
            if cpu:
                cpu_vals.append(cpu)
        
        print(f"\n  [Power & Energy]")
        print(f"    Avg Power: {statistics.mean(power_vals):.3f} W")
        print(f"    Total Energy: {sum(energy_vals):.2f} J ({sum(energy_vals)/3600:.4f} Wh)")
        
        print(f"\n  [System Metrics]")
        print(f"    Avg CPU: {statistics.mean(cpu_vals):.1f}%")
        print(f"    Avg Temp: {statistics.mean(temp_vals):.1f}°C")
        print(f"    Max Temp: {max(temp_vals):.1f}°C")
        
        # MAVLink
        hb_losses = []
        mav_msgs = []
        for suite_id, d in comp_data.items():
            loss = d.get('mavproxy_drone', {}).get('mavproxy_drone_heartbeat_loss_count')
            if loss is not None:
                hb_losses.append(loss)
            msgs = d.get('mavproxy_drone', {}).get('mavproxy_drone_total_msgs_received')
            if msgs:
                mav_msgs.append(msgs)
        
        print(f"\n  [MAVLink Telemetry]")
        print(f"    Total Heartbeat Losses: {sum(hb_losses)}")
        print(f"    Avg MAVLink msgs/suite: {statistics.mean(mav_msgs):.0f}")
        print(f"    Total MAVLink msgs: {sum(mav_msgs):,}")
    
    # =========================================================================
    # SECTION 11: FINAL SUMMARY
    # =========================================================================
    print_header("11. FINAL RUN SUMMARY")
    
    # Filter out 0ms (timeout failures) for fastest/slowest
    valid_suites = [s for s in sorted_suites if s['handshake_ms'] > 0]
    fastest = valid_suites[0] if valid_suites else sorted_suites[0]
    slowest = valid_suites[-1] if valid_suites else sorted_suites[-1]
    
    # Safe speed ratio
    speed_ratio = slowest['handshake_ms'] / fastest['handshake_ms'] if fastest['handshake_ms'] > 0 else 0
    
    print(f"""
  Run ID: live_run_20260205_145749
  Start:  2026-02-05 14:57:49 UTC
  End:    2026-02-05 17:10:30 UTC
  Duration: ~132 minutes

  SUITES TESTED: {len(suites)}
  COMPLETED WITH DATA: {len(valid_suites)}
  
  FASTEST: {fastest['suite_id']}
           {fastest['handshake_ms']:.2f}ms
           
  SLOWEST: {slowest['suite_id']}
           {slowest['handshake_ms']:.2f}ms
           
  SPEED RATIO: {speed_ratio:.1f}x

  HANDSHAKE STATISTICS (valid handshakes only):
    Mean:   {statistics.mean([s['handshake_ms'] for s in valid_suites]):.2f}ms
    Median: {statistics.median([s['handshake_ms'] for s in valid_suites]):.2f}ms
    StdDev: {statistics.stdev([s['handshake_ms'] for s in valid_suites]):.2f}ms
    Min:    {min([s['handshake_ms'] for s in valid_suites]):.2f}ms
    Max:    {max([s['handshake_ms'] for s in valid_suites]):.2f}ms

  RECOMMENDATIONS BY USE CASE:
  
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │ Latency-Critical (Real-time UAV control)                                    │
  │   → ML-KEM-512/768/1024 + ML-DSA-44/65/87                                   │
  │   → 9-28ms handshakes                                                       │
  │   → NIST L1/L3/L5 security                                                  │
  ├─────────────────────────────────────────────────────────────────────────────┤
  │ Balanced (General UAV operations)                                           │
  │   → HQC-128/192/256 + Falcon-512/1024 or ML-DSA                             │
  │   → 60-280ms handshakes                                                     │
  │   → Good security-performance tradeoff                                      │
  ├─────────────────────────────────────────────────────────────────────────────┤
  │ Security-First (High-value missions)                                        │
  │   → Classic-McEliece + SPHINCS+                                             │
  │   → 600-2800ms handshakes                                                   │
  │   → Maximum post-quantum security                                           │
  └─────────────────────────────────────────────────────────────────────────────┘
""")
    
    print("=" * 80)
    print(" ANALYSIS COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
