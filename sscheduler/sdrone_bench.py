#!/usr/bin/env python3
"""
Benchmark Drone Scheduler - sscheduler/sdrone_bench.py

A specialized drone scheduler for comprehensive suite benchmarking.
Cycles through ALL suites every 10 seconds, collecting detailed metrics.

Usage:
    python -m sscheduler.sdrone_bench [options]

Options:
    --interval SECS     Suite cycle interval (default: 10)
    --filter-aead AEAD  Only benchmark suites with this AEAD (aesgcm|chacha|ascon)
    --max-suites N      Maximum suites to benchmark
    --dry-run           Print plan without executing
"""

import os
import sys
import time
import json
import socket
import signal
import argparse
import threading
import subprocess
import logging
import atexit
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

_SCHEDULER = None

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import CONFIG
from core.suites import get_suite, list_suites
from core.process import ManagedProcess
from core.clock_sync import ClockSync
from sscheduler.benchmark_policy import BenchmarkPolicy, BenchmarkAction, get_suite_count

# Import MetricsAggregator for comprehensive metrics collection
try:
    from core.metrics_aggregator import MetricsAggregator
    HAS_METRICS_AGGREGATOR = True
except ImportError:
    HAS_METRICS_AGGREGATOR = False
    MetricsAggregator = None

# Extract config values
DRONE_HOST = str(CONFIG.get("DRONE_HOST"))
GCS_HOST = str(CONFIG.get("GCS_HOST"))
# For GCS control, use LAN by default since data plane also uses LAN
# Can override with GCS_CONTROL_HOST env var or --gcs-host CLI arg
GCS_CONTROL_HOST = os.environ.get("GCS_CONTROL_HOST") or str(CONFIG.get("GCS_HOST"))
GCS_CONTROL_PORT = int(CONFIG.get("GCS_CONTROL_PORT", 48080))
GCS_TELEMETRY_PORT = int(CONFIG.get("GCS_TELEMETRY_PORT", 52080))
DRONE_PLAIN_RX_PORT = int(CONFIG.get("DRONE_PLAINTEXT_RX", 47004))
DRONE_PLAIN_TX_PORT = int(CONFIG.get("DRONE_PLAINTEXT_TX", 47003))

SECRETS_DIR = Path(__file__).parent.parent / "secrets" / "matrix"
ROOT = Path(__file__).resolve().parents[1]
LOGS_DIR = ROOT / "logs" / "benchmarks"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# =============================================================================
# Logging
# =============================================================================

def log(msg: str, level: str = "INFO"):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    prefix = f"[{ts}] [sdrone-bench]"
    if level == "ERROR":
        print(f"{prefix} ERROR: {msg}", flush=True)
    elif level == "WARN":
        print(f"{prefix} WARN: {msg}", flush=True)
    else:
        print(f"{prefix} {msg}", flush=True)

# =============================================================================
# GCS Control Client
# =============================================================================

