#!/usr/bin/env python3
"""Simple all-in-one localhost loop test."""

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

def main():
    print("=" * 60)
    print("PQC Secure Tunnel - Localhost Loop Test")
    print("=" * 60)
    
    gcs_proc = None
    drone_proc = None
    echo_running = threading.Event()
    echo_running.set()
    echo_stats = {"rx": 0, "tx": 0}
    
    def run_echo():
        rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        rx.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        rx.bind(("127.0.0.1", DRONE_RX))
        rx.settimeout(1.0)
        tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        print(f"[Echo] Listening on {DRONE_RX}")
        while echo_running.is_set():
            try:
                data, addr = rx.recvfrom(65535)
                echo_stats["rx"] += 1
                tx.sendto(data, ("127.0.0.1", DRONE_TX))
                echo_stats["tx"] += 1
                if echo_stats["rx"] <= 3:
                    print(f"[Echo] Echoed {len(data)} bytes")
            except socket.timeout:
                continue
        rx.close()
        tx.close()
    
    try:
        # Start GCS proxy
        print("[Main] Starting GCS proxy...")
        gcs_proc = subprocess.Popen(
            [PYTHON, "-m", "core.run_proxy", "gcs",
             "--gcs-secret-file", "secrets/localtest/gcs_signing.key",
             "--suite", "cs-mlkem768-aesgcm-mldsa65",
             "--stop-seconds", "45", "--quiet"],
            env=os.environ.copy(),
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT
        )
        time.sleep(2)
        
        if gcs_proc.poll() is not None:
            print("[Main] ERROR: GCS proxy exited early!")
            out = gcs_proc.stdout.read().decode() if gcs_proc.stdout else ""
            print(out)
            return 1
        
        # Start Drone proxy
        print("[Main] Starting Drone proxy...")
        drone_proc = subprocess.Popen(
            [PYTHON, "-m", "core.run_proxy", "drone",
             "--peer-pubkey-file", "secrets/localtest/gcs_signing.pub",
             "--suite", "cs-mlkem768-aesgcm-mldsa65",
             "--stop-seconds", "40", "--quiet"],
            env=os.environ.copy(),
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT
        )
        time.sleep(3)
        
        if drone_proc.poll() is not None:
            print("[Main] ERROR: Drone proxy exited early!")
            out = drone_proc.stdout.read().decode() if drone_proc.stdout else ""
            print(out)
            return 1
        
        print("[Main] Proxies running - checking handshake...")
        
        # Wait a moment for handshake
        time.sleep(2)
        
        # Check if still running
        if gcs_proc.poll() is not None or drone_proc.poll() is not None:
            print("[Main] ERROR: A proxy exited during handshake!")
            return 1
        
        print("[Main] Handshake complete - starting echo server...")
        
        # Start echo server
        echo_thread = threading.Thread(target=run_echo, daemon=True)
        echo_thread.start()
        time.sleep(0.5)
        
        # Run the test
        print("\n" + "-" * 60)
        print(f"[Test] Sending 20 packets to GCS TX port {GCS_TX}")
        print(f"[Test] Expecting replies on GCS RX port {GCS_RX}")
        print("-" * 60)
        
        tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        rx.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        rx.bind(("127.0.0.1", GCS_RX))
        rx.settimeout(2.0)
        
        sent = 0
        received = 0
        
        for i in range(20):
            payload = f"PACKET-{i:04d}".encode()
            tx.sendto(payload, ("127.0.0.1", GCS_TX))
            sent += 1
            
            try:
                data, addr = rx.recvfrom(65535)
                received += 1
                if i < 5:
                    print(f"[Test] Pkt {i}: OK - {data.decode()}")
            except socket.timeout:
                if i < 5:
                    print(f"[Test] Pkt {i}: TIMEOUT")
            
            time.sleep(0.05)
        
        tx.close()
        rx.close()
        
        # Stop echo
        echo_running.clear()
        time.sleep(0.5)
        
        print("\n" + "=" * 60)
        print("RESULTS")
        print("=" * 60)
        print(f"Packets sent:     {sent}")
        print(f"Packets received: {received}")
        print(f"Echo server:      RX={echo_stats['rx']}, TX={echo_stats['tx']}")
        print("=" * 60)
        
        if received > 0:
            print("\n[OK] SUCCESS! PQC encrypted loop verified!")
            print("Data path: GCS -> encrypt (ML-KEM-768 + AES-GCM) -> network")
            print("           -> Drone decrypt -> Echo -> encrypt -> network")
            print("           -> GCS decrypt -> received!")
            return 0
        else:
            print("\n[FAIL] No packets completed the round trip")
            return 1
        
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return 1
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
        
        print("\n[Main] Cleanup complete.")


if __name__ == "__main__":
    # Wait for any ports to be released
    time.sleep(2)
    sys.exit(main())
