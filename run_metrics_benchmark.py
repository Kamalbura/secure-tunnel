#!/usr/bin/env python3
"""
run_metrics_benchmark.py

Comprehensive metrics benchmark - runs selected suites with full 231-metric collection.
Designed to work with existing scheduler infrastructure.

Usage:
    # GCS side:
    python run_metrics_benchmark.py --role gcs --suites 3

    # Drone side:
    python run_metrics_benchmark.py --role drone --suites 3
"""

import argparse
import json
import os
import sys
import time
import socket
import struct
import threading
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from core.config import CONFIG
from core.suites import get_suite, list_suites, SUITES
from core.metrics_schema import ComprehensiveSuiteMetrics, count_metrics
from core.metrics_aggregator import MetricsAggregator
from core.metrics_collectors import EnvironmentCollector, SystemCollector, NetworkCollector, LatencyTracker

# =============================================================================
# CONFIGURATION
# =============================================================================

BENCHMARK_CONFIG = {
    "handshake_timeout_s": 30.0,
    "traffic_duration_s": 5.0,
    "inter_suite_delay_s": 2.0,
    "traffic_rate_mbps": 50.0,
    "payload_size": 1200,
}

SECRETS_DIR = ROOT / "secrets" / "matrix"
OUTPUT_DIR = ROOT / "logs" / "metrics_benchmark"


# =============================================================================
# TRAFFIC GENERATOR
# =============================================================================

class TrafficGenerator:
    """Generate and measure UDP traffic through proxy."""
    
    def __init__(self, role: str):
        self.role = role
        self.latency_tracker = LatencyTracker()
        
        if role == "gcs":
            self.tx_addr = ("127.0.0.1", CONFIG["GCS_PLAINTEXT_TX"])
            self.rx_port = CONFIG["GCS_PLAINTEXT_RX"]
        else:
            self.tx_addr = ("127.0.0.1", CONFIG["DRONE_PLAINTEXT_TX"])
            self.rx_port = CONFIG["DRONE_PLAINTEXT_RX"]
    
    def run_traffic(self, duration_s: float, rate_mbps: float) -> Dict[str, Any]:
        """Run traffic test and collect metrics."""
        tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        rx.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        rx.bind(("127.0.0.1", self.rx_port))
        rx.settimeout(0.1)
        
        payload_size = BENCHMARK_CONFIG["payload_size"]
        pps = (rate_mbps * 1_000_000) / (8 * payload_size)
        interval = 1.0 / max(pps, 1)
        
        sent = 0
        received = 0
        bytes_sent = 0
        bytes_recv = 0
        latencies = []
        
        end_time = time.time() + duration_s
        seq = 0
        
        while time.time() < end_time:
            # Send packet
            send_time_ns = time.time_ns()
            payload = struct.pack("!IQ", seq, send_time_ns) + b"M" * (payload_size - 12)
            
            try:
                tx.sendto(payload, self.tx_addr)
                sent += 1
                bytes_sent += len(payload)
            except Exception:
                pass
            
            # Receive responses
            t0 = time.time()
            while time.time() - t0 < interval:
                try:
                    data, _ = rx.recvfrom(65535)
                    if len(data) >= 12:
                        received += 1
                        bytes_recv += len(data)
                        _, ts_sent = struct.unpack("!IQ", data[:12])
                        lat_ms = (time.time_ns() - ts_sent) / 1_000_000
                        latencies.append(lat_ms)
                        self.latency_tracker.record(lat_ms)
                except socket.timeout:
                    break
            
            seq += 1
            time.sleep(max(0, interval - (time.time() - t0)))
        
        tx.close()
        rx.close()
        
        return {
            "packets_sent": sent,
            "packets_received": received,
            "bytes_sent": bytes_sent,
            "bytes_received": bytes_recv,
            "delivery_rate": received / max(sent, 1),
            "latency_stats": self.latency_tracker.get_stats(),
            "latencies": latencies[:1000],  # Cap at 1000 samples
        }


# =============================================================================
# SUITE BENCHMARK
# =============================================================================

