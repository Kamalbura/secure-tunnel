#!/usr/bin/env python3
"""
AGGRESSIVE ANALYSIS - Complete 72-Suite PQC Benchmark Run
Run ID: live_run_20260205_145749
Date: 2026-02-05
"""
import json
import os
import csv
from pathlib import Path
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import statistics

# Paths
RUN_DIR = Path(__file__).parent
COMPREHENSIVE_DIR = RUN_DIR / "comprehensive"
RESULTS_JSON = RUN_DIR / "benchmark_results_20260205_145749.json"
RESULTS_CSV = RUN_DIR / "benchmark_results_20260205_145749.csv"
SUMMARY_JSON = RUN_DIR / "benchmark_summary_20260205_145749.json"


def load_all_comprehensive_files() -> List[dict]:
    """Load all comprehensive metric files."""
    suites = []
    for f in sorted(COMPREHENSIVE_DIR.glob("*.json")):
        try:
            with open(f) as fp:
                d = json.load(fp)
                suites.append(d)
        except Exception as e:
            print(f"ERROR loading {f.name}: {e}")
    return suites


def safe_get(d: dict, *keys, default=None):
    """Safely get nested dictionary values."""
    for key in keys:
        if isinstance(d, dict) and key in d:
            d = d[key]
        else:
            return default
    return d


def extract_metrics(d: dict) -> dict:
    """Extract key metrics from comprehensive file."""
    return {
        # Identity
        'suite': safe_get(d, 'run_context', 'suite_id', default='unknown'),
        'suite_index': safe_get(d, 'run_context', 'suite_index', default=-1),
        
        # Crypto Identity
        'kem': safe_get(d, 'crypto_identity', 'kem_algorithm', default=''),
        'kem_family': safe_get(d, 'crypto_identity', 'kem_family', default=''),
        'sig': safe_get(d, 'crypto_identity', 'sig_algorithm', default=''),
        'sig_family': safe_get(d, 'crypto_identity', 'sig_family', default=''),
        'aead': safe_get(d, 'crypto_identity', 'aead_algorithm', default=''),
        'nist_level': safe_get(d, 'crypto_identity', 'suite_security_level', default=''),
        
        # Handshake
        'handshake_ms': safe_get(d, 'handshake', 'protocol_handshake_duration_ms'),
        'e2e_handshake_ms': safe_get(d, 'handshake', 'end_to_end_handshake_duration_ms'),
        'handshake_success': safe_get(d, 'handshake', 'handshake_success', default=False),
        'handshake_failure': safe_get(d, 'handshake', 'handshake_failure_reason', default=''),
        
        # Crypto Primitives
        'kem_encaps_ms': safe_get(d, 'crypto_primitives', 'kem_encapsulation_time_ms'),
        'sig_verify_ms': safe_get(d, 'crypto_primitives', 'signature_verify_time_ms'),
        'pub_key_bytes': safe_get(d, 'crypto_primitives', 'pub_key_size_bytes'),
        'ciphertext_bytes': safe_get(d, 'crypto_primitives', 'ciphertext_size_bytes'),
        'sig_bytes': safe_get(d, 'crypto_primitives', 'sig_size_bytes'),
        
        # Data Plane
        'ptx_in': safe_get(d, 'data_plane', 'ptx_in'),
        'ptx_out': safe_get(d, 'data_plane', 'ptx_out'),
        'throughput_mbps': safe_get(d, 'data_plane', 'achieved_throughput_mbps'),
        'packet_loss': safe_get(d, 'data_plane', 'packet_loss_ratio', default=0.0),
        'aead_enc_ns': safe_get(d, 'data_plane', 'aead_encrypt_avg_ns'),
        'aead_dec_ns': safe_get(d, 'data_plane', 'aead_decrypt_avg_ns'),
        
        # MAVLink
        'mav_msgs_rx': safe_get(d, 'mavproxy_drone', 'mavproxy_drone_total_msgs_received'),
        'heartbeat_ms': safe_get(d, 'mavproxy_drone', 'mavproxy_drone_heartbeat_interval_ms'),
        'heartbeat_loss': safe_get(d, 'mavproxy_drone', 'mavproxy_drone_heartbeat_loss_count'),
        'mav_stream_hz': safe_get(d, 'mavproxy_drone', 'mavproxy_drone_stream_rate_hz'),
        'seq_gaps': safe_get(d, 'mavproxy_drone', 'mavproxy_drone_seq_gap_count'),
        
        # FC Telemetry
        'fc_mode': safe_get(d, 'fc_telemetry', 'fc_mode', default=''),
        'battery_v': safe_get(d, 'fc_telemetry', 'fc_battery_voltage_v'),
        'fc_cpu_load': safe_get(d, 'fc_telemetry', 'fc_cpu_load_percent'),
        
        # System Drone
        'cpu_avg': safe_get(d, 'system_drone', 'cpu_usage_avg_percent'),
        'cpu_peak': safe_get(d, 'system_drone', 'cpu_usage_peak_percent'),
        'temp_c': safe_get(d, 'system_drone', 'temperature_c'),
        'memory_mb': safe_get(d, 'system_drone', 'memory_rss_mb'),
        'load_1m': safe_get(d, 'system_drone', 'load_avg_1m'),
        
        # Power/Energy
        'power_w': safe_get(d, 'power_energy', 'power_avg_w'),
        'power_peak_w': safe_get(d, 'power_energy', 'power_peak_w'),
        'energy_j': safe_get(d, 'power_energy', 'energy_total_j'),
        'energy_per_hs_j': safe_get(d, 'power_energy', 'energy_per_handshake_j'),
        'voltage_v': safe_get(d, 'power_energy', 'voltage_avg_v'),
        'current_a': safe_get(d, 'power_energy', 'current_avg_a'),
        
        # Lifecycle
        'duration_ms': safe_get(d, 'lifecycle', 'suite_active_duration_ms'),
        
        # Validation
        'pass_fail': safe_get(d, 'validation', 'benchmark_pass_fail', default='UNKNOWN'),
    }


