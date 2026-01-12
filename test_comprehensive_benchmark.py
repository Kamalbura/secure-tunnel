#!/usr/bin/env python3
"""
Comprehensive Benchmark Runner
test_comprehensive_benchmark.py

Runs ALL cipher suites with full metrics collection across categories A-R.
Generates aggressive per-suite JSON files with ~200+ metrics each.

Usage:
    # GCS side (Windows):
    python test_comprehensive_benchmark.py --role gcs

    # Drone side (Raspberry Pi - run first to wait for GCS connections):
    python test_comprehensive_benchmark.py --role drone

Or use scheduler-based orchestration:
    python -m scheduler.sgcs --bench-mode comprehensive
"""

import argparse
import json
import os
import sys
import time
import socket
import threading
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.config import CONFIG
from core.suites import SUITES, get_suite, list_suites
from core.async_proxy import start_proxy, ProxyCounters
from core.metrics_schema import ComprehensiveSuiteMetrics
from core.metrics_aggregator import MetricsAggregator
from core.metrics_collectors import EnvironmentCollector


# =============================================================================
# CONFIGURATION
# =============================================================================

BENCHMARK_CONFIG = {
    # Timing
    "handshake_timeout_s": 60.0,       # Max time for handshake
    "traffic_duration_s": 3.0,          # Traffic phase duration
    "inter_suite_delay_s": 2.0,         # Delay between suites
    "cooldown_between_suites_s": 1.0,   # Cooldown after each suite
    
    # Output
    "output_dir": "logs/comprehensive_benchmark",
    "per_suite_json": True,
    "combined_json": True,
    "generate_summary": True,
    
    # Control
    "skip_failed_suites": True,
    "max_consecutive_failures": 5,
    "retry_on_failure": 0,
    
    # Network
    "tcp_handshake_port": 44444,
    "udp_gcs_rx": 5001,
    "udp_drone_rx": 5002,
}


# =============================================================================
# SUITE RUNNER
# =============================================================================

