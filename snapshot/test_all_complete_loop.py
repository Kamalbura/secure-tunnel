#!/usr/bin/env python3
"""
Run complete localhost loop for all available suites in secrets/matrix.
For each suite:
 - start GCS proxy
 - start Drone proxy
 - start drone plaintext echo server
 - send UDP traffic from a sender at target bandwidth for duration
 - measure delivery (GCS plaintext RX receives)

Usage: python test_all_complete_loop.py --duration 10 --rate 110
"""
import os
import sys
import time
import socket
import struct
import threading
import subprocess
from pathlib import Path
import argparse

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from core.config import CONFIG
from core.suites import list_suites

# Ports
GCS_PLAINTEXT_TX = CONFIG["GCS_PLAINTEXT_TX"]
GCS_PLAINTEXT_RX = CONFIG["GCS_PLAINTEXT_RX"]
DRONE_PLAINTEXT_TX = CONFIG["DRONE_PLAINTEXT_TX"]
DRONE_PLAINTEXT_RX = CONFIG["DRONE_PLAINTEXT_RX"]
HOST = "127.0.0.1"

SECRETS_DIR = ROOT / "secrets" / "matrix"

PAYLOAD_SIZE = 1200


def run_echo(stop_event, stats):
    rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    rx.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    rx.bind((HOST, DRONE_PLAINTEXT_RX))
    rx.settimeout(0.5)
    tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        while not stop_event.is_set():
            try:
                data, addr = rx.recvfrom(65535)
                stats['rx'] += 1
                tx.sendto(data, (HOST, DRONE_PLAINTEXT_TX))
                stats['tx'] += 1
            except socket.timeout:
                continue
    finally:
        rx.close(); tx.close()


def traffic_sender(duration_s, rate_mbps, result):
    """Send UDP packets to GCS_PLAINTEXT_TX for duration seconds and count responses at GCS_PLAINTEXT_RX."""
    tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    rx.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    rx.bind((HOST, GCS_PLAINTEXT_RX))
    rx.settimeout(1.0)

    pps = (rate_mbps * 1_000_000) / (8 * PAYLOAD_SIZE)
    if pps < 1:
        pps = 1
    interval = 1.0 / pps

    sent = 0
    received = 0
    end = time.time() + duration_s
    seq = 0

    while time.time() < end:
        send_time = time.time_ns()
        payload = struct.pack("!IQ", seq, send_time) + b"PQC-ALL-LOOP"
        try:
            tx.sendto(payload, (HOST, GCS_PLAINTEXT_TX))
            sent += 1
        except Exception:
            pass
        # try receive (non-blocking-ish)
        t0 = time.time()
        while time.time() - t0 < interval:
            try:
                data, addr = rx.recvfrom(65535)
                if len(data) >= 12:
                    received += 1
            except socket.timeout:
                break
            except Exception:
                break
        seq += 1
    tx.close(); rx.close()
    result['sent'] = sent
    result['received'] = received


def run_suite(suite_name, duration, rate):
    print('\n' + '='*60)
    print(f"Suite: {suite_name}")
    suite_dir = SECRETS_DIR / suite_name
    gcs_key = suite_dir / 'gcs_signing.key'
    gcs_pub = suite_dir / 'gcs_signing.pub'
    if not gcs_key.exists() or not gcs_pub.exists():
        print(f"  Skipping {suite_name}: missing keys in {suite_dir}")
        return {'suite': suite_name, 'status': 'skipped'}

    # Start GCS proxy
    gcs_cmd = [sys.executable, '-m', 'core.run_proxy', 'gcs', '--suite', suite_name, '--gcs-secret-file', str(gcs_key), '--quiet']
    gcs_proc = subprocess.Popen(gcs_cmd, cwd=ROOT, env=os.environ.copy())
    time.sleep(2.0)
    if gcs_proc.poll() is not None:
        print('  GCS proxy exited early')
        return {'suite': suite_name, 'status': 'gcs_failed'}

    # Start Drone proxy
    drone_cmd = [sys.executable, '-m', 'core.run_proxy', 'drone', '--suite', suite_name, '--peer-pubkey-file', str(gcs_pub), '--quiet']
    drone_proc = subprocess.Popen(drone_cmd, cwd=ROOT, env=os.environ.copy())
    time.sleep(3.0)
    if drone_proc.poll() is not None:
        print('  Drone proxy exited early')
        gcs_proc.terminate(); gcs_proc.wait(timeout=2)
        return {'suite': suite_name, 'status': 'drone_failed'}

    # Start echo
    stop_event = threading.Event()
    echo_stats = {'rx': 0, 'tx': 0}
    echo_thread = threading.Thread(target=run_echo, args=(stop_event, echo_stats), daemon=True)
    echo_thread.start()
    time.sleep(0.5)

    # Start traffic sender and measure
    result = {'sent': 0, 'received': 0}
    traffic_thread = threading.Thread(target=traffic_sender, args=(duration, rate, result), daemon=True)
    traffic_thread.start()
    traffic_thread.join(timeout=duration + 5)

    # Stop
    stop_event.set()
    time.sleep(0.2)

    # Cleanup procs
    if drone_proc.poll() is None:
        drone_proc.terminate();
        try: drone_proc.wait(timeout=2)
        except: drone_proc.kill()
    if gcs_proc.poll() is None:
        gcs_proc.terminate();
        try: gcs_proc.wait(timeout=2)
        except: gcs_proc.kill()

    sent = result.get('sent', 0)
    received = result.get('received', 0)
    delivery = 0.0 if sent==0 else 100.0 * received / sent
    print(f"  Sent: {sent}, Received: {received}, Delivery: {delivery:.1f}%")
    print(f"  Echo stats: RX={echo_stats['rx']}, TX={echo_stats['tx']}")
    status = 'pass' if received>0 else 'fail'
    return {'suite': suite_name, 'status': status, 'sent': sent, 'received': received, 'delivery': delivery}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--duration', type=float, default=10.0)
    parser.add_argument('--rate', type=float, default=110.0)
    parser.add_argument('--limit', type=int, default=None)
    args = parser.parse_args()

    suites = list_suites()
    suite_names = list(suites.keys())
    if args.limit:
        suite_names = suite_names[:args.limit]

    results = []
    for s in suite_names:
        res = run_suite(s, args.duration, args.rate)
        results.append(res)

    # Summary
    print('\n' + '='*60)
    print('SUMMARY')
    for r in results:
        print(f"{r['suite']}: {r.get('status')} - sent={r.get('sent',0)} rx={r.get('received',0)} delivery={r.get('delivery',0):.1f}%")

    return 0

if __name__ == '__main__':
    sys.exit(main())
