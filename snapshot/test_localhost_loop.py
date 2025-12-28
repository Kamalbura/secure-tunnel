#!/usr/bin/env python3
"""
Localhost loop test for PQC secure tunnel.

This script sends UDP packets through the complete encryption/decryption loop:
1. GCS plaintext sender (port 47001) -> GCS proxy
2. GCS proxy encrypts -> network (port 46011) -> Drone proxy  
3. Drone proxy decrypts -> Drone plaintext (port 47004)
4. Echo server returns packet via same path in reverse

We also run a simple echo server on the drone side to simulate the flight controller.
"""

import socket
import struct
import time
import threading

# Ports from core/config.py
GCS_PLAINTEXT_TX = 47001   # GCS app sends plaintext here -> GCS proxy
GCS_PLAINTEXT_RX = 47002   # GCS proxy returns decrypted packets here
DRONE_PLAINTEXT_TX = 47003  # Drone app sends plaintext here
DRONE_PLAINTEXT_RX = 47004  # Drone proxy returns decrypted packets here

HOST = "127.0.0.1"

def run_drone_echo_server(stop_event: threading.Event, stats: dict):
    """Run an echo server on the drone side to return packets."""
    
    # Bind to drone RX port (receives decrypted packets from drone proxy)
    rx_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    rx_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    rx_sock.bind((HOST, DRONE_PLAINTEXT_RX))
    rx_sock.settimeout(0.5)
    
    # Create send socket to send echo back to drone proxy
    tx_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    print(f"[Echo] Drone echo server started on {HOST}:{DRONE_PLAINTEXT_RX}")
    print(f"[Echo] Will echo back to {HOST}:{DRONE_PLAINTEXT_TX}")
    
    while not stop_event.is_set():
        try:
            data, addr = rx_sock.recvfrom(65535)
            stats["echo_received"] += 1
            
            # Echo the data back through the drone TX port
            tx_sock.sendto(data, (HOST, DRONE_PLAINTEXT_TX))
            stats["echo_sent"] += 1
            
            if stats["echo_received"] % 10 == 0:
                print(f"[Echo] Received and echoed {stats['echo_received']} packets")
        except socket.timeout:
            continue
        except Exception as e:
            print(f"[Echo] Error: {e}")
    
    rx_sock.close()
    tx_sock.close()
    print("[Echo] Echo server stopped")


def run_gcs_sender_receiver(packet_count: int, delay_ms: float):
    """Send packets from GCS side and receive echoed responses."""
    
    # Create sender socket (sends to GCS proxy plaintext input)
    tx_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    # Create receiver socket (receives from GCS proxy after decryption)
    rx_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    rx_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    rx_sock.bind((HOST, GCS_PLAINTEXT_RX))
    rx_sock.settimeout(2.0)
    
    print(f"\n[GCS] Sending {packet_count} packets to {HOST}:{GCS_PLAINTEXT_TX}")
    print(f"[GCS] Expecting responses on {HOST}:{GCS_PLAINTEXT_RX}")
    
    sent = 0
    received = 0
    rtt_samples = []
    
    for seq in range(packet_count):
        # Create packet with sequence number and timestamp
        send_time_ns = time.time_ns()
        packet = struct.pack("!IQ", seq, send_time_ns) + b"PQC-TEST-PAYLOAD-" + str(seq).encode()
        
        # Send to GCS proxy plaintext input
        tx_sock.sendto(packet, (HOST, GCS_PLAINTEXT_TX))
        sent += 1
        
        # Try to receive echoed response
        try:
            response, addr = rx_sock.recvfrom(65535)
            recv_time_ns = time.time_ns()
            
            if len(response) >= 12:
                resp_seq, resp_ts = struct.unpack("!IQ", response[:12])
                rtt_ns = recv_time_ns - resp_ts
                rtt_ms = rtt_ns / 1_000_000
                rtt_samples.append(rtt_ms)
                received += 1
                
                if seq % 10 == 0:
                    print(f"[GCS] Packet {seq}: RTT={rtt_ms:.2f}ms")
        except socket.timeout:
            print(f"[GCS] Packet {seq}: TIMEOUT (no response)")
        
        if delay_ms > 0:
            time.sleep(delay_ms / 1000.0)
    
    tx_sock.close()
    rx_sock.close()
    
    # Print summary
    print("\n" + "=" * 60)
    print("LOCALHOST LOOP TEST SUMMARY")
    print("=" * 60)
    print(f"Packets sent:     {sent}")
    print(f"Packets received: {received}")
    print(f"Delivery rate:    {100.0 * received / max(1, sent):.1f}%")
    
    if rtt_samples:
        avg_rtt = sum(rtt_samples) / len(rtt_samples)
        min_rtt = min(rtt_samples)
        max_rtt = max(rtt_samples)
        print(f"RTT (min/avg/max): {min_rtt:.2f} / {avg_rtt:.2f} / {max_rtt:.2f} ms")
    
    print("=" * 60)
    return sent, received


def main():
    print("=" * 60)
    print("PQC SECURE TUNNEL - LOCALHOST LOOP TEST")
    print("=" * 60)
    print("\nData flow:")
    print(f"  GCS plaintext ({GCS_PLAINTEXT_TX}) -> GCS proxy")
    print(f"  -> Encrypted UDP (46011/46012)")
    print(f"  -> Drone proxy -> Drone plaintext ({DRONE_PLAINTEXT_RX})")
    print(f"  -> Echo server -> Drone plaintext ({DRONE_PLAINTEXT_TX})")
    print(f"  -> Drone proxy -> Encrypted UDP")
    print(f"  -> GCS proxy -> GCS plaintext ({GCS_PLAINTEXT_RX})")
    print("")
    
    # Wait for proxies to be ready
    print("Waiting 2 seconds for proxies to be ready...")
    time.sleep(2)
    
    # Start echo server in background
    stop_event = threading.Event()
    echo_stats = {"echo_received": 0, "echo_sent": 0}
    echo_thread = threading.Thread(
        target=run_drone_echo_server, 
        args=(stop_event, echo_stats),
        daemon=True
    )
    echo_thread.start()
    
    time.sleep(0.5)  # Give echo server time to bind
    
    try:
        # Run the test - send 50 packets with 50ms delay
        sent, received = run_gcs_sender_receiver(packet_count=50, delay_ms=50)
        
        # Print echo stats
        print(f"\nEcho server stats:")
        print(f"  Packets received at drone: {echo_stats['echo_received']}")
        print(f"  Packets echoed back: {echo_stats['echo_sent']}")
        
        if received > 0:
            print("\n✅ SUCCESS: Complete encryption/decryption loop working!")
        else:
            print("\n❌ FAILED: No packets received back through the loop")
            print("   Check that both GCS and Drone proxies are running")
            
    finally:
        stop_event.set()
        echo_thread.join(timeout=2.0)


if __name__ == "__main__":
    main()
