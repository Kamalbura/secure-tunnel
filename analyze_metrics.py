#!/usr/bin/env python3
"""
analyze_metrics.py

Data Engineering & Analysis for Comprehensive PQC Metrics

This script provides:
1. Schema validation - confirms all 231 metrics captured
2. Statistical analysis - descriptive stats for each category
3. Comparison analysis - across AEAD, KEM, Signature variants
4. Data quality checks - missing values, outliers, anomalies
5. Export-ready summaries - for reporting and visualization
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from collections import defaultdict
import statistics

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from core.metrics_schema import (
    ComprehensiveSuiteMetrics,
    count_metrics,
    RunContextMetrics,
    SuiteCryptoIdentity,
    SuiteLifecycleTimeline,
    HandshakeMetrics,
    CryptoPrimitiveBreakdown,
    DataPlaneMetrics,
    LatencyJitterMetrics,
    SystemResourcesDrone,
    SystemResourcesGcs,
    PowerEnergyMetrics,
    ValidationMetrics,
)


@dataclass
class MetricStats:
    """Statistical summary for a single metric."""
    name: str
    count: int
    non_null: int
    null_percent: float
    min_val: float
    max_val: float
    mean: float
    median: float
    std_dev: float
    p25: float
    p75: float
    p95: float


class MetricsAnalyzer:
    """Comprehensive metrics analyzer for PQC benchmark data."""
    
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.metrics_data: List[Dict[str, Any]] = []
        self.suite_metrics: List[ComprehensiveSuiteMetrics] = []
        self.analysis_results: Dict[str, Any] = {}
    
    def load_data(self) -> int:
        """Load all JSON metrics files from directory."""
        json_files = list(self.data_dir.glob("*.json"))
        
        for jf in json_files:
            if "combined" in jf.name:
                continue  # Skip combined results
            
            try:
                data = json.loads(jf.read_text())

                # Accept both formats:
                # 1) Wrapped: {"metrics": {...}}
                # 2) Direct:  {...} (asdict(ComprehensiveSuiteMetrics))
                metrics_dict = None
                if isinstance(data, dict) and "metrics" in data and isinstance(data.get("metrics"), dict):
                    metrics_dict = data["metrics"]
                elif isinstance(data, dict) and "run_context" in data:
                    metrics_dict = data

                if metrics_dict is None:
                    continue

                wrapped = {"metrics": metrics_dict}
                self.metrics_data.append(wrapped)

                # Try to reconstruct ComprehensiveSuiteMetrics
                try:
                    m = ComprehensiveSuiteMetrics.from_dict(metrics_dict)
                    self.suite_metrics.append(m)
                except Exception:
                    pass
            except Exception as e:
                print(f"Warning: Could not load {jf.name}: {e}")
        
        print(f"Loaded {len(self.metrics_data)} suite results")
        return len(self.metrics_data)
    
    def validate_schema(self) -> Dict[str, Any]:
        """Validate that all 231 metrics are captured."""
        expected = count_metrics()
        total_expected = expected["TOTAL"]
        
        validation = {
            "expected_fields": total_expected,
            "categories": {},
            "missing_fields": [],
            "populated_fields": [],
            "validation_pass": True,
        }
        
        if not self.metrics_data:
            validation["validation_pass"] = False
            validation["error"] = "No data loaded"
            return validation
        
        # Analyze first suite's metrics structure
        sample = self.metrics_data[0].get("metrics", {})
        
        # Check each category
        category_map = {
            "A. Run & Context": "run_context",
            "B. Suite Crypto Identity": "crypto_identity",
            "C. Suite Lifecycle Timeline": "lifecycle",
            "D. Handshake Metrics": "handshake",
            "E. Crypto Primitive Breakdown": "crypto_primitives",
            "F. Rekey Metrics": "rekey",
            "G. Data Plane": "data_plane",
            "H. Latency & Jitter": "latency_jitter",
            "I. MAVProxy Drone": "mavproxy_drone",
            "J. MAVProxy GCS": "mavproxy_gcs",
            "K. MAVLink Integrity": "mavlink_integrity",
            "L. Flight Controller": "fc_telemetry",
            "M. Control Plane": "control_plane",
            "N. System Drone": "system_drone",
            "O. System GCS": "system_gcs",
            "P. Power & Energy": "power_energy",
            "Q. Observability": "observability",
            "R. Validation": "validation",
        }
        
        total_found = 0
        for cat_name, cat_key in category_map.items():
            expected_count = expected.get(cat_name, 0)
            cat_data = sample.get(cat_key, {})
            found_count = len(cat_data) if isinstance(cat_data, dict) else 0
            
            validation["categories"][cat_name] = {
                "expected": expected_count,
                "found": found_count,
                "match": found_count >= expected_count * 0.8,  # 80% threshold
                "fields": list(cat_data.keys()) if isinstance(cat_data, dict) else [],
            }
            total_found += found_count
        
        validation["total_found"] = total_found
        validation["coverage_percent"] = (total_found / total_expected) * 100 if total_expected > 0 else 0
        
        if validation["coverage_percent"] < 70:
            validation["validation_pass"] = False
        
        return validation
    
    def compute_statistics(self) -> Dict[str, Any]:
        """Compute descriptive statistics for all numeric metrics."""
        stats = {
            "handshake": {},
            "crypto_primitives": {},
            "data_plane": {},
            "latency": {},
            "system": {},
        }
        
        if not self.metrics_data:
            return stats
        
        # Collect values for each metric
        handshake_durations = []
        kem_encaps_times = []
        sig_verify_times = []
        packets_sent = []
        packets_recv = []
        delivery_rates = []
        latency_avg = []
        latency_p95 = []
        cpu_usage = []
        
        for data in self.metrics_data:
            m = data.get("metrics", {})
            
            # Handshake
            hs = m.get("handshake", {})
            if hs.get("handshake_total_duration_ms"):
                handshake_durations.append(hs["handshake_total_duration_ms"])
            
            # Crypto primitives
            cp = m.get("crypto_primitives", {})
            if cp.get("kem_encapsulation_time_ms"):
                kem_encaps_times.append(cp["kem_encapsulation_time_ms"])
            if cp.get("signature_verify_time_ms"):
                sig_verify_times.append(cp["signature_verify_time_ms"])
            
            # Data plane
            dp = m.get("data_plane", {})
            if dp.get("packets_sent"):
                packets_sent.append(dp["packets_sent"])
            if dp.get("packets_received"):
                packets_recv.append(dp["packets_received"])
            if dp.get("packet_delivery_ratio"):
                delivery_rates.append(dp["packet_delivery_ratio"])
            
            # Latency
            lat = m.get("latency_jitter", {})
            if lat.get("one_way_latency_avg_ms"):
                latency_avg.append(lat["one_way_latency_avg_ms"])
            if lat.get("one_way_latency_p95_ms"):
                latency_p95.append(lat["one_way_latency_p95_ms"])
            
            # System
            sys_d = m.get("system_drone", {})
            sys_g = m.get("system_gcs", {})
            if sys_d.get("cpu_usage_avg_percent"):
                cpu_usage.append(sys_d["cpu_usage_avg_percent"])
            if sys_g.get("cpu_usage_avg_percent"):
                cpu_usage.append(sys_g["cpu_usage_avg_percent"])
        
        def calc_stats(values: List[float], name: str) -> Dict[str, Any]:
            if not values:
                return {"name": name, "count": 0}
            
            sorted_vals = sorted(values)
            n = len(sorted_vals)
            
            return {
                "name": name,
                "count": n,
                "min": min(values),
                "max": max(values),
                "mean": statistics.mean(values),
                "median": statistics.median(values),
                "std_dev": statistics.stdev(values) if n > 1 else 0,
                "p25": sorted_vals[int(n * 0.25)] if n > 0 else 0,
                "p75": sorted_vals[int(n * 0.75)] if n > 0 else 0,
                "p95": sorted_vals[int(n * 0.95)] if n > 0 else 0,
            }
        
        stats["handshake"]["duration_ms"] = calc_stats(handshake_durations, "Handshake Duration (ms)")
        stats["crypto_primitives"]["kem_encaps_ms"] = calc_stats(kem_encaps_times, "KEM Encapsulation (ms)")
        stats["crypto_primitives"]["sig_verify_ms"] = calc_stats(sig_verify_times, "Signature Verify (ms)")
        stats["data_plane"]["packets_sent"] = calc_stats(packets_sent, "Packets Sent")
        stats["data_plane"]["packets_recv"] = calc_stats(packets_recv, "Packets Received")
        stats["data_plane"]["delivery_rate"] = calc_stats(delivery_rates, "Delivery Rate")
        stats["latency"]["avg_ms"] = calc_stats(latency_avg, "Latency Avg (ms)")
        stats["latency"]["p95_ms"] = calc_stats(latency_p95, "Latency P95 (ms)")
        stats["system"]["cpu_percent"] = calc_stats(cpu_usage, "CPU Usage (%)")
        
        return stats
    
    def analyze_by_algorithm(self) -> Dict[str, Any]:
        """Analyze metrics grouped by KEM, Signature, and AEAD algorithms."""
        by_kem = defaultdict(list)
        by_sig = defaultdict(list)
        by_aead = defaultdict(list)
        
        for data in self.metrics_data:
            m = data.get("metrics", {})
            ci = m.get("crypto_identity", {})
            
            kem = ci.get("kem_algorithm", "unknown")
            sig = ci.get("sig_algorithm", "unknown")
            aead = ci.get("aead_algorithm", "unknown")
            
            hs = m.get("handshake", {})
            duration = hs.get("handshake_total_duration_ms", 0)
            
            if duration > 0:
                by_kem[kem].append(duration)
                by_sig[sig].append(duration)
                by_aead[aead].append(duration)
        
        def summarize(groups: Dict[str, List[float]]) -> Dict[str, Any]:
            return {
                name: {
                    "count": len(vals),
                    "mean_ms": statistics.mean(vals) if vals else 0,
                    "min_ms": min(vals) if vals else 0,
                    "max_ms": max(vals) if vals else 0,
                }
                for name, vals in groups.items()
            }
        
        return {
            "by_kem": summarize(by_kem),
            "by_signature": summarize(by_sig),
            "by_aead": summarize(by_aead),
        }
    
    def data_quality_check(self) -> Dict[str, Any]:
        """Check data quality - missing values, outliers, anomalies."""
        quality = {
            "total_records": len(self.metrics_data),
            "complete_records": 0,
            "missing_fields": defaultdict(int),
            "outliers": [],
            "anomalies": [],
        }
        
        required_fields = [
            ("handshake", "handshake_success"),
            ("handshake", "handshake_total_duration_ms"),
            ("crypto_identity", "kem_algorithm"),
            ("crypto_identity", "sig_algorithm"),
            ("run_context", "suite_id"),
        ]
        
        for data in self.metrics_data:
            m = data.get("metrics", {})
            complete = True
            
            for cat, field in required_fields:
                cat_data = m.get(cat, {})
                if not cat_data.get(field):
                    quality["missing_fields"][f"{cat}.{field}"] += 1
                    complete = False
            
            if complete:
                quality["complete_records"] += 1
            
            # Check for outliers (handshake > 10s)
            hs = m.get("handshake", {})
            duration = hs.get("handshake_total_duration_ms", 0)
            if duration > 10000:  # > 10 seconds
                quality["outliers"].append({
                    "suite": m.get("run_context", {}).get("suite_id", "unknown"),
                    "metric": "handshake_duration_ms",
                    "value": duration,
                    "threshold": 10000,
                })
        
        quality["completeness_percent"] = (quality["complete_records"] / max(quality["total_records"], 1)) * 100
        quality["missing_fields"] = dict(quality["missing_fields"])
        
        return quality
    
    def generate_report(self) -> str:
        """Generate comprehensive analysis report."""
        lines = []
        lines.append("=" * 70)
        lines.append("COMPREHENSIVE METRICS ANALYSIS REPORT")
        lines.append("=" * 70)
        lines.append(f"Generated: {datetime.now().isoformat()}")
        lines.append(f"Data Directory: {self.data_dir}")
        lines.append("")
        
        # Schema Validation
        lines.append("-" * 70)
        lines.append("1. SCHEMA VALIDATION")
        lines.append("-" * 70)
        validation = self.validate_schema()
        lines.append(f"Expected Fields: {validation['expected_fields']}")
        lines.append(f"Found Fields: {validation.get('total_found', 0)}")
        lines.append(f"Coverage: {validation.get('coverage_percent', 0):.1f}%")
        lines.append(f"Validation: {'PASS' if validation['validation_pass'] else 'FAIL'}")
        lines.append("")
        
        for cat, info in validation.get("categories", {}).items():
            status = "✓" if info["match"] else "✗"
            lines.append(f"  {status} {cat}: {info['found']}/{info['expected']}")
        lines.append("")
        
        # Statistics
        lines.append("-" * 70)
        lines.append("2. DESCRIPTIVE STATISTICS")
        lines.append("-" * 70)
        stats = self.compute_statistics()
        
        for category, metrics in stats.items():
            lines.append(f"\n{category.upper()}:")
            for metric_name, metric_stats in metrics.items():
                if metric_stats.get("count", 0) > 0:
                    lines.append(f"  {metric_stats['name']}:")
                    lines.append(f"    n={metric_stats['count']}, mean={metric_stats['mean']:.3f}, "
                               f"median={metric_stats['median']:.3f}, std={metric_stats['std_dev']:.3f}")
                    lines.append(f"    min={metric_stats['min']:.3f}, max={metric_stats['max']:.3f}, "
                               f"p95={metric_stats['p95']:.3f}")
        lines.append("")
        
        # Algorithm Analysis
        lines.append("-" * 70)
        lines.append("3. ALGORITHM COMPARISON")
        lines.append("-" * 70)
        algo_analysis = self.analyze_by_algorithm()
        
        for group_name, group_data in algo_analysis.items():
            lines.append(f"\n{group_name.upper().replace('_', ' ')}:")
            for algo, stats in sorted(group_data.items(), key=lambda x: x[1]["mean_ms"]):
                lines.append(f"  {algo}: n={stats['count']}, mean={stats['mean_ms']:.2f}ms, "
                           f"range=[{stats['min_ms']:.2f}, {stats['max_ms']:.2f}]")
        lines.append("")
        
        # Data Quality
        lines.append("-" * 70)
        lines.append("4. DATA QUALITY CHECK")
        lines.append("-" * 70)
        quality = self.data_quality_check()
        lines.append(f"Total Records: {quality['total_records']}")
        lines.append(f"Complete Records: {quality['complete_records']}")
        lines.append(f"Completeness: {quality['completeness_percent']:.1f}%")
        
        if quality["missing_fields"]:
            lines.append("\nMissing Fields:")
            for field, count in quality["missing_fields"].items():
                lines.append(f"  {field}: {count} records")
        
        if quality["outliers"]:
            lines.append("\nOutliers Detected:")
            for outlier in quality["outliers"][:5]:
                lines.append(f"  {outlier['suite']}: {outlier['metric']}={outlier['value']}")
        lines.append("")
        
        lines.append("=" * 70)
        lines.append("END OF REPORT")
        lines.append("=" * 70)
        
        return "\n".join(lines)
    
    def run_full_analysis(self) -> Dict[str, Any]:
        """Run complete analysis pipeline."""
        print("Loading data...")
        count = self.load_data()
        
        if count == 0:
            print("No data to analyze!")
            return {}
        
        print("Validating schema...")
        self.analysis_results["schema_validation"] = self.validate_schema()
        
        print("Computing statistics...")
        self.analysis_results["statistics"] = self.compute_statistics()
        
        print("Analyzing algorithms...")
        self.analysis_results["algorithm_analysis"] = self.analyze_by_algorithm()
        
        print("Checking data quality...")
        self.analysis_results["data_quality"] = self.data_quality_check()
        
        # Generate report
        print("\nGenerating report...")
        report = self.generate_report()
        print(report)
        
        # Save analysis results
        analysis_file = self.data_dir / "analysis_results.json"
        analysis_file.write_text(json.dumps(self.analysis_results, indent=2, default=str))
        print(f"\nAnalysis saved to: {analysis_file}")
        
        return self.analysis_results


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Analyze PQC Metrics Data")
    parser.add_argument("--dir", type=str, required=True, help="Directory containing metrics JSON files")
    parser.add_argument("--output", type=str, default=None, help="Output file for report")
    args = parser.parse_args()
    
    analyzer = MetricsAnalyzer(Path(args.dir))
    results = analyzer.run_full_analysis()
    
    if args.output:
        Path(args.output).write_text(analyzer.generate_report())
        print(f"Report saved to: {args.output}")


if __name__ == "__main__":
    main()
