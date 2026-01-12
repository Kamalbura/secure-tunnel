#!/usr/bin/env python3
"""
Comprehensive PQC Benchmark Data Analysis
Expert Data Analyst Report Generator

Analyzes benchmark_results JSON files with statistical rigor.
"""

import json
import os
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple
import statistics
import math

@dataclass
class SuiteMetrics:
    """Metrics for a single cipher suite."""
    suite_id: str
    kem_name: str
    sig_name: str
    aead: str
    nist_level: int
    handshake_ms: float
    throughput_mbps: float
    latency_ms: float
    power_w: float
    energy_mj: float
    kem_keygen_ms: float
    kem_encaps_ms: float
    kem_decaps_ms: float
    sig_sign_ms: float
    sig_verify_ms: float
    pub_key_size_bytes: int
    ciphertext_size_bytes: int
    sig_size_bytes: int
    success: bool
    error_message: str = ""

@dataclass
class StatsSummary:
    """Statistical summary for a metric."""
    count: int
    min_val: float
    max_val: float
    mean: float
    median: float
    stddev: float
    p25: float
    p75: float
    p95: float
    p99: float
    iqr: float
    cv: float  # coefficient of variation

def compute_stats(values: List[float]) -> Optional[StatsSummary]:
    """Compute comprehensive statistics for a list of values."""
    if not values or len(values) < 2:
        return None
    
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    
    mean = statistics.mean(values)
    median = statistics.median(values)
    stddev = statistics.stdev(values)
    
    # Percentiles
    def percentile(data, p):
        k = (len(data) - 1) * p / 100
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return data[int(k)]
        return data[f] * (c - k) + data[c] * (k - f)
    
    p25 = percentile(sorted_vals, 25)
    p75 = percentile(sorted_vals, 75)
    p95 = percentile(sorted_vals, 95)
    p99 = percentile(sorted_vals, 99)
    
    return StatsSummary(
        count=n,
        min_val=min(values),
        max_val=max(values),
        mean=mean,
        median=median,
        stddev=stddev,
        p25=p25,
        p75=p75,
        p95=p95,
        p99=p99,
        iqr=p75 - p25,
        cv=stddev / mean if mean > 0 else 0
    )

