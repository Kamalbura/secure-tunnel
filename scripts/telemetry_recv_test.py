#!/usr/bin/env python3
"""
Telemetry Receiver Doctor (Drone Side)
Receives and validates uav.pqc.telemetry.v1 packets from GCS.
"""

import socket
import time
import json
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.config import CONFIG

GCS_HOST = CONFIG.get("GCS_HOST")
PORT = CONFIG.get("GCS_TELEMETRY_PORT", 52080)

def main():
    print(f"--- Telemetry Receiver Doctor ---")
    print(f"Listening on 0.0.0.0:{PORT}")
    print(f"Expecting packets from: {GCS_HOST}")
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("0.0.0.0", PORT))
    
    last_seq = -1
    
    try:
        while True:
            data, addr = sock.recvfrom(4096)
            sender_ip = addr[0]
            
            if sender_ip != GCS_HOST:
                print(f"DROP: Packet from unauthorized IP {sender_ip}")
                continue
                
            if len(data) > 2048:
                print(f"DROP: Packet too large ({len(data)} bytes)")
                continue
                
            try:
                packet = json.loads(data.decode('utf-8'))
            except json.JSONDecodeError:
                print(f"INVALID: JSON decode failed")
                continue
                
            # Schema validation
            if packet.get("schema") != "uav.pqc.telemetry.v1":
                print(f"INVALID: Wrong schema {packet.get('schema')}")
                continue
                
            seq = packet.get("seq", 0)
            age_ms = (time.time() * 1000.0) - packet.get("t", {}).get("wall_ms", 0)
            
            status = "OK"
            if last_seq != -1 and seq != last_seq + 1:
                status = "SEQ_JUMP"
            
            print(f"RX {status}: seq={seq} age={age_ms:.1f}ms from={sender_ip} suite={packet.get('state',{}).get('suite',{}).get('active_suite')}")
            
            last_seq = seq
            
    except KeyboardInterrupt:
        pass
    finally:
        sock.close()
        print("Done.")

if __name__ == "__main__":
    main()
