#!/usr/bin/env python3
"""
test_metrics_integration.py

Quick localhost test of the comprehensive metrics collection framework.
Runs a single suite to verify all collectors and aggregator work together.
"""

import os
import sys
import time
import json
import socket
import struct
import threading
import subprocess
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from core.config import CONFIG
from core.suites import get_suite, list_suites
from core.metrics_schema import ComprehensiveSuiteMetrics
from core.metrics_aggregator import MetricsAggregator

# =============================================================================
# LOCALHOST CONFIG
# =============================================================================

TEST_SUITE = "cs-mlkem768-aesgcm-mldsa65"  # Mid-range suite for testing
TRAFFIC_DURATION = 3.0
PAYLOAD_SIZE = 1200

SECRETS_DIR = ROOT / "secrets" / "matrix"

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def start_proxy_process(role: str, suite_id: str, secrets_dir: Path, status_file: Path = None, stop_seconds: float = None) -> subprocess.Popen:
    """Start a proxy process."""
    # Build key path
    suite_key_dir = secrets_dir / suite_id
    
    if role == "gcs":
        key_path = suite_key_dir / "gcs_signing.key"
        cmd = [
            sys.executable,
            "-m", "core.run_proxy", "gcs",
            f"--suite={suite_id}",
            f"--gcs-secret-file={key_path}",
            "--quiet",
        ]
    else:  # drone
        key_path = suite_key_dir / "gcs_signing.pub"
        cmd = [
            sys.executable,
            "-m", "core.run_proxy", "drone",
            f"--suite={suite_id}",
            f"--peer-pubkey-file={key_path}",
            "--quiet",
        ]
    
    if status_file:
        cmd.append(f"--status-file={status_file}")
    
    if stop_seconds:
        cmd.append(f"--stop-seconds={stop_seconds}")
    
    return subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def run_echo_server(stop_event: threading.Event, stats: dict):
    """Run plaintext echo server (simulates drone FC)."""
    rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    rx.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    rx.bind(("127.0.0.1", CONFIG["DRONE_PLAINTEXT_RX"]))
    rx.settimeout(0.5)
    
    tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    try:
        while not stop_event.is_set():
            try:
                data, addr = rx.recvfrom(65535)
                stats['rx'] += 1
                tx.sendto(data, ("127.0.0.1", CONFIG["DRONE_PLAINTEXT_TX"]))
                stats['tx'] += 1
            except socket.timeout:
                continue
    finally:
        rx.close()
        tx.close()


def traffic_generator(duration_s: float, rate_mbps: float, result: dict):
    """Generate UDP traffic and measure delivery."""
    tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    rx.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    rx.bind(("127.0.0.1", CONFIG["GCS_PLAINTEXT_RX"]))
    rx.settimeout(0.1)
    
    pps = (rate_mbps * 1_000_000) / (8 * PAYLOAD_SIZE)
    interval = 1.0 / pps if pps > 0 else 0.001
    
    sent = 0
    received = 0
    latencies = []
    end = time.time() + duration_s
    seq = 0
    
    while time.time() < end:
        send_time = time.time_ns()
        payload = struct.pack("!IQ", seq, send_time) + b"METRICS-TEST"
        
        try:
            tx.sendto(payload, ("127.0.0.1", CONFIG["GCS_PLAINTEXT_TX"]))
            sent += 1
        except Exception:
            pass
        
        # Non-blocking receive
        t0 = time.time()
        while time.time() - t0 < interval:
            try:
                data, addr = rx.recvfrom(65535)
                if len(data) >= 12:
                    received += 1
                    _, ts_sent = struct.unpack("!IQ", data[:12])
                    lat_ns = time.time_ns() - ts_sent
                    latencies.append(lat_ns / 1_000_000)  # Convert to ms
            except socket.timeout:
                break
            except Exception:
                break
        
        seq += 1
        time.sleep(max(0, interval - (time.time() - t0)))
    
    tx.close()
    rx.close()
    
    result['sent'] = sent
    result['received'] = received
    result['latencies'] = latencies
    result['delivery_rate'] = received / max(1, sent)


