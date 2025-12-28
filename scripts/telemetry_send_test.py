#!/usr/bin/env python3
"""
Telemetry Sender Doctor (GCS Side)
Sends valid uav.pqc.telemetry.v1 packets to the Drone to verify network connectivity.
"""

import socket
import time
import json
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.config import CONFIG

DRONE_HOST = CONFIG.get("DRONE_HOST")
PORT = CONFIG.get("GCS_TELEMETRY_PORT", 52080)

def main():
    print(f"--- Telemetry Sender Doctor ---")
    print(f"Target: {DRONE_HOST}:{PORT}")
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    seq = 0
    try:
        while True:
            seq += 1
            now_mono = time.monotonic()
            now_wall = time.time()
            
            packet = {
                "schema": "uav.pqc.telemetry.v1",
                "schema_ver": 1,
                "sender": {
                    "role": "gcs",
                    "node_id": "doctor_test",
                    "pid": 12345
                },
                "t": {
                    "wall_ms": now_wall * 1000.0,
                    "mono_ms": now_mono * 1000.0,
                    "boot_id": int(now_wall)
                },
                "state": {
                    "suite": {
                        "active_suite": "test-suite-123",
                        "suite_epoch": 1
                    }
                },
                "metrics": {
                    "sys": {"cpu_pct": 10.5},
                    "sniff": {"rx_pps": 50.0}
                },
                "seq": seq
            }
            
            payload = json.dumps(packet).encode('utf-8')
            sock.sendto(payload, (DRONE_HOST, PORT))
            
            print(f"Sent seq={seq} size={len(payload)} to {DRONE_HOST}:{PORT}")
            time.sleep(0.1) # 10 Hz
            
            if seq >= 50:
                break
                
    except KeyboardInterrupt:
        pass
    finally:
        sock.close()
        print("Done.")

if __name__ == "__main__":
    main()