class MetricsBenchmark:
    """Run benchmark with comprehensive metrics collection."""
    
    def __init__(self, role: str, output_dir: Path = None):
        self.role = role
        self.run_id = datetime.now().strftime("metrics_%Y%m%d_%H%M%S")
        
        self.output_dir = output_dir or OUTPUT_DIR / self.run_id
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.aggregator = MetricsAggregator(role=role, output_dir=str(self.output_dir))
        self.aggregator.set_run_id(self.run_id)
        
        self.env_collector = EnvironmentCollector()
        self.sys_collector = SystemCollector()
        self.net_collector = NetworkCollector()
        
        self.results: List[Dict[str, Any]] = []
        self.all_metrics: List[ComprehensiveSuiteMetrics] = []
    
    def get_available_suites(self) -> List[str]:
        """Get suites that have keys available."""
        available = []
        for suite_id in list_suites().keys():
            suite_dir = SECRETS_DIR / suite_id
            if suite_dir.exists():
                gcs_key = suite_dir / "gcs_signing.key"
                gcs_pub = suite_dir / "gcs_signing.pub"
                if gcs_key.exists() and gcs_pub.exists():
                    available.append(suite_id)
        return available
    
    def collect_baseline_metrics(self) -> Dict[str, Any]:
        """Collect baseline system metrics before benchmark."""
        return {
            "environment": self.env_collector.collect(),
            "system_baseline": self.sys_collector.collect(),
            "network_baseline": self.net_collector.collect(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    
    def run_suite(self, suite_id: str, proxy_proc: subprocess.Popen) -> Dict[str, Any]:
        """Run a single suite with full metrics collection."""
        result = {
            "suite_id": suite_id,
            "role": self.role,
            "success": False,
            "error": None,
        }
        
        suite_config = get_suite(suite_id)
        start_time = time.time()
        
        try:
            # Start metrics aggregation
            metrics = self.aggregator.start_suite(suite_id, suite_config)
            
            # Record handshake timing
            self.aggregator.record_handshake_start()
            
            # Wait for proxy to establish connection (check status)
            status_file = self.output_dir / f"{suite_id}_{self.role}_status.json"
            handshake_timeout = time.time() + BENCHMARK_CONFIG["handshake_timeout_s"]
            handshake_done = False
            
            while time.time() < handshake_timeout:
                if proxy_proc.poll() is not None:
                    raise RuntimeError("Proxy exited during handshake")
                
                if status_file.exists():
                    try:
                        status = json.loads(status_file.read_text())
                        if status.get("status") == "handshake_ok":
                            handshake_done = True
                            hs_metrics = status.get("handshake_metrics", {})
                            
                            # Record handshake success
                            self.aggregator.record_handshake_end(success=True)
                            
                            # Extract primitive timing
                            if hs_metrics:
                                primitives = hs_metrics.get("primitives", {})
                                kem = primitives.get("kem", {})
                                sig = primitives.get("signature", {})
                                
                                self.aggregator.record_crypto_primitives({
                                    "kem_keygen_ns": kem.get("keygen_ns", 0),
                                    "kem_encaps_ns": kem.get("encap_ns", 0),
                                    "kem_decaps_ns": kem.get("decap_ns", 0),
                                    "sig_sign_ns": sig.get("sign_ns", 0),
                                    "sig_verify_ns": sig.get("verify_ns", 0),
                                    "pub_key_size_bytes": kem.get("public_key_bytes", 0),
                                    "ciphertext_size_bytes": kem.get("ciphertext_bytes", 0),
                                    "sig_size_bytes": sig.get("signature_bytes", 0),
                                })
                            
                            break
                    except json.JSONDecodeError:
                        pass
                
                time.sleep(0.2)
            
            if not handshake_done:
                raise TimeoutError("Handshake timeout")
            
            result["handshake_ms"] = (time.time() - start_time) * 1000
            
            # Traffic phase
            self.aggregator.record_traffic_start()
            traffic_gen = TrafficGenerator(self.role)
            traffic_result = traffic_gen.run_traffic(
                BENCHMARK_CONFIG["traffic_duration_s"],
                BENCHMARK_CONFIG["traffic_rate_mbps"]
            )
            self.aggregator.record_traffic_end()
            
            # Record data plane metrics
            self.aggregator.record_data_plane_metrics({
                "ptx_in": traffic_result["packets_sent"],
                "ptx_out": traffic_result["packets_received"],
                "enc_in": traffic_result["packets_sent"],
                "enc_out": traffic_result["packets_received"],
                "bytes_in": traffic_result["bytes_received"],
                "bytes_out": traffic_result["bytes_sent"],
            })
            
            # Record latency samples
            for lat in traffic_result.get("latencies", [])[:500]:
                self.aggregator.record_latency_sample(lat)
            
            result["traffic"] = traffic_result
            result["success"] = True
            
        except Exception as e:
            result["error"] = str(e)
            self.aggregator.record_handshake_end(success=False, failure_reason=str(e))
        
        # Finalize metrics
        final_metrics = self.aggregator.finalize_suite()
        result["metrics"] = final_metrics.to_dict()
        result["total_ms"] = (time.time() - start_time) * 1000
        
        self.all_metrics.append(final_metrics)
        self.results.append(result)
        
        return result
    
    def save_comprehensive_output(self):
        """Save all results to JSON files."""
        # Individual suite results already saved by aggregator
        
        # Save combined results
        combined = {
            "run_id": self.run_id,
            "role": self.role,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "config": BENCHMARK_CONFIG,
            "baseline": self.collect_baseline_metrics(),
            "metrics_schema_fields": count_metrics(),
            "results": self.results,
            "summary": {
                "total_suites": len(self.results),
                "successful": sum(1 for r in self.results if r["success"]),
                "failed": sum(1 for r in self.results if not r["success"]),
            },
        }
        
        combined_file = self.output_dir / f"combined_results_{self.role}.json"
        combined_file.write_text(json.dumps(combined, indent=2, default=str))
        
        print(f"\nResults saved to: {self.output_dir}")
        return combined


def start_proxy(role: str, suite_id: str, status_file: Path, stop_seconds: float) -> subprocess.Popen:
    """Start proxy process."""
    suite_dir = SECRETS_DIR / suite_id
    
    if role == "gcs":
        key_file = suite_dir / "gcs_signing.key"
        cmd = [
            sys.executable, "-m", "core.run_proxy", "gcs",
            f"--suite={suite_id}",
            f"--gcs-secret-file={key_file}",
            f"--status-file={status_file}",
            f"--stop-seconds={stop_seconds}",
            "--quiet",
        ]
    else:
        key_file = suite_dir / "gcs_signing.pub"
        cmd = [
            sys.executable, "-m", "core.run_proxy", "drone",
            f"--suite={suite_id}",
            f"--peer-pubkey-file={key_file}",
            f"--status-file={status_file}",
            f"--stop-seconds={stop_seconds}",
            "--quiet",
        ]
    
    return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def main():
    parser = argparse.ArgumentParser(description="Comprehensive Metrics Benchmark")
    parser.add_argument("--role", required=True, choices=["gcs", "drone"])
    parser.add_argument("--suites", type=int, default=5, help="Number of suites to benchmark")
    parser.add_argument("--filter", type=str, default=None, help="Filter suites by pattern")
    args = parser.parse_args()
    
    print("=" * 70)
    print(f"COMPREHENSIVE METRICS BENCHMARK - {args.role.upper()}")
    print("=" * 70)
    
    benchmark = MetricsBenchmark(args.role)
    available = benchmark.get_available_suites()
    
    if args.filter:
        available = [s for s in available if args.filter.lower() in s.lower()]
    
    suites_to_run = available[:args.suites]
    
    print(f"Run ID: {benchmark.run_id}")
    print(f"Available suites: {len(available)}")
    print(f"Suites to benchmark: {len(suites_to_run)}")
    print(f"Output: {benchmark.output_dir}")
    
    # Collect baseline
    print("\nCollecting baseline metrics...")
    baseline = benchmark.collect_baseline_metrics()
    print(f"  CPU: {baseline['system_baseline']['cpu_percent']:.1f}%")
    print(f"  Memory: {baseline['system_baseline']['memory_rss_mb']:.1f} MB")
    
    print("\n" + "-" * 70)
    
    for i, suite_id in enumerate(suites_to_run, 1):
        print(f"\n[{i}/{len(suites_to_run)}] {suite_id}")
        
        status_file = benchmark.output_dir / f"{suite_id}_{args.role}_status.json"
        total_time = BENCHMARK_CONFIG["handshake_timeout_s"] + BENCHMARK_CONFIG["traffic_duration_s"] + 10
        
        # Start proxy
        proxy = start_proxy(args.role, suite_id, status_file, total_time)
        
        try:
            result = benchmark.run_suite(suite_id, proxy)
            
            if result["success"]:
                traffic = result.get("traffic", {})
                lat_stats = traffic.get("latency_stats", {})
                print(f"  ✓ SUCCESS")
                print(f"    Handshake: {result['handshake_ms']:.1f}ms")
                print(f"    Packets: {traffic.get('packets_sent', 0)} sent, {traffic.get('packets_received', 0)} recv")
                print(f"    Delivery: {traffic.get('delivery_rate', 0)*100:.1f}%")
                print(f"    Latency p50: {lat_stats.get('p50_ms', 0):.2f}ms, p95: {lat_stats.get('p95_ms', 0):.2f}ms")
            else:
                print(f"  ✗ FAILED: {result['error']}")
        
        finally:
            if proxy.poll() is None:
                proxy.terminate()
                proxy.wait(timeout=2)
        
        # Inter-suite delay
        if i < len(suites_to_run):
            time.sleep(BENCHMARK_CONFIG["inter_suite_delay_s"])
    
    # Save comprehensive output
    print("\n" + "=" * 70)
    combined = benchmark.save_comprehensive_output()
    
    print("BENCHMARK SUMMARY")
    print("=" * 70)
    print(f"Total: {combined['summary']['total_suites']}")
    print(f"Success: {combined['summary']['successful']}")
    print(f"Failed: {combined['summary']['failed']}")
    print(f"Output: {benchmark.output_dir}")


if __name__ == "__main__":
    main()