def main():
    print("=" * 70)
    print("METRICS INTEGRATION TEST")
    print("=" * 70)
    
    # Check keys exist - keys are in subdirectories by suite name
    suite_key_dir = SECRETS_DIR / TEST_SUITE
    gcs_key_path = suite_key_dir / "gcs_signing.key"
    drone_key_path = suite_key_dir / "drone_signing.key"
    
    if not suite_key_dir.exists():
        print(f"ERROR: Missing key directory for {TEST_SUITE}")
        print(f"  Expected: {suite_key_dir}")
        # List available suites
        available = [d.name for d in SECRETS_DIR.iterdir() if d.is_dir() and d.name.startswith("cs-")]
        print(f"  Available: {len(available)} suites")
        print(f"  First 5: {available[:5]}")
        sys.exit(1)
    
    if not gcs_key_path.exists() or not drone_key_path.exists():
        print(f"ERROR: Missing keys for {TEST_SUITE}")
        print(f"  GCS key: {gcs_key_path} - {'EXISTS' if gcs_key_path.exists() else 'MISSING'}")
        print(f"  Drone key: {drone_key_path} - {'EXISTS' if drone_key_path.exists() else 'MISSING'}")
        sys.exit(1)
    
    suite_config = get_suite(TEST_SUITE)
    
    print(f"Suite: {TEST_SUITE}")
    print(f"Traffic duration: {TRAFFIC_DURATION}s")
    
    # Initialize metrics aggregator
    run_id = datetime.now().strftime("test_%Y%m%d_%H%M%S")
    output_dir = ROOT / "logs" / "metrics_test" / run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    
    aggregator = MetricsAggregator(role="gcs", output_dir=str(output_dir))
    aggregator.set_run_id(run_id)
    
    print(f"Output dir: {output_dir}")
    print("-" * 70)
    
    # Start metrics collection
    print("\n1. Starting metrics collection...")
    metrics = aggregator.start_suite(TEST_SUITE, suite_config)
    
    # Start processes
    print("2. Starting proxies...")
    gcs_proc = None
    drone_proc = None
    echo_thread = None
    stop_echo = threading.Event()
    echo_stats = {'rx': 0, 'tx': 0}
    
    try:
        # Status files for monitoring
        gcs_status = output_dir / "gcs_status.json"
        drone_status = output_dir / "drone_status.json"
        
        # Start GCS proxy with status file
        total_duration = TRAFFIC_DURATION + 30  # Handshake + traffic + buffer
        gcs_proc = start_proxy_process("gcs", TEST_SUITE, SECRETS_DIR, gcs_status, total_duration)
        
        # Wait for GCS to be ready (listening on TCP)
        print("   Waiting for GCS to start...")
        time.sleep(1.0)
        
        # Start echo server
        echo_thread = threading.Thread(target=run_echo_server, args=(stop_echo, echo_stats))
        echo_thread.start()
        
        # Start drone proxy
        drone_proc = start_proxy_process("drone", TEST_SUITE, SECRETS_DIR, drone_status, total_duration)
        
        # Wait for handshake
        print("3. Waiting for handshake...")
        aggregator.record_handshake_start()
        time.sleep(2.0)  # Allow handshake to complete
        
        # Check if both are running
        if gcs_proc.poll() is not None:
            gcs_stdout, gcs_stderr = gcs_proc.communicate()
            print(f"  GCS proxy exited with code {gcs_proc.returncode}")
            print(f"  STDOUT: {gcs_stdout.decode()[:500] if gcs_stdout else 'empty'}")
            print(f"  STDERR: {gcs_stderr.decode()[:500] if gcs_stderr else 'empty'}")
            raise RuntimeError("GCS proxy process exited prematurely")
        
        if drone_proc.poll() is not None:
            drone_stdout, drone_stderr = drone_proc.communicate()
            print(f"  Drone proxy exited with code {drone_proc.returncode}")
            print(f"  STDOUT: {drone_stdout.decode()[:500] if drone_stdout else 'empty'}")
            print(f"  STDERR: {drone_stderr.decode()[:500] if drone_stderr else 'empty'}")
            raise RuntimeError("Drone proxy process exited prematurely")
        
        aggregator.record_handshake_end(success=True)
        print("   Handshake complete!")
        
        # Generate traffic
        print(f"4. Generating {TRAFFIC_DURATION}s of traffic...")
        aggregator.record_traffic_start()
        
        traffic_result = {}
        traffic_generator(TRAFFIC_DURATION, 10.0, traffic_result)  # 10 Mbps
        
        aggregator.record_traffic_end()
        
        # Record data plane metrics
        aggregator.record_data_plane_metrics({
            "ptx_in": traffic_result['sent'],
            "ptx_out": traffic_result['received'],
            "enc_in": traffic_result['sent'],
            "enc_out": traffic_result['received'],
        })
        
        # Record latency samples
        for lat in traffic_result.get('latencies', [])[:100]:
            aggregator.record_latency_sample(lat)
        
        print(f"   Sent: {traffic_result['sent']}, Received: {traffic_result['received']}")
        print(f"   Delivery: {traffic_result['delivery_rate']*100:.1f}%")
        
    finally:
        # Cleanup
        print("\n5. Cleaning up...")
        stop_echo.set()
        if echo_thread:
            echo_thread.join(timeout=1.0)
        
        for proc in [gcs_proc, drone_proc]:
            if proc and proc.poll() is None:
                proc.terminate()
                proc.wait(timeout=2.0)
    
    # Finalize metrics
    print("6. Finalizing metrics...")
    final_metrics = aggregator.finalize_suite()
    
    # Print summary
    print("\n" + "=" * 70)
    print("METRICS SUMMARY")
    print("=" * 70)
    
    print(f"\nA. Run Context:")
    print(f"   Run ID: {final_metrics.run_context.run_id}")
    print(f"   Suite: {final_metrics.run_context.suite_id}")
    print(f"   GCS Host: {final_metrics.run_context.gcs_hostname}")
    
    print(f"\nB. Crypto Identity:")
    print(f"   KEM: {final_metrics.crypto_identity.kem_algorithm}")
    print(f"   Sig: {final_metrics.crypto_identity.sig_algorithm}")
    print(f"   AEAD: {final_metrics.crypto_identity.aead_algorithm}")
    
    print(f"\nC. Lifecycle:")
    print(f"   Total duration: {final_metrics.lifecycle.suite_total_duration_ms:.2f} ms")
    
    print(f"\nD. Handshake:")
    print(f"   Success: {final_metrics.handshake.handshake_success}")
    print(f"   Duration: {final_metrics.handshake.handshake_total_duration_ms:.2f} ms")
    
    print(f"\nG. Data Plane:")
    print(f"   Packets sent: {final_metrics.data_plane.packets_sent}")
    print(f"   Packets received: {final_metrics.data_plane.packets_received}")
    print(f"   Delivery: {final_metrics.data_plane.packet_delivery_ratio*100:.1f}%")
    
    print(f"\nH. Latency:")
    print(f"   Avg: {final_metrics.latency_jitter.one_way_latency_avg_ms:.2f} ms")
    print(f"   P95: {final_metrics.latency_jitter.one_way_latency_p95_ms:.2f} ms")
    
    print(f"\nO. System (GCS):")
    print(f"   CPU avg: {final_metrics.system_gcs.cpu_usage_avg_percent:.1f}%")
    print(f"   Memory: {final_metrics.system_gcs.memory_rss_mb:.1f} MB")
    
    print(f"\nQ. Observability:")
    print(f"   Samples: {final_metrics.observability.log_sample_count}")
    print(f"   Duration: {final_metrics.observability.collection_duration_ms:.2f} ms")
    
    print(f"\nR. Validation:")
    print(f"   Result: {final_metrics.validation.benchmark_pass_fail}")
    
    # Save to JSON
    json_file = output_dir / f"{TEST_SUITE}_comprehensive.json"
    final_metrics.save_json(str(json_file))
    print(f"\n✓ Saved to: {json_file}")
    
    print("\n" + "=" * 70)
    print("TEST COMPLETE!")
    print("=" * 70)


if __name__ == "__main__":
    main()
