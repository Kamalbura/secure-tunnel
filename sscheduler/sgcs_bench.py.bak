#!/usr/bin/env python3
"""
Benchmark GCS Scheduler - sscheduler/sgcs_bench.py
"Operation Chronos": Scientific Instrumentation Layer.

Directives:
1. Telemetry Listener: Intercept JSON packets (UDP 47002).
2. Logger: Write latency/jitter to benchmarks/comprehensive_session.jsonl.
3. Controller: Accept commands from Drone.
"""

import os
import sys
import time
import json
import socket
import threading
import logging
from pathlib import Path
from collections import deque
from typing import Dict, Any

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import CONFIG
from core.run_proxy import GcsProxyManager
from core.suites import get_suite

# =============================================================================
# Configuration
# =============================================================================

GCS_CONTROL_HOST = str(CONFIG.get("GCS_CONTROL_BIND_HOST", "0.0.0.0"))
GCS_CONTROL_PORT = int(CONFIG.get("GCS_CONTROL_PORT", 48080))
GCS_PLAIN_RX_PORT = int(CONFIG.get("GCS_PLAINTEXT_RX", 47002))

LOGS_DIR = Path(__file__).parent.parent / "logs" / "benchmarks"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
SESSION_LOG = LOGS_DIR / "comprehensive_session.jsonl"

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [sgcs-bench] %(message)s',
    datefmt='%Y-%m-%dT%H:%M:%SZ'
)

def log(msg):
    logging.info(msg)

# =============================================================================
# JSON Telemetry Listener (The Scientist)
# =============================================================================

class JsonChronosListener:
    def __init__(self, port: int, output_file: Path):
        self.port = port
        self.output_file = output_file
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("0.0.0.0", port))
        self.running = True
        self.packet_count = 0
        
    def run(self):
        log(f"Chronos Listener sniffing on UDP {self.port}...")
        with open(self.output_file, "a") as f:
            while self.running:
                try:
                    data, addr = self.sock.recvfrom(4096)
                    recv_ts = time.time()
                    
                    try:
                        packet = json.loads(data.decode("utf-8"))
                        
                        # Calculate Metrics
                        sent_ts = packet.get("ts", recv_ts)
                        latency_ms = (recv_ts - sent_ts) * 1000.0
                        
                        # Augment
                        packet["recv_ts"] = recv_ts
                        packet["latency_ms"] = latency_ms
                        
                        # Write to Disk
                        f.write(json.dumps(packet) + "\n")
                        f.flush()
                        
                        self.packet_count += 1
                        if self.packet_count % 10 == 0:
                            log(f"RX: {self.packet_count} | Latency: {latency_ms:.2f}ms | Suite: {packet.get('suite')}")
                            
                    except json.JSONDecodeError:
                        log("WARN: Received non-JSON packet")
                        
                except Exception as e:
                    if self.running:
                        log(f"Listener Error: {e}")

    def stop(self):
        self.running = False
        self.sock.close()

# =============================================================================
# Control Server (The Servant)
# =============================================================================

class ControlServer:
    def __init__(self, proxy: GcsProxyManager):
        self.proxy = proxy
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((GCS_CONTROL_HOST, GCS_CONTROL_PORT))
        self.sock.listen(5)
        self.running = True
        
    def run(self):
        log(f"Control Server listening on {GCS_CONTROL_PORT}")
        while self.running:
            try:
                client, addr = self.sock.accept()
                threading.Thread(target=self._handle_client, args=(client,), daemon=True).start()
            except Exception as e:
                if self.running:
                    log(f"Accept Error: {e}")
                    
    def _handle_client(self, client):
        try:
            data = b""
            while True:
                chunk = client.recv(4096)
                if not chunk: break
                data += chunk
                if b"\n" in data: break
            
            req = json.loads(data.decode())
            resp = self._process_command(req)
            client.sendall(json.dumps(resp).encode() + b"\n")
            
        except Exception as e:
            log(f"Client Error: {e}")
        finally:
            client.close()

    def _process_command(self, req: dict) -> dict:
        cmd = req.get("cmd")
        
        if cmd == "start_proxy":
            suite = req.get("suite")
            log(f"CMD: start_proxy({suite})")
            if self.proxy.start(suite):
                return {"status": "ok"}
            return {"status": "error"}
            
        elif cmd == "prepare_rekey":
            log("CMD: prepare_rekey")
            self.proxy.stop()
            return {"status": "ok"}
            
        return {"status": "error", "message": "unknown_cmd"}

    def stop(self):
        self.running = False
        self.sock.close()

# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    # Clean env
    # (Simplified for bench)
    
    proxy = GcsProxyManager()
    server = ControlServer(proxy)
    listener = JsonChronosListener(GCS_PLAIN_RX_PORT, SESSION_LOG)
    
    t_server = threading.Thread(target=server.run, daemon=True)
    t_listener = threading.Thread(target=listener.run, daemon=True)
    
    t_server.start()
    t_listener.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log("Stopping...")
        server.stop()
        listener.stop()
        proxy.stop()