def send_gcs_command(cmd: str, **params) -> dict:
    """Send command to GCS control server."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(30.0)
        sock.connect((GCS_CONTROL_HOST, GCS_CONTROL_PORT))
        
        request = {"cmd": cmd, **params}
        sock.sendall(json.dumps(request).encode() + b"\n")
        
        response = b""
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            response += chunk
            if b"\n" in response:
                break
        
        sock.close()
        return json.loads(response.decode().strip())
    except Exception as e:
        return {"status": "error", "message": str(e)}

def wait_for_gcs(timeout: float = 30.0) -> bool:
    """Wait for GCS control server to be ready."""
    start = time.time()
    while time.time() - start < timeout:
        result = send_gcs_command("ping")
        if result.get("status") == "ok":
            return True
        time.sleep(0.5)
    return False

# =============================================================================
# Drone Proxy Manager
# =============================================================================

class DroneProxyManager:
    """Manages drone proxy subprocess."""
    
    def __init__(self):
        self.managed_proc = None
        self.current_suite = None
        self.last_log_path = None
    
    def start(self, suite_name: str) -> bool:
        """Start drone proxy with given suite."""
        if self.managed_proc and self.managed_proc.is_running():
            self.stop()
        
        suite = get_suite(suite_name)
        if not suite:
            log(f"Unknown suite: {suite_name}", "ERROR")
            return False
        
        secret_dir = SECRETS_DIR / suite_name
        peer_pubkey = secret_dir / "gcs_signing.pub"
        
        if not peer_pubkey.exists():
            log(f"Missing key: {peer_pubkey}", "ERROR")
            return False
        
        cmd = [
            sys.executable, "-m", "core.run_proxy", "drone",
            "--suite", suite_name,
            "--peer-pubkey-file", str(peer_pubkey),
            "--quiet",
            "--status-file", str(LOGS_DIR / "drone_status.json")
        ]

        timestamp = time.strftime("%Y%m%d-%H%M%S")
        log_path = LOGS_DIR / f"drone_{suite_name}_{timestamp}.log"
        log_handle = open(log_path, "w", encoding="utf-8")
        
        self.managed_proc = ManagedProcess(
            cmd=cmd,
            name=f"proxy-{suite_name}",
            stdout=log_handle,
            stderr=subprocess.STDOUT
        )
        
        if self.managed_proc.start():
            self.last_log_path = log_path
            self.current_suite = suite_name
            time.sleep(1.0)  # Short wait for process to start
            if not self.managed_proc.is_running():
                log(f"Proxy exited early", "ERROR")
                return False
            return True
        return False
    
    def stop(self):
        """Stop drone proxy."""
        if self.managed_proc:
            self.managed_proc.stop()
            self.managed_proc = None
            self.current_suite = None
    
    def is_running(self) -> bool:
        return self.managed_proc is not None and self.managed_proc.is_running()

# =============================================================================
# Handshake Status Reader
# =============================================================================

def read_handshake_status(timeout: float = 45.0) -> Dict[str, Any]:
    """Read handshake status and metrics from status file.
    
    Note: Some PQC suites (Classic McEliece) can take 30+ seconds
    for key operations, so allow generous timeout.
    
    The proxy writes 'handshake_ok' immediately after handshake,
    then switches to 'running' for periodic updates. Both are valid.
    """
    status_file = LOGS_DIR / "drone_status.json"
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        if status_file.exists():
            try:
                with open(status_file, "r") as f:
                    data = json.load(f)
                    status = data.get("status")
                    # Accept both handshake_ok and running (running means handshake succeeded)
                    if status in ("handshake_ok", "running"):
                        # Extract handshake metrics from either location
                        metrics = data.get("handshake_metrics")
                        if not metrics:
                            # In 'running' status, metrics may be nested in counters
                            counters = data.get("counters", {})
                            metrics = counters.get("handshake_metrics", {})
                        if metrics:
                            data["handshake_metrics"] = metrics
                            data["status"] = "handshake_ok"  # Normalize
                            return data
            except Exception:
                pass
        time.sleep(0.2)
    
    return {"status": "timeout", "handshake_metrics": {}}

# =============================================================================
# MAVProxy Manager
# =============================================================================

# Sniff port for MAVLink metrics collector (different from proxy port to avoid conflict)
MAVLINK_SNIFF_PORT = 47005

def start_mavproxy(mav_master: str) -> Optional[ManagedProcess]:
    """Start persistent MAVProxy for drone."""
    python_exe = sys.executable
    # Primary output to proxy for encryption/forwarding
    out_proxy = f"udp:127.0.0.1:{DRONE_PLAIN_TX_PORT}"
    # Secondary output for MAVLink metrics sniffing
    out_sniff = f"udp:127.0.0.1:{MAVLINK_SNIFF_PORT}"
    
    cmd = [
        python_exe, "-m", "MAVProxy.mavproxy",
        f"--master={mav_master}",
        f"--out={out_proxy}",
        f"--out={out_sniff}",
        # "--nowait",  # REMOVED: Bind lifecycle to parent
        # "--daemon",  # REMOVED: Bind lifecycle to parent
    ]
    
    ts = time.strftime("%Y%m%d-%H%M%S")
    log_path = LOGS_DIR / f"mavproxy_bench_{ts}.log"
    
    try:
        fh = open(log_path, "w", encoding="utf-8")
    except Exception:
        fh = subprocess.DEVNULL
    
    log(f"Starting MAVProxy: {' '.join(cmd)}")
    
    proc = ManagedProcess(
        cmd=cmd,
        name="mavproxy-bench",
        stdout=fh,
        stderr=subprocess.STDOUT,
        new_console=False
    )
    
    if proc.start():
        time.sleep(1.0)
        return proc if proc.is_running() else None
    return None

# =============================================================================
# Benchmark Scheduler
# =============================================================================

class BenchmarkScheduler:
    """Main benchmark scheduler orchestrating suite cycling."""
    
    def __init__(self, args):
        self.args = args
        self.proxy = DroneProxyManager()
        self.mavproxy_proc = None
        self.clock_sync = ClockSync()
        
        # Initialize benchmark policy
        self.policy = BenchmarkPolicy(
            cycle_interval_s=args.interval,
            filter_aead=args.filter_aead
        )
        
        # Limit suites if requested
        if args.max_suites and args.max_suites < len(self.policy.suite_list):
            self.policy.suite_list = self.policy.suite_list[:args.max_suites]
            log(f"Limited to {args.max_suites} suites")
        
        # Results tracking
        self.results_file = LOGS_DIR / f"benchmark_{self.policy.run_id}.jsonl"
        self.summary_file = LOGS_DIR / f"benchmark_summary_{self.policy.run_id}.json"
        self.gcs_results_file = LOGS_DIR / f"benchmark_gcs_{self.policy.run_id}.jsonl"
        
        # Initialize comprehensive metrics aggregator (drone side)
        self.metrics_aggregator = None
        if HAS_METRICS_AGGREGATOR:
            try:
                self.metrics_aggregator = MetricsAggregator(
                    role="drone",
                    output_dir=str(LOGS_DIR / "comprehensive")
                )
                self.metrics_aggregator.set_run_id(self.policy.run_id)
                log("MetricsAggregator initialized for comprehensive metrics")
            except Exception as e:
                log(f"MetricsAggregator init failed: {e}", "WARN")
    
    def run(self):
        """Run the benchmark."""
        total_suites = len(self.policy.suite_list)
        estimated_time = total_suites * self.args.interval
        
        log("=" * 70)
        log("BENCHMARK MODE - Comprehensive Suite Testing")
        log("=" * 70)
        log(f"Total suites to test: {total_suites}")
        log(f"Interval per suite: {self.args.interval}s")
        log(f"Estimated total time: {estimated_time/60:.1f} minutes")
        log(f"Output directory: {LOGS_DIR}")
        log(f"Filter AEAD: {self.args.filter_aead or 'all'}")
        log("=" * 70)
        
        if self.args.dry_run:
            log("DRY RUN - Printing plan only:")
            for i, suite in enumerate(self.policy.suite_list):
                cfg = self.policy.all_suites.get(suite, {})
                log(f"  {i+1:3d}. {suite} ({cfg.get('nist_level', '?')})")
            return
        
        # Wait for GCS
        log("Waiting for GCS control server...")
        if not wait_for_gcs(timeout=60.0):
            log("GCS not available, aborting", "ERROR")
            return
        log("GCS connected")

        # Clock sync with GCS
        try:
            t1 = time.time()
            resp = send_gcs_command("chronos_sync", t1=t1)
            t4 = time.time()
            if resp.get("status") == "ok":
                offset = self.clock_sync.update_from_rpc(t1, t4, resp)
                log(f"Clock sync offset (gcs-drone): {offset:.6f}s")
                if self.metrics_aggregator:
                    self.metrics_aggregator.set_clock_offset(offset, method="chronos")
            else:
                log(f"Clock sync failed: {resp}", "WARN")
        except Exception as e:
            log(f"Clock sync error: {e}", "WARN")
        
        # Start MAVProxy
        log("Starting MAVProxy...")
        self.mavproxy_proc = start_mavproxy(self.args.mav_master)
        if not self.mavproxy_proc:
            log("MAVProxy failed to start, continuing anyway", "WARN")
        
        # Start benchmark
        try:
            start_time = self.clock_sync.synced_time() if self.clock_sync.is_synced() else time.monotonic()
            first_suite = self.policy.start_benchmark(start_time_mono=start_time)
            log(f"Starting benchmark with {first_suite}")
            
            self._run_loop()
            
        except KeyboardInterrupt:
            log("Benchmark interrupted by user")
        finally:
            self._cleanup()
            self._save_final_summary()
    
    def _run_loop(self):
        """Main benchmark loop."""
        current_suite = self.policy.get_current_suite()
        
        while not self.policy.benchmark_complete:
            # Activate current suite
            if not self._activate_suite(current_suite):
                log(f"Failed to activate {current_suite}, marking as failed", "WARN")
                self.policy.finalize_suite_metrics(success=False, error_message="activation_failed")
            
            # Wait for policy to switch
            while True:
                now = self.clock_sync.synced_time() if self.clock_sync.is_synced() else time.monotonic()
                output = self.policy.evaluate(now)
                
                if output.action == BenchmarkAction.COMPLETE:
                    log("Benchmark complete!")
                    if self.metrics_aggregator:
                        self.metrics_aggregator.record_control_plane_metrics(
                            scheduler_action_type=str(output.action),
                            scheduler_action_reason=output.reasons[0] if output.reasons else "",
                            policy_name="BenchmarkPolicy",
                            policy_state="COMPLETE",
                            policy_suite_index=output.current_index,
                            policy_total_suites=output.total_suites,
                            scheduler_tick_interval_ms=self.args.interval * 1000.0,
                        )
                    
                    # 1. Collect GCS metrics FIRST (so we can include them in final report)
                    gcs_metrics = self._collect_gcs_metrics(current_suite)

                    # 2. Finalize metrics (passing GCS data for consolidation)
                    self._finalize_metrics(success=True, gcs_metrics=gcs_metrics)
                    return
                
                if output.action == BenchmarkAction.NEXT_SUITE:
                    progress = output.progress_pct
                    log(f"[{progress:.1f}%] Switching to {output.target_suite}")

                    if self.metrics_aggregator:
                        self.metrics_aggregator.record_control_plane_metrics(
                            scheduler_action_type=str(output.action),
                            scheduler_action_reason=output.reasons[0] if output.reasons else "",
                            policy_name="BenchmarkPolicy",
                            policy_state="ADVANCE",
                            policy_suite_index=output.current_index,
                            policy_total_suites=output.total_suites,
                            scheduler_tick_interval_ms=self.args.interval * 1000.0,
                        )
                    
                    # 1. Collect GCS metrics FIRST
                    gcs_metrics = self._collect_gcs_metrics(current_suite)
                    gcs_ok = bool(gcs_metrics)
                    
                    # 2. Finalize metrics (passing GCS data for consolidation)
                    self._finalize_metrics(success=True, gcs_metrics=gcs_metrics)
                    
                    # Stop current proxy
                    self.proxy.stop()
                    # Stop GCS proxy via stop_suite (already stopped); fallback to prepare_rekey if needed
                    if not gcs_ok:
                        resp = send_gcs_command("prepare_rekey")
                        if resp.get("status") != "ok":
                            log(f"GCS prepare_rekey failed: {resp}", "WARN")
                    time.sleep(0.5)
                    
                    current_suite = output.target_suite
                    break
                
                # HOLD - wait a bit
                time.sleep(1.0)
    
    def _activate_suite(self, suite_name: str) -> bool:
        """Activate a suite on both drone and GCS."""
        log(f"Activating suite: {suite_name}")
        
        # Get suite config for metrics
        suite_config = self.policy.all_suites.get(suite_name, {})
        
        # Start comprehensive metrics collection
        if self.metrics_aggregator:
            try:
                self.metrics_aggregator.start_suite(suite_name, suite_config)
                self.metrics_aggregator.record_handshake_start()
                self.metrics_aggregator.record_control_plane_metrics(
                    scheduler_tick_interval_ms=self.args.interval * 1000.0,
                    policy_name="BenchmarkPolicy",
                    policy_state="ACTIVE",
                    policy_suite_index=self.policy.current_index,
                    policy_total_suites=len(self.policy.suite_list),
                )
            except Exception as e:
                log(f"Metrics start failed: {e}", "WARN")
        
        # Clear old status file to avoid reading stale data
        status_file = LOGS_DIR / "drone_status.json"
        try:
            if status_file.exists():
                status_file.unlink()
        except Exception:
            pass
        
        # Tell GCS to start proxy
        resp = send_gcs_command("start_proxy", suite=suite_name, run_id=self.policy.run_id)
        if resp.get("status") != "ok":
            log(f"GCS rejected: {resp}", "ERROR")
            self._finalize_metrics(success=False, error="gcs_rejected")
            return False
        
        log(f"  GCS proxy started, starting drone proxy...")
        
        # Start drone proxy
        if not self.proxy.start(suite_name):
            log("Drone proxy failed to start", "ERROR")
            self._finalize_metrics(success=False, error="proxy_start_failed")
            return False
        
        log(f"  Drone proxy started, waiting for handshake...")
        
        # Read handshake metrics (allow 45s for Classic McEliece)
        status = read_handshake_status(timeout=45.0)
        if status.get("status") == "handshake_ok":
            metrics = status.get("handshake_metrics", {})
            self.policy.record_handshake_metrics(metrics)
            
            handshake_ms = metrics.get("rekey_ms", 0)
            log(f"  Handshake OK: {handshake_ms:.1f}ms")
            
            # Record crypto primitives in aggregator
            if self.metrics_aggregator:
                try:
                    self.metrics_aggregator.record_handshake_end(success=True)
                    self.metrics_aggregator.record_crypto_primitives(metrics)
                except Exception as e:
                    log(f"Metrics record failed: {e}", "WARN")
            
            # Log to results file
            self._log_result(suite_name, metrics, success=True)
            
            # NOTE: _finalize_metrics() is called AFTER the interval wait, in _run_loop
            # when NEXT_SUITE is triggered, so data plane metrics can accumulate
            return True
        else:
            log(f"  Handshake timeout/failed", "WARN")
            self._log_result(suite_name, {}, success=False, error="handshake_timeout")
            self._finalize_metrics(success=False, error="handshake_timeout")
            return False
    
    def _finalize_metrics(self, success: bool, error: str = "", gcs_metrics: Dict = None):
        """Finalize and save comprehensive metrics for current suite."""
        if not self.metrics_aggregator:
            return
        try:
            # Read data plane metrics from proxy status file (allow a brief window for the status writer to run)
            status_file = LOGS_DIR / "drone_status.json"
            counters: Dict[str, Any] = {}
            if status_file.exists():
                for _ in range(3):  # up to ~3s total
                    try:
                        with open(status_file, "r") as f:
                            status_data = json.load(f)
                        candidate = status_data.get("counters", {})
                        counters = candidate or counters
                        # Break early if counters are present and non-empty
                        if candidate:
                            break
                    except Exception:
                        pass
                    time.sleep(1.0)
            if counters:
                self.metrics_aggregator.record_data_plane_metrics(counters)
                log(
                    "  Data plane: ptx_in=%s, enc_out=%s" %
                    (counters.get("ptx_in", 0), counters.get("enc_out", 0))
                )
            
            # NOTE: record_handshake_end() is NOT called here.
            # It was already called in _activate_suite() immediately after handshake completion.
            # Calling it here would overwrite the correct handshake duration with the suite duration.
            
            # MERGE GCS METRICS HERE
            comprehensive = self.metrics_aggregator.finalize_suite(merge_from=gcs_metrics)
            if comprehensive:
                # Export to JSON
                output_path = self.metrics_aggregator.save_suite_metrics(comprehensive)
                if output_path:
                    log(f"  Comprehensive metrics saved: {output_path}")
        except Exception as e:
            log(f"Metrics finalize failed: {e}", "WARN")

    def _collect_gcs_metrics(self, suite_name: str) -> Optional[Dict[str, Any]]:
        """Fetch GCS-side metrics for the suite and return them (also log to JSONL)."""
        gcs_info: Dict[str, Any] = {}
        try:
            info_resp = send_gcs_command("get_info")
            if info_resp.get("status") == "ok":
                gcs_info = info_resp
        except Exception:
            gcs_info = {}
        try:
            resp = send_gcs_command("stop_suite")
        except Exception as e:
            log(f"GCS stop_suite error: {e}", "WARN")
            return None

        if resp.get("status") != "ok":
            log(f"GCS stop_suite failed: {resp}", "WARN")
            return None

        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "suite_id": suite_name,
            "gcs_metrics": resp,
            "gcs_info": gcs_info,
        }
        try:
            with open(self.gcs_results_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            log(f"Failed to log GCS metrics: {e}", "WARN")
            # Don't return None here, we still have the metrics to pass to aggregator
        
        if gcs_info:
            resp = dict(resp)
            resp["gcs_info"] = gcs_info
        return resp
    
    def _log_result(self, suite_name: str, metrics: Dict, success: bool, error: str = ""):
        """Log result to JSONL file."""
        cfg = self.policy.all_suites.get(suite_name, {})
        
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "suite_id": suite_name,
            "nist_level": cfg.get("nist_level", ""),
            "kem_name": cfg.get("kem_name", ""),
            "sig_name": cfg.get("sig_name", ""),
            "aead": cfg.get("aead", ""),
            "success": success,
            "error": error,
            "handshake_ms": metrics.get("rekey_ms", 0),
            "kem_keygen_ms": metrics.get("kem_keygen_max_ms", 0),
            "kem_encaps_ms": metrics.get("kem_encaps_max_ms", 0),
            "kem_decaps_ms": metrics.get("kem_decaps_max_ms", 0),
            "sig_sign_ms": metrics.get("sig_sign_max_ms", 0),
            "sig_verify_ms": metrics.get("sig_verify_max_ms", 0),
            "pub_key_size_bytes": metrics.get("pub_key_size_bytes", 0),
            "ciphertext_size_bytes": metrics.get("ciphertext_size_bytes", 0),
            "sig_size_bytes": metrics.get("sig_size_bytes", 0)
        }
        
        try:
            with open(self.results_file, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            log(f"Failed to log result: {e}", "WARN")
    
    def _cleanup(self):
        """Cleanup resources."""
        log("Cleaning up...")
        if self.proxy:
            self.proxy.stop()
        if self.mavproxy_proc:
            self.mavproxy_proc.stop()
    
    def _save_final_summary(self):
        """Save final benchmark summary."""
        summary = self.policy.get_progress_summary()
        summary["collected_metrics"] = len(self.policy.collected_metrics)
        summary["results_file"] = str(self.results_file)
        
        # Calculate statistics
        successful = [m for m in self.policy.collected_metrics if m.success]
        if successful:
            handshake_times = [m.handshake_ms for m in successful]
            summary["stats"] = {
                "successful_count": len(successful),
                "failed_count": len(self.policy.collected_metrics) - len(successful),
                "handshake_min_ms": min(handshake_times),
                "handshake_max_ms": max(handshake_times),
                "handshake_avg_ms": sum(handshake_times) / len(handshake_times)
            }
        
        try:
            with open(self.summary_file, "w") as f:
                json.dump(summary, f, indent=2)
            log(f"Summary saved to {self.summary_file}")
        except Exception as e:
            log(f"Failed to save summary: {e}", "WARN")

# =============================================================================
# Cleanup
# =============================================================================

def cleanup_environment(aggressive: bool = False):
    """Kill stale processes if aggressive, otherwise just MAVProxy."""
    patterns = ["mavproxy.py"]
    if aggressive:
        patterns.append("core.run_proxy")
    for p in patterns:
        try:
            subprocess.run(["pkill", "-f", p], 
                          stdout=subprocess.DEVNULL, 
                          stderr=subprocess.DEVNULL)
        except Exception:
            pass
    time.sleep(0.5)


def _atexit_cleanup():
    global _SCHEDULER
    try:
        if _SCHEDULER is not None:
            _SCHEDULER._cleanup()
    except Exception:
        pass
    try:
        cleanup_environment(aggressive=True)
    except Exception:
        pass

# =============================================================================
# Main
# =============================================================================

def main():
    global GCS_CONTROL_HOST
    parser = argparse.ArgumentParser(description="Benchmark Drone Scheduler")
    parser.add_argument("--mav-master", 
                       default=str(CONFIG.get("MAV_MASTER", "/dev/ttyACM0")),
                       help="MAVLink master (e.g., /dev/ttyACM0)")
    parser.add_argument("--interval", type=float, default=110.0,
                       help="Seconds per suite (default: 110)")
    parser.add_argument("--filter-aead", choices=["aesgcm", "chacha", "ascon"],
                       help="Only benchmark suites with this AEAD")
    parser.add_argument("--max-suites", type=int,
                       help="Maximum number of suites to benchmark")
    parser.add_argument("--dry-run", action="store_true",
                       help="Print plan without executing")
    parser.add_argument("--gcs-host", type=str,
                       help="GCS control server host (override for Tailscale)")
    args = parser.parse_args()
    
    # Override GCS host if provided
    if args.gcs_host:
        GCS_CONTROL_HOST = args.gcs_host
        log(f"Using GCS host override: {GCS_CONTROL_HOST}")
    
    # Setup signal handler
    def sigint_handler(sig, frame):
        log("Interrupted")
        cleanup_environment(aggressive=True)  # Full cleanup on interrupt
        sys.exit(0)
    
    signal.signal(signal.SIGINT, sigint_handler)
    # Don't register atexit - it kills proxies during normal benchmark flow
    
    # Light cleanup before starting (just MAVProxy, not proxies)
    # Aggressive cleanup before starting to ensure clean slate (per Operational Plan)
    cleanup_environment(aggressive=True)
    
    # Run benchmark
    scheduler = BenchmarkScheduler(args)
    global _SCHEDULER
    _SCHEDULER = scheduler
    atexit.register(_atexit_cleanup)
    scheduler.run()
    
    return 0

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sys.exit(main())
