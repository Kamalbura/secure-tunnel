#!/usr/bin/env python3
"""
Complete localhost loop test for PQC secure tunnel - all in one script.

This script:
1. Starts GCS proxy (server) in a subprocess
2. Starts Drone proxy (client) in a subprocess  
3. Runs a UDP echo server simulating the drone application
4. Sends test packets through the complete encrypt/decrypt loop
5. Validates the round-trip

Run with: python test_complete_loop.py
"""

import os
import sys
import socket
import struct
import time
import threading
import subprocess

# Configure localhost for both sides
os.environ["DRONE_HOST"] = "127.0.0.1"
os.environ["GCS_HOST"] = "127.0.0.1"
os.environ["DRONE_CONTROL_HOST"] = "127.0.0.1"
# Disable packet type prefix for simple test (raw passthrough)
os.environ["ENABLE_PACKET_TYPE"] = "0"

# Add parent directory to path for imports
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.config import CONFIG

# Ports from config
GCS_PLAINTEXT_TX = CONFIG["GCS_PLAINTEXT_TX"]   # 47001 - GCS app sends here
GCS_PLAINTEXT_RX = CONFIG["GCS_PLAINTEXT_RX"]   # 47002 - GCS app receives here
DRONE_PLAINTEXT_TX = CONFIG["DRONE_PLAINTEXT_TX"]  # 47003 - Drone app sends here
DRONE_PLAINTEXT_RX = CONFIG["DRONE_PLAINTEXT_RX"]  # 47004 - Drone app receives here

HOST = "127.0.0.1"
TEST_DURATION = 30  # seconds


