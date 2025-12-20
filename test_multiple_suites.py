#!/usr/bin/env python3
"""Test multiple PQC cipher suites on localhost."""

import os
import sys
import socket
import subprocess
import threading
import time

# Set environment
os.environ["DRONE_HOST"] = "127.0.0.1"
os.environ["GCS_HOST"] = "127.0.0.1"
os.environ["ENABLE_PACKET_TYPE"] = "0"

ROOT = os.path.dirname(os.path.abspath(__file__))
PYTHON = sys.executable

# Ports
GCS_TX = 47001
GCS_RX = 47002
DRONE_RX = 47004
DRONE_TX = 47003

# Test suites with different algorithms (all have keys in secrets/matrix/)
TEST_SUITES = [
    "cs-mlkem512-aesgcm-falcon512",        # ML-KEM-512 + AES-GCM + Falcon-512 (NIST L1)
    "cs-hqc128-aesgcm-mldsa44",            # HQC-128 + AES-GCM + ML-DSA-44 (NIST L1)
    "cs-hqc192-aesgcm-mldsa65",            # HQC-192 + AES-GCM + ML-DSA-65 (NIST L3)
]


def wait_for_port_free(port, timeout=10):
    """Wait for a port to be free."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.bind(("127.0.0.1", port))
            sock.close()
            return True
        except OSError:
            time.sleep(0.5)
    return False


def test_suite(suite_id):
    """Test a single cipher suite."""
    gcs_proc = None
    drone_proc = None
    echo_running = threading.Event()
    echo_running.set()
    echo_stats = {"rx": 0, "tx": 0}
    
    # Check for keys
    key_file = os.path.join(ROOT, f"secrets/matrix/{suite_id}/gcs_signing.key")
    pub_file = os.path.join(ROOT, f"secrets/matrix/{suite_id}/gcs_signing.pub")
    
    if not os.path.exists(key_file) or not os.path.exists(pub_file):
        return None, f"Missing keys for {suite_id}"
    
    def run_echo():
        rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        rx.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        rx.bind(("127.0.0.1", DRONE_RX))
        rx.settimeout(1.0)
        tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        while echo_running.is_set():
            try:
                data, addr = rx.recvfrom(65535)
                echo_stats["rx"] += 1
                tx.sendto(data, ("127.0.0.1", DRONE_TX))
                echo_stats["tx"] += 1
            except socket.timeout:
                continue
        rx.close()
        tx.close()
    
    try:
        # Start GCS proxy
        gcs_proc = subprocess.Popen(
            [PYTHON, "-m", "core.run_proxy", "gcs",
             "--gcs-secret-file", key_file,
             "--suite", suite_id,
             "--stop-seconds", "30", "--quiet"],
            env=os.environ.copy(),
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT
        )
        time.sleep(2)
        
        if gcs_proc.poll() is not None:
            out = gcs_proc.stdout.read().decode() if gcs_proc.stdout else ""
            return False, f"GCS proxy exited: {out[:200]}"
        
        # Start Drone proxy
        drone_proc = subprocess.Popen(
            [PYTHON, "-m", "core.run_proxy", "drone",
             "--peer-pubkey-file", pub_file,
             "--suite", suite_id,
             "--stop-seconds", "25", "--quiet"],
            env=os.environ.copy(),
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT
        )
        time.sleep(3)
        
        if drone_proc.poll() is not None:
            out = drone_proc.stdout.read().decode() if drone_proc.stdout else ""
            return False, f"Drone proxy exited: {out[:200]}"
        
        # Start echo server
        echo_thread = threading.Thread(target=run_echo, daemon=True)
        echo_thread.start()
        time.sleep(0.5)
        
        # Run test packets
        tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        rx.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        rx.bind(("127.0.0.1", GCS_RX))
        rx.settimeout(2.0)
        
        sent = 0
        received = 0
        
        for i in range(10):
            payload = f"TEST-{i:04d}".encode()
            tx.sendto(payload, ("127.0.0.1", GCS_TX))
            sent += 1
            
            try:
                data, addr = rx.recvfrom(65535)
                received += 1
            except socket.timeout:
                pass
            
            time.sleep(0.05)
        
        tx.close()
        rx.close()
        
        # Stop echo
        echo_running.clear()
        time.sleep(0.3)
        
        if received >= 8:  # Allow some packet loss
            return True, f"OK ({received}/{sent} packets)"
        else:
            return False, f"Low delivery ({received}/{sent} packets)"
        
    except Exception as e:
        return False, str(e)
    finally:
        echo_running.clear()
        
        if drone_proc and drone_proc.poll() is None:
            drone_proc.terminate()
            try:
                drone_proc.wait(timeout=3)
            except:
                drone_proc.kill()
        
        if gcs_proc and gcs_proc.poll() is None:
            gcs_proc.terminate()
            try:
                gcs_proc.wait(timeout=3)
            except:
                gcs_proc.kill()


def main():
    print("=" * 70)
    print("PQC Secure Tunnel - Multi-Suite Localhost Test")
    print("=" * 70)
    print()
    
    results = []
    
    for suite_id in TEST_SUITES:
        print(f"Testing: {suite_id}")
        print("-" * 70)
        
        # Wait for ports to be free
        for port in [GCS_RX, GCS_TX, DRONE_RX, DRONE_TX]:
            if not wait_for_port_free(port, timeout=5):
                print(f"  [WARN] Port {port} still in use, proceeding anyway...")
        
        success, message = test_suite(suite_id)
        
        if success is None:
            status = "SKIP"
            results.append((suite_id, "SKIP", message))
        elif success:
            status = "PASS"
            results.append((suite_id, "PASS", message))
        else:
            status = "FAIL"
            results.append((suite_id, "FAIL", message))
        
        print(f"  [{status}] {message}")
        print()
        
        # Wait between suites
        time.sleep(3)
    
    # Summary
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    passed = sum(1 for r in results if r[1] == "PASS")
    failed = sum(1 for r in results if r[1] == "FAIL")
    skipped = sum(1 for r in results if r[1] == "SKIP")
    
    for suite_id, status, message in results:
        print(f"  [{status:4}] {suite_id}")
    
    print()
    print(f"Total: {len(results)}, Passed: {passed}, Failed: {failed}, Skipped: {skipped}")
    print("=" * 70)
    
    if failed > 0:
        return 1
    return 0


if __name__ == "__main__":
    time.sleep(2)  # Wait for ports to release
    sys.exit(main())
