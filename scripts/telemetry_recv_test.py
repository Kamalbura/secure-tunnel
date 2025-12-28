#!/usr/bin/env python3
"""
Telemetry Receiver Doctor (Drone Side)
Receives and validates uav.pqc.telemetry.v1 packets from GCS.
Strictly mirrors safety logic in sscheduler/sdrone.py.
"""

import socket
import time
import json
import sys
from pathlib import Path

# Add parent to path to load config
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.config import CONFIG

# Configuration mirroring sdrone.py
GCS_HOST = CONFIG.get("GCS_HOST")
PORT = int(CONFIG.get("GCS_TELEMETRY_PORT", 52080))
MAX_PACKET_SIZE = 8192
SCHEMA = "uav.pqc.telemetry.v1"

def main():
    print(f"--- Telemetry Receiver Doctor ---")
    print(f"Listening on 0.0.0.0:{PORT}")
    print(f"Allow-list IP: {GCS_HOST}")
    print(f"Max Packet Size: {MAX_PACKET_SIZE}")
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("0.0.0.0", PORT))
    
    last_seq = -1
    
    try:
        while True:
            data, addr = sock.recvfrom(65535)
            sender_ip = addr[0]
            
            # 1. IP Safety Gate
            if sender_ip != GCS_HOST:
                print(f"DROP: Packet from unauthorized IP {sender_ip}")
                continue
                
            # 2. Size Safety Gate
            if len(data) > MAX_PACKET_SIZE:
                print(f"DROP: Packet too large ({len(data)} bytes)")
                continue
                
            try:
                packet = json.loads(data.decode('utf-8'))
            except json.JSONDecodeError:
                print(f"INVALID: JSON decode failed")
                continue
                
            # 3. Schema Safety Gate
            if packet.get("schema") != SCHEMA:
                print(f"INVALID: Wrong schema {packet.get('schema')}")
                continue
            
            if packet.get("schema_ver") != 1:
                print(f"INVALID: Wrong schema version {packet.get('schema_ver')}")
                continue
                
            # Metrics
            seq = packet.get("seq", 0)
            wall_ms = packet.get("t", {}).get("wall_ms", 0)
            age_ms = (time.time() * 1000.0) - wall_ms
            active_suite = packet.get('state',{}).get('suite',{}).get('active_suite')
            
            status = "OK"
            if last_seq != -1 and seq != last_seq + 1:
                status = "SEQ_JUMP"
            
            print(f"RX {status}: seq={seq:<6} age={age_ms:>5.1f}ms size={len(data):<4} suite={active_suite}")
            
            last_seq = seq
            
    except KeyboardInterrupt:
        pass
    finally:
        sock.close()
        print("Done.")

if __name__ == "__main__":
    main()
