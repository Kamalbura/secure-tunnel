#!/usr/bin/env python3
"""Quick test to ping GCS control server."""
import socket
import json

def main():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(5.0)
    s.connect(("192.168.0.101", 48080))
    s.sendall(b'{"cmd":"ping"}\n')
    response = s.recv(1024)
    s.close()
    print(f"Response: {response.decode()}")
    return json.loads(response)

if __name__ == "__main__":
    result = main()
    print(f"Status: {result.get('status')}")