class ComprehensiveBenchmarkRunner:
    """Runs benchmark with comprehensive metrics collection."""
    
    def __init__(self, role: str, config: Dict[str, Any] = None):
        """
        Initialize runner.
        
        Args:
            role: "gcs" or "drone"
            config: Optional config overrides
        """
        self.role = role
        self.config = {**BENCHMARK_CONFIG, **(config or {})}
        
        # Run identification
        self.run_id = datetime.now().strftime("bench_%Y%m%d_%H%M%S")
        
        # Output directory
        self.output_dir = Path(self.config["output_dir"]) / self.run_id
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Metrics aggregator
        self.aggregator = MetricsAggregator(role=role, output_dir=str(self.output_dir))
        self.aggregator.set_run_id(self.run_id)
        
        # Results storage
        self.results: List[Dict[str, Any]] = []
        self.all_metrics: List[ComprehensiveSuiteMetrics] = []
        
        # Statistics
        self.total_suites = 0
        self.successful_suites = 0
        self.failed_suites = 0
        self.consecutive_failures = 0
        
        # Environment info
        self.env_collector = EnvironmentCollector()
    
    def get_suite_list(self, filter_pattern: str = None) -> List[str]:
        """Get list of suites to benchmark."""
        all_suites = list(list_suites().keys())
        
        if filter_pattern:
            return [s for s in all_suites if filter_pattern.lower() in s.lower()]
        
        return all_suites
    
    def prepare_config(self, suite_id: str) -> Dict[str, Any]:
        """Prepare proxy config for a suite."""
        base_config = dict(CONFIG)
        
        # Override network settings
        base_config["TCP_HANDSHAKE_PORT"] = self.config["tcp_handshake_port"]
        base_config["UDP_GCS_RX"] = self.config["udp_gcs_rx"]
        base_config["UDP_DRONE_RX"] = self.config["udp_drone_rx"]
        
        # Get suite details
        suite = get_suite(suite_id)
        base_config["SUITE_AEAD_TOKEN"] = suite.get("aead_token", "aesgcm")
        
        return base_config
    
    def run_single_suite(
        self,
        suite_id: str,
        suite_config: Dict[str, Any],
        proxy_config: Dict[str, Any],
        gcs_sig_secret: Optional[object] = None,
        gcs_sig_public: Optional[bytes] = None,
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Run a single suite benchmark.
        
        Returns:
            (success, result_dict)
        """
        result = {
            "suite_id": suite_id,
            "role": self.role,
            "success": False,
            "error": None,
            "handshake_ms": 0.0,
            "traffic_ms": 0.0,
            "counters": {},
            "metrics": None,
        }
        
        start_time = time.time()
        
        try:
            # Start metrics collection
            metrics = self.aggregator.start_suite(suite_id, suite_config)
            
            # Record handshake start
            self.aggregator.record_handshake_start()
            
            # Create stop event and ready event
            stop_event = threading.Event()
            ready_event = threading.Event()
            
            # Status file for this run
            status_file = self.output_dir / f"{suite_id}_{self.role}_status.json"
            
            # Run proxy with timeout
            proxy_result = {}
            proxy_error = None
            
            def run_proxy_thread():
                nonlocal proxy_result, proxy_error
                try:
                    proxy_result = start_proxy(
                        role=self.role,
                        suite=suite_config,
                        cfg=proxy_config,
                        gcs_sig_secret=gcs_sig_secret,
                        gcs_sig_public=gcs_sig_public,
                        stop_after_seconds=self.config["handshake_timeout_s"] + self.config["traffic_duration_s"],
                        status_file=str(status_file),
                        ready_event=ready_event,
                    )
                except Exception as e:
                    proxy_error = e
            
            # Start proxy in thread
            proxy_thread = threading.Thread(target=run_proxy_thread)
            proxy_thread.start()
            
            # Wait for handshake completion (check status file)
            handshake_timeout = time.time() + self.config["handshake_timeout_s"]
            handshake_done = False
            
            while time.time() < handshake_timeout:
                if status_file.exists():
                    try:
                        status_data = json.loads(status_file.read_text())
                        if status_data.get("status") == "handshake_ok":
                            handshake_done = True
                            result["handshake_ms"] = (time.time() - start_time) * 1000
                            
                            # Record handshake success
                            self.aggregator.record_handshake_end(success=True)
                            
                            # Extract handshake metrics
                            hs_metrics = status_data.get("handshake_metrics", {})
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
                                    "shared_secret_size_bytes": kem.get("shared_secret_bytes", 0),
                                })
                            
                            break
                    except json.JSONDecodeError:
                        pass
                
                time.sleep(0.1)
            
            if not handshake_done:
                raise TimeoutError(f"Handshake timeout for {suite_id}")
            
            # Traffic phase
            self.aggregator.record_traffic_start()
            time.sleep(self.config["traffic_duration_s"])
            self.aggregator.record_traffic_end()
            
            result["traffic_ms"] = self.config["traffic_duration_s"] * 1000
            
            # Wait for proxy to finish
            proxy_thread.join(timeout=5.0)
            
            if proxy_error:
                raise proxy_error
            
            # Record counters
            if proxy_result:
                result["counters"] = proxy_result
                self.aggregator.record_data_plane_metrics(proxy_result)
            
            # Finalize metrics
            final_metrics = self.aggregator.finalize_suite()
            result["metrics"] = final_metrics.to_dict()
            result["success"] = True
            
            self.all_metrics.append(final_metrics)
            
        except Exception as e:
            result["error"] = str(e)
            result["traceback"] = traceback.format_exc()
            
            # Record failure
            self.aggregator.record_handshake_end(success=False, failure_reason=str(e))
            self.aggregator.finalize_suite()
        
        result["total_ms"] = (time.time() - start_time) * 1000
        return result["success"], result
    
    def run_all_suites(
        self,
        suite_filter: str = None,
        gcs_sig_secret: Optional[object] = None,
        gcs_sig_public: Optional[bytes] = None,
    ) -> Dict[str, Any]:
        """
        Run benchmark for all suites.
        
        Args:
            suite_filter: Optional filter pattern
            gcs_sig_secret: GCS signing key (for gcs role)
            gcs_sig_public: GCS public key (for drone role)
        
        Returns:
            Summary dict
        """
        suites = self.get_suite_list(suite_filter)
        self.total_suites = len(suites)
        
        print("=" * 70)
        print(f"COMPREHENSIVE BENCHMARK - {self.role.upper()}")
        print("=" * 70)
        print(f"Run ID: {self.run_id}")
        print(f"Total suites: {self.total_suites}")
        print(f"Output dir: {self.output_dir}")
        print("=" * 70)
        
        # Collect environment info
        env_info = self.env_collector.collect()
        
        start_time = time.time()
        
        for i, suite_id in enumerate(suites, 1):
            print(f"\n[{i}/{self.total_suites}] {suite_id}")
            
            # Check consecutive failures
            if self.consecutive_failures >= self.config["max_consecutive_failures"]:
                print(f"ABORT: {self.consecutive_failures} consecutive failures")
                break
            
            try:
                suite_config = get_suite(suite_id)
                proxy_config = self.prepare_config(suite_id)
                
                success, result = self.run_single_suite(
                    suite_id,
                    suite_config,
                    proxy_config,
                    gcs_sig_secret=gcs_sig_secret,
                    gcs_sig_public=gcs_sig_public,
                )
                
                self.results.append(result)
                
                if success:
                    self.successful_suites += 1
                    self.consecutive_failures = 0
                    print(f"  ✓ SUCCESS - Handshake: {result['handshake_ms']:.1f}ms")
                else:
                    self.failed_suites += 1
                    self.consecutive_failures += 1
                    print(f"  ✗ FAILED - {result.get('error', 'Unknown error')}")
                
                # Save per-suite JSON
                if self.config["per_suite_json"]:
                    suite_file = self.output_dir / f"{suite_id}_{self.role}.json"
                    suite_file.write_text(json.dumps(result, indent=2, default=str))
                
            except Exception as e:
                print(f"  ✗ ERROR - {e}")
                self.failed_suites += 1
                self.consecutive_failures += 1
                self.results.append({
                    "suite_id": suite_id,
                    "success": False,
                    "error": str(e),
                })
            
            # Inter-suite delay
            if i < len(suites):
                time.sleep(self.config["inter_suite_delay_s"])
        
        total_time = time.time() - start_time
        
        # Generate summary
        summary = {
            "run_id": self.run_id,
            "role": self.role,
            "environment": env_info,
            "config": self.config,
            "total_suites": self.total_suites,
            "successful_suites": self.successful_suites,
            "failed_suites": self.failed_suites,
            "success_rate": self.successful_suites / max(1, self.total_suites) * 100,
            "total_time_s": total_time,
            "avg_time_per_suite_s": total_time / max(1, len(self.results)),
            "results": self.results,
        }
        
        # Save combined JSON
        if self.config["combined_json"]:
            combined_file = self.output_dir / f"benchmark_results_{self.role}.json"
            combined_file.write_text(json.dumps(summary, indent=2, default=str))
        
        # Print summary
        print("\n" + "=" * 70)
        print("BENCHMARK SUMMARY")
        print("=" * 70)
        print(f"Total: {self.total_suites} | Success: {self.successful_suites} | Failed: {self.failed_suites}")
        print(f"Success Rate: {summary['success_rate']:.1f}%")
        print(f"Total Time: {total_time:.1f}s")
        print(f"Output: {self.output_dir}")
        print("=" * 70)
        
        return summary


# =============================================================================
# KEY LOADING
# =============================================================================

def load_gcs_signing_key(secrets_dir: Path = None):
    """Load GCS signing key for benchmarks."""
    if secrets_dir is None:
        secrets_dir = PROJECT_ROOT / "secrets" / "localtest"
    
    # Try different key formats
    key_files = [
        "gcs_signing.key",
        "gcs_signing.pem",
        "gcs_sig.key",
    ]
    
    for kf in key_files:
        key_path = secrets_dir / kf
        if key_path.exists():
            return key_path.read_bytes()
    
    return None


def load_gcs_public_key(secrets_dir: Path = None):
    """Load GCS public key for benchmarks."""
    if secrets_dir is None:
        secrets_dir = PROJECT_ROOT / "secrets"
    
    key_files = [
        "gcs_signing.pub",
        "localtest/gcs_signing.pub",
    ]
    
    for kf in key_files:
        key_path = secrets_dir / kf
        if key_path.exists():
            return key_path.read_bytes()
    
    return None


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Comprehensive PQC Benchmark")
    parser.add_argument("--role", required=True, choices=["gcs", "drone"],
                        help="Role to run benchmark as")
    parser.add_argument("--filter", type=str, default=None,
                        help="Filter suites by pattern (e.g., 'mlkem512')")
    parser.add_argument("--output", type=str, default=None,
                        help="Output directory override")
    parser.add_argument("--timeout", type=float, default=60.0,
                        help="Handshake timeout in seconds")
    parser.add_argument("--traffic", type=float, default=3.0,
                        help="Traffic phase duration in seconds")
    
    args = parser.parse_args()
    
    # Build config
    config = dict(BENCHMARK_CONFIG)
    if args.output:
        config["output_dir"] = args.output
    if args.timeout:
        config["handshake_timeout_s"] = args.timeout
    if args.traffic:
        config["traffic_duration_s"] = args.traffic
    
    # Load keys
    if args.role == "gcs":
        gcs_sig_secret = load_gcs_signing_key()
        gcs_sig_public = None
        if not gcs_sig_secret:
            print("ERROR: GCS signing key not found")
            sys.exit(1)
    else:
        gcs_sig_secret = None
        gcs_sig_public = load_gcs_public_key()
        if not gcs_sig_public:
            print("ERROR: GCS public key not found")
            sys.exit(1)
    
    # Create and run benchmark
    runner = ComprehensiveBenchmarkRunner(role=args.role, config=config)
    
    summary = runner.run_all_suites(
        suite_filter=args.filter,
        gcs_sig_secret=gcs_sig_secret,
        gcs_sig_public=gcs_sig_public,
    )
    
    # Exit code based on success rate
    if summary["success_rate"] >= 90:
        sys.exit(0)
    elif summary["success_rate"] >= 50:
        sys.exit(1)
    else:
        sys.exit(2)


if __name__ == "__main__":
    main()
