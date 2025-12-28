#!/usr/bin/env python3
"""
Validation script for GCS Telemetry v1.
Starts the collector and a synthetic traffic generator.
"""

import sys
import time
import json
import socket
import threading
import logging
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sscheduler.gcs_metrics import GcsMetricsCollector

SNIFF_PORT = 14552

def traffic_generator(running_event):
    """Generates synthetic UDP traffic to sniff port"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    seq = 0
    print(f"Traffic generator started, targeting 127.0.0.1:{SNIFF_PORT}")
    
    while running_event.is_set():
        # Simulate 10Hz traffic
        msg = f"synthetic_packet_{seq}".encode()
        try:
            sock.sendto(msg, ("127.0.0.1", SNIFF_PORT))
        except Exception:
            pass
        seq += 1
        time.sleep(0.1)

def main():
    logging.basicConfig(level=logging.INFO)
    
    print("Initializing GCS Metrics Collector v1...")
    collector = GcsMetricsCollector(
        mavlink_host="127.0.0.1",
        mavlink_port=SNIFF_PORT
    )
    
    running_event = threading.Event()
    running_event.set()
    
    # Start traffic generator
    gen_thread = threading.Thread(target=traffic_generator, args=(running_event,), daemon=True)
    gen_thread.start()
    
    try:
        collector.start()
        print("Collector started. Running for 10 seconds...")
        
        for i in range(10):
            time.sleep(1.0)
            snapshot = collector.get_snapshot()
            
            # Print key metrics
            sniff = snapshot['metrics']['sniff']
            sys_stats = snapshot['metrics']['sys']
            print(f"[{i+1}s] PPS={sniff['rx_pps']} GapMax={sniff['gap_max_ms']}ms CPU={sys_stats['cpu_pct']}%")
            
            # Verify schema
            if snapshot.get("schema") != "uav.pqc.telemetry.v1":
                print("ERROR: Schema mismatch!")
                
    except KeyboardInterrupt:
        print("Interrupted")
    finally:
        print("Stopping...")
        running_event.clear()
        collector.stop()
        gen_thread.join(timeout=1.0)
        print("Done.")

if __name__ == "__main__":
    main()