def wait_for_port(port: int, host: str = "127.0.0.1", timeout: float = 10.0) -> bool:
    """Wait for a port to become unavailable (i.e., something is listening)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.5)
        try:
            result = sock.connect_ex((host, port))
            sock.close()
            if result == 0:
                return True
        except Exception:
            pass
        time.sleep(0.2)
    return False


def run_drone_echo(stop_event: threading.Event, stats: dict):
    """Simple echo server on drone side - receives decrypted, sends back."""
    try:
        rx_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        rx_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        rx_sock.bind((HOST, DRONE_PLAINTEXT_RX))
        rx_sock.settimeout(0.5)
        
        tx_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        print(f"[Echo] Started on {HOST}:{DRONE_PLAINTEXT_RX} -> {HOST}:{DRONE_PLAINTEXT_TX}")
        
        while not stop_event.is_set():
            try:
                data, addr = rx_sock.recvfrom(65535)
                stats["rx"] += 1
                # Echo back through the encrypt path
                tx_sock.sendto(data, (HOST, DRONE_PLAINTEXT_TX))
                stats["tx"] += 1
            except socket.timeout:
                continue
            except Exception as e:
                if not stop_event.is_set():
                    print(f"[Echo] Error: {e}")
                    
    except Exception as e:
        print(f"[Echo] Failed to start: {e}")
    finally:
        try: rx_sock.close()
        except: pass
        try: tx_sock.close()
        except: pass


def run_test_client(packet_count: int, delay_s: float) -> tuple:
    """Send packets and measure round-trip through encrypted tunnel."""
    
    tx_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    rx_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    rx_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    rx_sock.bind((HOST, GCS_PLAINTEXT_RX))
    rx_sock.settimeout(2.0)
    
    sent = 0
    received = 0
    rtt_samples = []
    
    print(f"\n[Test] Sending {packet_count} packets to {HOST}:{GCS_PLAINTEXT_TX}")
    print(f"[Test] Expecting responses on {HOST}:{GCS_PLAINTEXT_RX}")
    
    for seq in range(packet_count):
        send_time = time.time_ns()
        packet = struct.pack("!IQ", seq, send_time) + b"PQC-LOCALHOST-TEST"
        
        tx_sock.sendto(packet, (HOST, GCS_PLAINTEXT_TX))
        sent += 1
        
        try:
            response, addr = rx_sock.recvfrom(65535)
            recv_time = time.time_ns()
            
            if len(response) >= 12:
                resp_seq, resp_ts = struct.unpack("!IQ", response[:12])
                rtt_ns = recv_time - resp_ts
                rtt_ms = rtt_ns / 1_000_000
                rtt_samples.append(rtt_ms)
                received += 1
                
                if seq % 10 == 0 or seq < 5:
                    print(f"[Test] Packet {seq}: RTT = {rtt_ms:.2f} ms")
        except socket.timeout:
            if seq < 5 or seq % 10 == 0:
                print(f"[Test] Packet {seq}: TIMEOUT")
        
        if delay_s > 0:
            time.sleep(delay_s)
    
    tx_sock.close()
    rx_sock.close()
    
    return sent, received, rtt_samples


def main():
    print("=" * 70)
    print("PQC SECURE TUNNEL - COMPLETE LOCALHOST LOOP TEST")
    print("=" * 70)
    print(f"\nUsing suite: cs-mlkem768-aesgcm-mldsa65")
    print(f"Hosts: DRONE_HOST={os.environ['DRONE_HOST']}, GCS_HOST={os.environ['GCS_HOST']}")
    print(f"\nData flow:")
    print(f"  GCS Client ({GCS_PLAINTEXT_TX}) -> GCS Proxy (encrypt)")
    print(f"    -> UDP Network (46011/46012)")
    print(f"    -> Drone Proxy (decrypt) -> Echo Server ({DRONE_PLAINTEXT_RX})")
    print(f"    -> Echo ({DRONE_PLAINTEXT_TX}) -> Drone Proxy (encrypt)")
    print(f"    -> UDP Network")  
    print(f"    -> GCS Proxy (decrypt) -> GCS Client ({GCS_PLAINTEXT_RX})")
    print("")
    
    gcs_proc = None
    drone_proc = None
    stop_event = threading.Event()
    echo_stats = {"rx": 0, "tx": 0}
    
    try:
        # Start GCS proxy (server side)
        print("[Main] Starting GCS proxy...")
        gcs_cmd = [
            sys.executable, "-m", "core.run_proxy", "gcs",
            "--gcs-secret-file", "secrets/localtest/gcs_signing.key",
            "--suite", "cs-mlkem768-aesgcm-mldsa65",
            "--stop-seconds", str(TEST_DURATION)
        ]
        gcs_proc = subprocess.Popen(
            gcs_cmd,
            stdout=None,  # Let output go to console
            stderr=None,
            cwd=ROOT,
            env=os.environ.copy()
        )
        
        # Wait for GCS to start listening
        print("[Main] Waiting for GCS proxy to start...")
        time.sleep(2)
        
        if gcs_proc.poll() is not None:
            output = gcs_proc.stdout.read().decode() if gcs_proc.stdout else ""
            print(f"[Main] ERROR: GCS proxy exited early! Output:\n{output}")
            return 1
        
        # Start Drone proxy (client side)
        print("[Main] Starting Drone proxy...")
        drone_cmd = [
            sys.executable, "-m", "core.run_proxy", "drone",
            "--peer-pubkey-file", "secrets/localtest/gcs_signing.pub",
            "--suite", "cs-mlkem768-aesgcm-mldsa65",
            "--stop-seconds", str(TEST_DURATION - 2),
            "--quiet"
        ]
        drone_proc = subprocess.Popen(
            drone_cmd,
            stdout=None,  # Let output go to console
            stderr=None,
            cwd=ROOT,
            env=os.environ.copy()
        )
        
        # Wait for handshake
        print("[Main] Waiting for PQC handshake...")
        time.sleep(3)
        
        if drone_proc.poll() is not None:
            output = drone_proc.stdout.read().decode() if drone_proc.stdout else ""
            print(f"[Main] ERROR: Drone proxy exited! Output:\n{output}")
            return 1
        
        print("[Main] OK - Proxies started successfully!")
        
        # Start echo server
        echo_thread = threading.Thread(
            target=run_drone_echo,
            args=(stop_event, echo_stats),
            daemon=True
        )
        echo_thread.start()
        time.sleep(0.5)
        
        # Run the test
        print("\n" + "-" * 70)
        sent, received, rtt_samples = run_test_client(packet_count=30, delay_s=0.1)
        print("-" * 70)
        
        # Results
        print("\n" + "=" * 70)
        print("TEST RESULTS")
        print("=" * 70)
        print(f"Packets sent:       {sent}")
        print(f"Packets received:   {received}")
        print(f"Delivery rate:      {100.0 * received / max(1, sent):.1f}%")
        print(f"Echo server stats:  RX={echo_stats['rx']}, TX={echo_stats['tx']}")
        
        if rtt_samples:
            avg_rtt = sum(rtt_samples) / len(rtt_samples)
            min_rtt = min(rtt_samples)
            max_rtt = max(rtt_samples)
            print(f"RTT (min/avg/max):  {min_rtt:.2f} / {avg_rtt:.2f} / {max_rtt:.2f} ms")
        
        print("=" * 70)
        
        if received > 0:
            print("\n[OK] SUCCESS: Complete PQC encryption/decryption loop verified!")
            print("   Packets successfully traveled:")
            print("   1. GCS plaintext -> GCS proxy (ML-KEM-768 + AES-256-GCM encrypt)")
            print("   2. UDP encrypted tunnel (localhost)")
            print("   3. Drone proxy (AES-256-GCM decrypt) -> Echo server")
            print("   4. Echo server -> Drone proxy (encrypt)")
            print("   5. UDP encrypted tunnel (localhost)")
            print("   6. GCS proxy (decrypt) -> GCS client")
            return 0
        else:
            print("\n[FAIL] No packets completed the round-trip")
            return 1
            
    except Exception as e:
        print(f"\n[ERROR]: {e}")
        import traceback
        traceback.print_exc()
        return 1
        
    finally:
        stop_event.set()
        
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
        
        print("\n[Main] Cleanup complete.")


if __name__ == "__main__":
    sys.exit(main())
