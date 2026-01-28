import sys
import socket
import json
import time

# Host is from config or arg, we'll try 100.x based on user prompt or default
# User prompt: "gcs this computer how to reach drone its on reachable at ssh dev@100.101.93.23"
# Reverse direction (Drone -> GCS) might be different IP or same subnet.
# We'll use the IP found in config if possible, but simplest is to assume GCS is reachable.
# Let's try to connect to GCS Control Port (48080 default).
# We'll use the IP that the user implied or Config would have.
# Since I don't know GCS IP for sure, I'll try to find it or just fail.
HOST = "100.101.93.23" # Wait, that's the DRONE IP.
# If GCS is "this computer", I need its Tailscale IP. 
# But I can't easily get it here without running 'tailscale ip'.

# Let's try connecting to the gateway or assuming the user meant something else.
# Actually, sdrone_bench.py loads CONFIG.get("GCS_HOST").
# I'll import config and use that.

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from core.config import CONFIG
    HOST = str(CONFIG.get("GCS_HOST"))
    PORT = int(CONFIG.get("GCS_CONTROL_PORT", 48080))
    print(f"Targeting GCS at {HOST}:{PORT}")
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5.0)
    sock.connect((HOST, PORT))
    
    req = {"cmd": "chronos_sync", "t1": time.time()}
    sock.sendall(json.dumps(req).encode() + b"\n")
    
    resp_data = sock.recv(4096)
    print(f"Response: {resp_data.decode().strip()}")
    sock.close()
except Exception as e:
    print(f"FAIL: {e}")