class BenchmarkAnalyzer:
    """Expert-level benchmark data analyzer."""
    
    def __init__(self, filepath: str):
        self.filepath = Path(filepath)
        self.data = self._load_data()
        self.suites: List[SuiteMetrics] = self._parse_suites()
        
    def _load_data(self) -> Dict:
        """Load benchmark JSON file."""
        with open(self.filepath) as f:
            return json.load(f)
    
    def _parse_suites(self) -> List[SuiteMetrics]:
        """Parse suite data into SuiteMetrics objects."""
        suites_raw = self.data.get('suites', [])
        suites = []
        
        for s in suites_raw:
            if s.get('success', False):
                try:
                    suites.append(SuiteMetrics(
                        suite_id=s.get('suite_id', ''),
                        kem_name=s.get('kem_name', ''),
                        sig_name=s.get('sig_name', ''),
                        aead=s.get('aead', ''),
                        nist_level=s.get('nist_level', 0),
                        handshake_ms=float(s.get('handshake_ms', 0)),
                        throughput_mbps=float(s.get('throughput_mbps', 0)),
                        latency_ms=float(s.get('latency_ms', 0)),
                        power_w=float(s.get('power_w', 0)),
                        energy_mj=float(s.get('energy_mj', 0)),
                        kem_keygen_ms=float(s.get('kem_keygen_ms', 0)),
                        kem_encaps_ms=float(s.get('kem_encaps_ms', 0)),
                        kem_decaps_ms=float(s.get('kem_decaps_ms', 0)),
                        sig_sign_ms=float(s.get('sig_sign_ms', 0)),
                        sig_verify_ms=float(s.get('sig_verify_ms', 0)),
                        pub_key_size_bytes=int(s.get('pub_key_size_bytes', 0)),
                        ciphertext_size_bytes=int(s.get('ciphertext_size_bytes', 0)),
                        sig_size_bytes=int(s.get('sig_size_bytes', 0)),
                        success=True
                    ))
                except (ValueError, KeyError) as e:
                    print(f"Warning: Could not parse suite {s.get('suite_id', 'unknown')}: {e}")
        
        return suites
    
    def generate_report(self) -> str:
        """Generate comprehensive analysis report."""
        lines = []
        lines.append("=" * 80)
        lines.append("PQC BENCHMARK COMPREHENSIVE ANALYSIS REPORT")
        lines.append("Expert Data Analyst Assessment")
        lines.append("=" * 80)
        lines.append(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"Data File: {self.filepath.name}")
        lines.append(f"Run ID: {self.data.get('run_id', 'N/A')}")
        
        # Overview
        lines.append("\n" + "-" * 80)
        lines.append("1. DATASET OVERVIEW")
        lines.append("-" * 80)
        lines.append(f"  Total suites in file:     {self.data.get('total_suites', 0)}")
        lines.append(f"  Successful suites:        {len(self.suites)}")
        lines.append(f"  Success rate:             {len(self.suites) / max(1, self.data.get('total_suites', 1)) * 100:.1f}%")
        
        # Unique algorithms
        kems = set(s.kem_name for s in self.suites)
        sigs = set(s.sig_name for s in self.suites)
        aeads = set(s.aead for s in self.suites)
        levels = set(s.nist_level for s in self.suites)
        
        lines.append(f"\n  Unique KEM algorithms:    {len(kems)}")
        lines.append(f"  Unique Signature algs:    {len(sigs)}")
        lines.append(f"  Unique AEAD modes:        {len(aeads)}")
        lines.append(f"  NIST security levels:     {sorted(levels)}")
        
        # Handshake Performance
        lines.append("\n" + "-" * 80)
        lines.append("2. HANDSHAKE PERFORMANCE ANALYSIS")
        lines.append("-" * 80)
        
        handshake_vals = [s.handshake_ms for s in self.suites if s.handshake_ms > 0]
        hs_stats = compute_stats(handshake_vals)
        
        if hs_stats:
            lines.append(f"\n  Sample size:              {hs_stats.count}")
            lines.append(f"  Mean:                     {hs_stats.mean:.2f} ms")
            lines.append(f"  Median:                   {hs_stats.median:.2f} ms")
            lines.append(f"  Std Dev:                  {hs_stats.stddev:.2f} ms")
            lines.append(f"  Min:                      {hs_stats.min_val:.2f} ms")
            lines.append(f"  Max:                      {hs_stats.max_val:.2f} ms")
            lines.append(f"  P25:                      {hs_stats.p25:.2f} ms")
            lines.append(f"  P75:                      {hs_stats.p75:.2f} ms")
            lines.append(f"  P95:                      {hs_stats.p95:.2f} ms")
            lines.append(f"  P99:                      {hs_stats.p99:.2f} ms")
            lines.append(f"  IQR:                      {hs_stats.iqr:.2f} ms")
            lines.append(f"  CV:                       {hs_stats.cv:.2%}")
            
            # Top 5 fastest
            lines.append("\n  Top 5 Fastest Handshakes:")
            sorted_by_hs = sorted(self.suites, key=lambda x: x.handshake_ms if x.handshake_ms > 0 else float('inf'))
            for i, s in enumerate(sorted_by_hs[:5], 1):
                lines.append(f"    {i}. {s.suite_id[:50]:50} {s.handshake_ms:8.2f} ms")
            
            # Top 5 slowest
            lines.append("\n  Top 5 Slowest Handshakes:")
            for i, s in enumerate(sorted_by_hs[-5:][::-1], 1):
                lines.append(f"    {i}. {s.suite_id[:50]:50} {s.handshake_ms:8.2f} ms")
        
        # KEM Operations
        lines.append("\n" + "-" * 80)
        lines.append("3. KEM CRYPTO OPERATIONS ANALYSIS")
        lines.append("-" * 80)
        
        keygen_vals = [s.kem_keygen_ms for s in self.suites if s.kem_keygen_ms > 0]
        encaps_vals = [s.kem_encaps_ms for s in self.suites if s.kem_encaps_ms > 0]
        decaps_vals = [s.kem_decaps_ms for s in self.suites if s.kem_decaps_ms > 0]
        
        for name, vals in [("KeyGen", keygen_vals), ("Encapsulation", encaps_vals), ("Decapsulation", decaps_vals)]:
            stats = compute_stats(vals)
            if stats:
                lines.append(f"\n  {name}:")
                lines.append(f"    Mean: {stats.mean:.3f} ms | Median: {stats.median:.3f} ms | StdDev: {stats.stddev:.3f} ms")
                lines.append(f"    Range: [{stats.min_val:.3f}, {stats.max_val:.3f}] ms | P95: {stats.p95:.3f} ms")
        
        # Signature Operations
        lines.append("\n" + "-" * 80)
        lines.append("4. SIGNATURE OPERATIONS ANALYSIS")
        lines.append("-" * 80)
        
        sign_vals = [s.sig_sign_ms for s in self.suites if s.sig_sign_ms > 0]
        verify_vals = [s.sig_verify_ms for s in self.suites if s.sig_verify_ms > 0]
        
        for name, vals in [("Sign", sign_vals), ("Verify", verify_vals)]:
            stats = compute_stats(vals)
            if stats:
                lines.append(f"\n  {name}:")
                lines.append(f"    Mean: {stats.mean:.3f} ms | Median: {stats.median:.3f} ms | StdDev: {stats.stddev:.3f} ms")
                lines.append(f"    Range: [{stats.min_val:.3f}, {stats.max_val:.3f}] ms | P95: {stats.p95:.3f} ms")
        
        # Throughput Analysis
        lines.append("\n" + "-" * 80)
        lines.append("5. DATA PLANE THROUGHPUT ANALYSIS")
        lines.append("-" * 80)
        
        tp_vals = [s.throughput_mbps for s in self.suites if s.throughput_mbps > 0]
        tp_stats = compute_stats(tp_vals)
        
        if tp_stats:
            lines.append(f"\n  Sample size:              {tp_stats.count}")
            lines.append(f"  Mean:                     {tp_stats.mean:.2f} Mbps")
            lines.append(f"  Median:                   {tp_stats.median:.2f} Mbps")
            lines.append(f"  Std Dev:                  {tp_stats.stddev:.2f} Mbps")
            lines.append(f"  Min:                      {tp_stats.min_val:.2f} Mbps")
            lines.append(f"  Max:                      {tp_stats.max_val:.2f} Mbps")
            lines.append(f"  P95:                      {tp_stats.p95:.2f} Mbps")
        
        # Latency Analysis
        lines.append("\n" + "-" * 80)
        lines.append("6. NETWORK LATENCY ANALYSIS")
        lines.append("-" * 80)
        
        lat_vals = [s.latency_ms for s in self.suites if s.latency_ms > 0]
        lat_stats = compute_stats(lat_vals)
        
        if lat_stats:
            lines.append(f"\n  Mean:                     {lat_stats.mean:.2f} ms")
            lines.append(f"  Median:                   {lat_stats.median:.2f} ms")
            lines.append(f"  P95:                      {lat_stats.p95:.2f} ms")
            lines.append(f"  P99:                      {lat_stats.p99:.2f} ms")
        
        # Power & Energy
        lines.append("\n" + "-" * 80)
        lines.append("7. POWER & ENERGY ANALYSIS")
        lines.append("-" * 80)
        
        pwr_vals = [s.power_w for s in self.suites if s.power_w > 0]
        energy_vals = [s.energy_mj for s in self.suites if s.energy_mj > 0]
        
        pwr_stats = compute_stats(pwr_vals)
        if pwr_stats:
            lines.append(f"\n  Power (W):")
            lines.append(f"    Mean: {pwr_stats.mean:.3f} W | Range: [{pwr_stats.min_val:.3f}, {pwr_stats.max_val:.3f}] W")
        else:
            lines.append("\n  Power: No data available")
        
        energy_stats = compute_stats(energy_vals)
        if energy_stats:
            lines.append(f"\n  Energy per Handshake (mJ):")
            lines.append(f"    Mean: {energy_stats.mean:.3f} mJ | Range: [{energy_stats.min_val:.3f}, {energy_stats.max_val:.3f}] mJ")
        else:
            lines.append("\n  Energy: No data available")
        
        # Key/Ciphertext Sizes
        lines.append("\n" + "-" * 80)
        lines.append("8. CRYPTOGRAPHIC SIZES ANALYSIS")
        lines.append("-" * 80)
        
        pub_key_vals = [s.pub_key_size_bytes for s in self.suites if s.pub_key_size_bytes > 0]
        ct_vals = [s.ciphertext_size_bytes for s in self.suites if s.ciphertext_size_bytes > 0]
        sig_vals = [s.sig_size_bytes for s in self.suites if s.sig_size_bytes > 0]
        
        for name, vals in [("Public Key", pub_key_vals), ("Ciphertext", ct_vals), ("Signature", sig_vals)]:
            if vals:
                lines.append(f"\n  {name} Size (bytes):")
                lines.append(f"    Min: {min(vals):,} | Max: {max(vals):,} | Mean: {statistics.mean(vals):,.0f}")
        
        # Analysis by KEM Algorithm
        lines.append("\n" + "-" * 80)
        lines.append("9. ANALYSIS BY KEM ALGORITHM")
        lines.append("-" * 80)
        
        kem_groups = {}
        for s in self.suites:
            if s.kem_name not in kem_groups:
                kem_groups[s.kem_name] = []
            kem_groups[s.kem_name].append(s)
        
        kem_summary = []
        for kem, suites_list in sorted(kem_groups.items()):
            hs_vals = [s.handshake_ms for s in suites_list if s.handshake_ms > 0]
            if hs_vals:
                avg_hs = statistics.mean(hs_vals)
                kem_summary.append((kem, avg_hs, len(suites_list)))
        
        kem_summary.sort(key=lambda x: x[1])  # Sort by avg handshake
        
        lines.append(f"\n  {'KEM Algorithm':<40} {'Avg HS (ms)':<12} {'Count'}")
        lines.append("  " + "-" * 60)
        for kem, avg_hs, count in kem_summary:
            lines.append(f"  {kem:<40} {avg_hs:>10.2f}   {count:>3}")
        
        # Analysis by Signature Algorithm
        lines.append("\n" + "-" * 80)
        lines.append("10. ANALYSIS BY SIGNATURE ALGORITHM")
        lines.append("-" * 80)
        
        sig_groups = {}
        for s in self.suites:
            if s.sig_name not in sig_groups:
                sig_groups[s.sig_name] = []
            sig_groups[s.sig_name].append(s)
        
        sig_summary = []
        for sig, suites_list in sorted(sig_groups.items()):
            hs_vals = [s.handshake_ms for s in suites_list if s.handshake_ms > 0]
            if hs_vals:
                avg_hs = statistics.mean(hs_vals)
                sig_summary.append((sig, avg_hs, len(suites_list)))
        
        sig_summary.sort(key=lambda x: x[1])
        
        lines.append(f"\n  {'Signature Algorithm':<40} {'Avg HS (ms)':<12} {'Count'}")
        lines.append("  " + "-" * 60)
        for sig, avg_hs, count in sig_summary:
            lines.append(f"  {sig:<40} {avg_hs:>10.2f}   {count:>3}")
        
        # Analysis by NIST Level
        lines.append("\n" + "-" * 80)
        lines.append("11. ANALYSIS BY NIST SECURITY LEVEL")
        lines.append("-" * 80)
        
        level_groups = {}
        for s in self.suites:
            lvl = s.nist_level
            if lvl not in level_groups:
                level_groups[lvl] = []
            level_groups[lvl].append(s)
        
        for lvl in sorted(level_groups.keys()):
            suites_list = level_groups[lvl]
            hs_vals = [s.handshake_ms for s in suites_list if s.handshake_ms > 0]
            if hs_vals:
                stats = compute_stats(hs_vals)
                lines.append(f"\n  NIST Level {lvl}: ({len(suites_list)} suites)")
                lines.append(f"    Handshake: Mean={stats.mean:.2f}ms, Median={stats.median:.2f}ms, P95={stats.p95:.2f}ms")
        
        # Data Quality Assessment
        lines.append("\n" + "-" * 80)
        lines.append("12. DATA QUALITY ASSESSMENT")
        lines.append("-" * 80)
        
        # Check for missing/zero values
        total = len(self.suites)
        metrics_coverage = {
            "handshake_ms": len([s for s in self.suites if s.handshake_ms > 0]),
            "throughput_mbps": len([s for s in self.suites if s.throughput_mbps > 0]),
            "latency_ms": len([s for s in self.suites if s.latency_ms > 0]),
            "power_w": len([s for s in self.suites if s.power_w > 0]),
            "energy_mj": len([s for s in self.suites if s.energy_mj > 0]),
            "kem_keygen_ms": len([s for s in self.suites if s.kem_keygen_ms > 0]),
            "kem_encaps_ms": len([s for s in self.suites if s.kem_encaps_ms > 0]),
            "kem_decaps_ms": len([s for s in self.suites if s.kem_decaps_ms > 0]),
            "sig_sign_ms": len([s for s in self.suites if s.sig_sign_ms > 0]),
            "sig_verify_ms": len([s for s in self.suites if s.sig_verify_ms > 0]),
        }
        
        lines.append(f"\n  Metric Coverage (non-zero values):")
        lines.append(f"  {'Metric':<25} {'Count':<10} {'Coverage'}")
        lines.append("  " + "-" * 50)
        for metric, count in metrics_coverage.items():
            pct = count / max(1, total) * 100
            status = "OK" if pct >= 90 else "WARN" if pct >= 50 else "MISS"
            lines.append(f"  {metric:<25} {count:>5}/{total:<5} {pct:>5.1f}% {status}")
        
        # Outlier Detection
        lines.append("\n  Outlier Detection (>3σ from mean):")
        hs_vals = [s.handshake_ms for s in self.suites if s.handshake_ms > 0]
        if len(hs_vals) > 2:
            mean = statistics.mean(hs_vals)
            stddev = statistics.stdev(hs_vals)
            outliers = [v for v in hs_vals if abs(v - mean) > 3 * stddev]
            lines.append(f"    Handshake outliers: {len(outliers)} of {len(hs_vals)}")
        
        # Executive Summary
        lines.append("\n" + "=" * 80)
        lines.append("EXECUTIVE SUMMARY")
        lines.append("=" * 80)
        
        if hs_stats:
            lines.append(f"\n  • Analyzed {len(self.suites)} cipher suite combinations")
            lines.append(f"  • Handshake latency: {hs_stats.mean:.1f}ms mean, {hs_stats.median:.1f}ms median")
            lines.append(f"  • Handshake range: {hs_stats.min_val:.1f}ms to {hs_stats.max_val:.1f}ms ({hs_stats.max_val/max(0.01, hs_stats.min_val):.1f}x spread)")
            
            if tp_stats:
                lines.append(f"  • Data throughput: {tp_stats.mean:.1f} Mbps average")
            
            # Best performers
            if kem_summary:
                best_kem = kem_summary[0]
                lines.append(f"  • Fastest KEM: {best_kem[0]} ({best_kem[1]:.1f}ms avg)")
            
            if sig_summary:
                best_sig = sig_summary[0]
                lines.append(f"  • Fastest Signature: {best_sig[0]} ({best_sig[1]:.1f}ms avg)")
        
        lines.append("\n" + "=" * 80)
        lines.append("END OF REPORT")
        lines.append("=" * 80)
        
        return "\n".join(lines)
    
    def export_json(self, outpath: str):
        """Export analysis results as JSON."""
        results = {
            "analysis_timestamp": datetime.now().isoformat(),
            "source_file": str(self.filepath),
            "run_id": self.data.get('run_id'),
            "total_suites": len(self.suites),
            "unique_kems": list(set(s.kem_name for s in self.suites)),
            "unique_sigs": list(set(s.sig_name for s in self.suites)),
            "unique_aeads": list(set(s.aead for s in self.suites)),
            "statistics": {}
        }
        
        # Compute stats for each metric
        metrics = {
            "handshake_ms": [s.handshake_ms for s in self.suites if s.handshake_ms > 0],
            "throughput_mbps": [s.throughput_mbps for s in self.suites if s.throughput_mbps > 0],
            "latency_ms": [s.latency_ms for s in self.suites if s.latency_ms > 0],
            "kem_keygen_ms": [s.kem_keygen_ms for s in self.suites if s.kem_keygen_ms > 0],
            "kem_encaps_ms": [s.kem_encaps_ms for s in self.suites if s.kem_encaps_ms > 0],
            "kem_decaps_ms": [s.kem_decaps_ms for s in self.suites if s.kem_decaps_ms > 0],
            "sig_sign_ms": [s.sig_sign_ms for s in self.suites if s.sig_sign_ms > 0],
            "sig_verify_ms": [s.sig_verify_ms for s in self.suites if s.sig_verify_ms > 0],
        }
        
        for metric, vals in metrics.items():
            stats = compute_stats(vals)
            if stats:
                results["statistics"][metric] = {
                    "count": stats.count,
                    "mean": round(stats.mean, 4),
                    "median": round(stats.median, 4),
                    "stddev": round(stats.stddev, 4),
                    "min": round(stats.min_val, 4),
                    "max": round(stats.max_val, 4),
                    "p25": round(stats.p25, 4),
                    "p75": round(stats.p75, 4),
                    "p95": round(stats.p95, 4),
                    "p99": round(stats.p99, 4),
                }
        
        with open(outpath, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"Analysis JSON exported to: {outpath}")


def main():
    import sys
    
    # Find benchmark files
    if len(sys.argv) > 1:
        filepath = sys.argv[1]
    else:
        # Default to most recent benchmark
        bench_dir = Path("logs/benchmarks")
        if bench_dir.exists():
            files = sorted(bench_dir.glob("benchmark_results_*.json"))
            if files:
                filepath = str(files[-1])
            else:
                print("No benchmark files found in logs/benchmarks/")
                return
        else:
            print("Directory logs/benchmarks/ not found")
            return
    
    print(f"Analyzing: {filepath}")
    print()
    
    analyzer = BenchmarkAnalyzer(filepath)
    
    # Generate and print report
    report = analyzer.generate_report()
    print(report)
    
    # Save report
    report_path = Path(filepath).parent / f"analysis_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"\nReport saved to: {report_path}")
    
    # Export JSON
    json_path = Path(filepath).parent / f"analysis_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    analyzer.export_json(str(json_path))


if __name__ == "__main__":
    main()