def group_by(metrics: List[dict], key: str) -> Dict[str, List[dict]]:
    """Group metrics by a given key."""
    groups = defaultdict(list)
    for m in metrics:
        groups[m[key]].append(m)
    return dict(groups)


def calc_stats(values: List[float]) -> Tuple[float, float, float, float, float]:
    """Calculate avg, min, max, stdev, median."""
    if not values:
        return (0, 0, 0, 0, 0)
    avg = statistics.mean(values)
    mn = min(values)
    mx = max(values)
    std = statistics.stdev(values) if len(values) > 1 else 0
    med = statistics.median(values)
    return (avg, mn, mx, std, med)


def print_header(title: str):
    """Print section header."""
    print()
    print("=" * 80)
    print(f" {title}")
    print("=" * 80)


def main():
    print("=" * 80)
    print(" AGGRESSIVE ANALYSIS - PQC Benchmark Run")
    print(" Run ID: live_run_20260205_145749")
    print(" Date: 2026-02-05 14:57:49 - 17:10:30 UTC")
    print("=" * 80)
    
    # Load data
    raw_data = load_all_comprehensive_files()
    print(f"\nLoaded {len(raw_data)} comprehensive metric files")
    
    # Extract metrics
    metrics = [extract_metrics(d) for d in raw_data]
    
    # Deduplicate (some files may be duplicated with different naming)
    seen = set()
    unique_metrics = []
    for m in metrics:
        key = m['suite']
        if key not in seen:
            seen.add(key)
            unique_metrics.append(m)
    
    metrics = unique_metrics
    print(f"Unique suites: {len(metrics)}")
    
    # =========================================================================
    # SECTION 1: HANDSHAKE ANALYSIS
    # =========================================================================
    print_header("1. HANDSHAKE PERFORMANCE ANALYSIS")
    
    # By KEM Family
    print("\n[1.1] HANDSHAKE BY KEM FAMILY")
    print("-" * 70)
    kem_groups = group_by(metrics, 'kem_family')
    for fam in sorted(kem_groups.keys()):
        hs_times = [m['handshake_ms'] for m in kem_groups[fam] if m['handshake_ms']]
        if hs_times:
            avg, mn, mx, std, med = calc_stats(hs_times)
            print(f"  {fam:20s}: avg={avg:8.2f}ms  min={mn:8.2f}ms  max={mx:8.2f}ms  σ={std:7.2f}  med={med:8.2f}ms  (n={len(hs_times)})")
    
    # By Signature Family
    print("\n[1.2] HANDSHAKE BY SIGNATURE FAMILY")
    print("-" * 70)
    sig_groups = group_by(metrics, 'sig_family')
    for fam in sorted(sig_groups.keys()):
        hs_times = [m['handshake_ms'] for m in sig_groups[fam] if m['handshake_ms']]
        if hs_times:
            avg, mn, mx, std, med = calc_stats(hs_times)
            print(f"  {fam:20s}: avg={avg:8.2f}ms  min={mn:8.2f}ms  max={mx:8.2f}ms  σ={std:7.2f}  med={med:8.2f}ms  (n={len(hs_times)})")
    
    # By AEAD
    print("\n[1.3] HANDSHAKE BY AEAD CIPHER")
    print("-" * 70)
    aead_groups = group_by(metrics, 'aead')
    for aead in sorted(aead_groups.keys()):
        hs_times = [m['handshake_ms'] for m in aead_groups[aead] if m['handshake_ms']]
        if hs_times:
            avg, mn, mx, std, med = calc_stats(hs_times)
            print(f"  {aead:22s}: avg={avg:8.2f}ms  σ={std:7.2f}  (n={len(hs_times)})")
    
    # By NIST Level
    print("\n[1.4] HANDSHAKE BY NIST SECURITY LEVEL")
    print("-" * 70)
    level_groups = group_by(metrics, 'nist_level')
    for level in sorted(level_groups.keys()):
        hs_times = [m['handshake_ms'] for m in level_groups[level] if m['handshake_ms']]
        if hs_times:
            avg, mn, mx, std, med = calc_stats(hs_times)
            print(f"  {level:5s}: avg={avg:8.2f}ms  min={mn:8.2f}ms  max={mx:8.2f}ms  σ={std:7.2f}  (n={len(hs_times)})")
    
    # Top 10 Fastest
    print("\n[1.5] TOP 10 FASTEST HANDSHAKES")
    print("-" * 70)
    sorted_by_hs = sorted([m for m in metrics if m['handshake_ms']], key=lambda x: x['handshake_ms'])
    for i, m in enumerate(sorted_by_hs[:10], 1):
        print(f"  {i:2d}. {m['suite']:55s} {m['handshake_ms']:8.2f}ms")
    
    # Top 10 Slowest
    print("\n[1.6] TOP 10 SLOWEST HANDSHAKES")
    print("-" * 70)
    for i, m in enumerate(sorted_by_hs[-10:][::-1], 1):
        print(f"  {i:2d}. {m['suite']:55s} {m['handshake_ms']:8.2f}ms")
    
    # =========================================================================
    # SECTION 2: POWER & ENERGY ANALYSIS
    # =========================================================================
    print_header("2. POWER & ENERGY ANALYSIS")
    
    # By KEM Family
    print("\n[2.1] POWER BY KEM FAMILY")
    print("-" * 70)
    for fam in sorted(kem_groups.keys()):
        power_vals = [m['power_w'] for m in kem_groups[fam] if m['power_w']]
        energy_vals = [m['energy_per_hs_j'] for m in kem_groups[fam] if m['energy_per_hs_j']]
        if power_vals:
            p_avg = statistics.mean(power_vals)
            e_avg = statistics.mean(energy_vals) if energy_vals else 0
            print(f"  {fam:20s}: power_avg={p_avg:.3f}W  energy_per_hs={e_avg:.3f}J")
    
    # Total Energy
    print("\n[2.2] TOTAL ENERGY CONSUMPTION")
    print("-" * 70)
    total_energy = sum(m['energy_j'] for m in metrics if m['energy_j'])
    avg_power = statistics.mean([m['power_w'] for m in metrics if m['power_w']])
    peak_power = max([m['power_peak_w'] for m in metrics if m['power_peak_w']])
    print(f"  Total energy: {total_energy:.2f} J ({total_energy/3600:.4f} Wh)")
    print(f"  Avg power draw: {avg_power:.3f} W")
    print(f"  Peak power: {peak_power:.3f} W")
    
    # Energy vs Handshake Correlation
    print("\n[2.3] ENERGY EFFICIENCY (Energy per ms of handshake)")
    print("-" * 70)
    for fam in sorted(kem_groups.keys()):
        hs_times = [m['handshake_ms'] for m in kem_groups[fam] if m['handshake_ms']]
        energy_vals = [m['energy_per_hs_j'] for m in kem_groups[fam] if m['energy_per_hs_j']]
        if hs_times and energy_vals:
            avg_hs = statistics.mean(hs_times)
            avg_e = statistics.mean(energy_vals)
            eff = avg_e / avg_hs * 1000 if avg_hs > 0 else 0
            print(f"  {fam:20s}: {eff:.4f} mJ/ms")
    
    # =========================================================================
    # SECTION 3: CPU & TEMPERATURE ANALYSIS
    # =========================================================================
    print_header("3. CPU & TEMPERATURE ANALYSIS")
    
    print("\n[3.1] CPU USAGE BY KEM FAMILY")
    print("-" * 70)
    for fam in sorted(kem_groups.keys()):
        cpu_vals = [m['cpu_avg'] for m in kem_groups[fam] if m['cpu_avg']]
        peak_vals = [m['cpu_peak'] for m in kem_groups[fam] if m['cpu_peak']]
        if cpu_vals:
            avg = statistics.mean(cpu_vals)
            peak = max(peak_vals) if peak_vals else 0
            print(f"  {fam:20s}: cpu_avg={avg:.1f}%  cpu_peak={peak:.1f}%")
    
    print("\n[3.2] TEMPERATURE BY KEM FAMILY")
    print("-" * 70)
    for fam in sorted(kem_groups.keys()):
        temp_vals = [m['temp_c'] for m in kem_groups[fam] if m['temp_c']]
        if temp_vals:
            avg, mn, mx, std, med = calc_stats(temp_vals)
            print(f"  {fam:20s}: avg={avg:.1f}°C  min={mn:.1f}°C  max={mx:.1f}°C")
    
    # =========================================================================
    # SECTION 4: MAVLINK TELEMETRY ANALYSIS
    # =========================================================================
    print_header("4. MAVLINK TELEMETRY ANALYSIS")
    
    print("\n[4.1] HEARTBEAT HEALTH")
    print("-" * 70)
    total_hb_loss = sum(m['heartbeat_loss'] for m in metrics if m['heartbeat_loss'])
    hb_intervals = [m['heartbeat_ms'] for m in metrics if m['heartbeat_ms']]
    avg_hb = statistics.mean(hb_intervals) if hb_intervals else 0
    print(f"  Total heartbeat losses: {total_hb_loss}")
    print(f"  Avg heartbeat interval: {avg_hb:.2f}ms (target: 1000ms)")
    print(f"  Heartbeat deviation: {abs(avg_hb - 1000):.2f}ms")
    
    print("\n[4.2] MAVLINK MESSAGE RATES")
    print("-" * 70)
    mav_msgs = [m['mav_msgs_rx'] for m in metrics if m['mav_msgs_rx']]
    stream_rates = [m['mav_stream_hz'] for m in metrics if m['mav_stream_hz']]
    print(f"  Avg MAVLink msgs/suite: {statistics.mean(mav_msgs):.0f}")
    print(f"  Total MAVLink msgs: {sum(mav_msgs):,}")
    print(f"  Avg stream rate: {statistics.mean(stream_rates):.1f} Hz")
    
    print("\n[4.3] SEQUENCE GAPS (potential packet loss)")
    print("-" * 70)
    seq_gaps = [m['seq_gaps'] for m in metrics if m['seq_gaps']]
    total_gaps = sum(seq_gaps)
    avg_gaps = statistics.mean(seq_gaps) if seq_gaps else 0
    print(f"  Total sequence gaps: {total_gaps}")
    print(f"  Avg gaps/suite: {avg_gaps:.1f}")
    
    # =========================================================================
    # SECTION 5: DATA PLANE ANALYSIS
    # =========================================================================
    print_header("5. DATA PLANE ANALYSIS")
    
    print("\n[5.1] PACKET COUNTS")
    print("-" * 70)
    total_ptx_in = sum(m['ptx_in'] for m in metrics if m['ptx_in'])
    total_ptx_out = sum(m['ptx_out'] for m in metrics if m['ptx_out'])
    print(f"  Total packets IN (from FC): {total_ptx_in:,}")
    print(f"  Total packets OUT (to GCS): {total_ptx_out:,}")
    print(f"  Ratio OUT/IN: {total_ptx_out/total_ptx_in:.4f}" if total_ptx_in > 0 else "  Ratio: N/A")
    
    print("\n[5.2] THROUGHPUT")
    print("-" * 70)
    throughput_vals = [m['throughput_mbps'] for m in metrics if m['throughput_mbps']]
    avg_tp = statistics.mean(throughput_vals) if throughput_vals else 0
    print(f"  Avg throughput: {avg_tp:.4f} Mbps")
    
    print("\n[5.3] AEAD PERFORMANCE")
    print("-" * 70)
    for aead in sorted(aead_groups.keys()):
        enc_vals = [m['aead_enc_ns'] for m in aead_groups[aead] if m['aead_enc_ns']]
        dec_vals = [m['aead_dec_ns'] for m in aead_groups[aead] if m['aead_dec_ns']]
        if enc_vals:
            avg_enc = statistics.mean(enc_vals)
            avg_dec = statistics.mean(dec_vals) if dec_vals else 0
            print(f"  {aead:22s}: enc_avg={avg_enc/1000:.2f}µs  dec_avg={avg_dec/1000:.2f}µs")
    
    # =========================================================================
    # SECTION 6: CRYPTO PRIMITIVE SIZES
    # =========================================================================
    print_header("6. CRYPTO PRIMITIVE SIZES")
    
    print("\n[6.1] KEY SIZES BY KEM")
    print("-" * 70)
    for fam in sorted(kem_groups.keys()):
        pk_vals = [m['pub_key_bytes'] for m in kem_groups[fam] if m['pub_key_bytes']]
        ct_vals = [m['ciphertext_bytes'] for m in kem_groups[fam] if m['ciphertext_bytes']]
        if pk_vals:
            pk_sizes = set(pk_vals)
            ct_sizes = set(ct_vals)
            print(f"  {fam:20s}: pub_key={pk_sizes}  ciphertext={ct_sizes}")
    
    print("\n[6.2] SIGNATURE SIZES BY SIG")
    print("-" * 70)
    for fam in sorted(sig_groups.keys()):
        sig_vals = [m['sig_bytes'] for m in sig_groups[fam] if m['sig_bytes']]
        if sig_vals:
            sig_sizes = set(sig_vals)
            print(f"  {fam:20s}: sig_size={sig_sizes}")
    
    # =========================================================================
    # SECTION 7: VALIDATION SUMMARY
    # =========================================================================
    print_header("7. VALIDATION SUMMARY")
    
    pass_count = sum(1 for m in metrics if m['pass_fail'] == 'PASS')
    fail_count = sum(1 for m in metrics if m['pass_fail'] == 'FAIL')
    success_count = sum(1 for m in metrics if m['handshake_success'])
    
    print(f"\n  Handshake Success: {success_count}/{len(metrics)}")
    print(f"  Benchmark PASS: {pass_count}")
    print(f"  Benchmark FAIL: {fail_count}")
    print(f"  Total Suites: {len(metrics)}")
    
    # List failures
    failures = [m for m in metrics if not m['handshake_success']]
    if failures:
        print("\n  Failed Handshakes:")
        for m in failures:
            print(f"    - {m['suite']}: {m['handshake_failure']}")
    
    # =========================================================================
    # SECTION 8: CROSS-DIMENSIONAL ANALYSIS
    # =========================================================================
    print_header("8. CROSS-DIMENSIONAL ANALYSIS")
    
    print("\n[8.1] KEM × SIG HANDSHAKE MATRIX (avg ms)")
    print("-" * 70)
    
    # Build matrix
    kem_families = sorted(set(m['kem_family'] for m in metrics))
    sig_families = sorted(set(m['sig_family'] for m in metrics))
    
    # Header
    header = "          " + "".join(f"{s:12s}" for s in sig_families)
    print(header)
    
    for kem in kem_families:
        row = f"{kem:10s}"
        for sig in sig_families:
            hs_times = [m['handshake_ms'] for m in metrics 
                       if m['kem_family'] == kem and m['sig_family'] == sig and m['handshake_ms']]
            if hs_times:
                avg = statistics.mean(hs_times)
                row += f"{avg:12.1f}"
            else:
                row += "       -    "
        print(row)
    
    print("\n[8.2] AEAD × NIST LEVEL HANDSHAKE MATRIX (avg ms)")
    print("-" * 70)
    aeads = sorted(set(m['aead'] for m in metrics))
    levels = sorted(set(m['nist_level'] for m in metrics))
    
    header = "                      " + "".join(f"{l:10s}" for l in levels)
    print(header)
    
    for aead in aeads:
        row = f"{aead:22s}"
        for level in levels:
            hs_times = [m['handshake_ms'] for m in metrics 
                       if m['aead'] == aead and m['nist_level'] == level and m['handshake_ms']]
            if hs_times:
                avg = statistics.mean(hs_times)
                row += f"{avg:10.1f}"
            else:
                row += "     -    "
        print(row)
    
    # =========================================================================
    # SECTION 9: COMPLETE SUITE TABLE
    # =========================================================================
    print_header("9. COMPLETE SUITE TABLE (sorted by handshake time)")
    print("-" * 100)
    print(f"{'#':>3} {'Suite':<50} {'HS(ms)':>10} {'Power(W)':>10} {'CPU(%)':>8} {'Temp(C)':>8}")
    print("-" * 100)
    
    for i, m in enumerate(sorted_by_hs, 1):
        suite = m['suite'][:48]
        hs = m['handshake_ms'] or 0
        pwr = m['power_w'] or 0
        cpu = m['cpu_avg'] or 0
        temp = m['temp_c'] or 0
        print(f"{i:3d} {suite:<50} {hs:10.2f} {pwr:10.3f} {cpu:8.1f} {temp:8.1f}")
    
    # =========================================================================
    # SECTION 10: RUN SUMMARY
    # =========================================================================
    print_header("10. RUN SUMMARY")
    
    # Calculate total run time
    durations = [m['duration_ms'] for m in metrics if m['duration_ms']]
    total_run_time_ms = sum(durations)
    total_run_time_min = total_run_time_ms / 60000
    
    print(f"""
  Run ID: live_run_20260205_145749
  Start:  2026-02-05 14:57:49 UTC
  End:    2026-02-05 17:10:30 UTC
  
  Total Suites Tested: {len(metrics)}
  Successful Handshakes: {success_count}
  Failed Handshakes: {len(metrics) - success_count}
  
  Total Active Time: {total_run_time_min:.1f} minutes
  Total Packets Processed: {total_ptx_in:,}
  Total Energy: {total_energy:.1f} J ({total_energy/3600:.3f} Wh)
  
  FASTEST: {sorted_by_hs[0]['suite']} @ {sorted_by_hs[0]['handshake_ms']:.2f}ms
  SLOWEST: {sorted_by_hs[-1]['suite']} @ {sorted_by_hs[-1]['handshake_ms']:.2f}ms
  SPEED RATIO: {sorted_by_hs[-1]['handshake_ms'] / sorted_by_hs[0]['handshake_ms']:.1f}x
  
  RECOMMENDATIONS:
  - For latency-critical applications: ML-KEM + ML-DSA (9-17ms)
  - For security-first applications: Classic-McEliece + SPHINCS+ (2000-2800ms)
  - Balanced: HQC + Falcon (200-500ms)
""")
    
    print("=" * 80)
    print(" ANALYSIS COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
