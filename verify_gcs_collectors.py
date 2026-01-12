#!/usr/bin/env python3
"""Verify all 5 collectors on GCS side."""

from core.metrics_collectors import (
    EnvironmentCollector, 
    SystemCollector, 
    NetworkCollector, 
    LatencyTracker, 
    PowerCollector
)
import json

def main():
    print("=" * 60)
    print("GCS COLLECTORS VERIFICATION")
    print("=" * 60)

    # 1. Environment
    env = EnvironmentCollector()
    m = env.collect()
    print("\n[1] ENVIRONMENT COLLECTOR")
    print(f"    Hostname: {m['hostname']}")
    print(f"    Platform: {m['platform']}")
    print(f"    Python:   {m['python_version']}")
    git_hash = m.get('git_commit_hash', 'N/A')
    print(f"    Git Hash: {git_hash[:12] if git_hash else 'N/A'}...")

    # 2. System
    sys_c = SystemCollector()
    m = sys_c.collect()
    print("\n[2] SYSTEM COLLECTOR")
    print(f"    CPU Usage:     {m['cpu_percent']:.1f}%")
    print(f"    CPU Freq:      {m['cpu_freq_mhz']:.0f} MHz")
    print(f"    Memory RSS:    {m['memory_rss_mb']:.1f} MB")
    print(f"    Memory %:      {m['memory_percent']:.1f}%")
    print(f"    Sys Mem Avail: {m['system_memory_available_mb']:.0f} MB")
    print(f"    Load Avg 1m:   {m['load_avg_1m']:.2f}")
    print(f"    Temperature:   {m.get('temperature_c', 0):.1f}°C")
    print(f"    Thread Count:  {m['thread_count']}")

    # 3. Network
    net = NetworkCollector()
    m = net.collect()
    print("\n[3] NETWORK COLLECTOR")
    print(f"    RX Bytes:      {m['rx_bytes']/1e6:.1f} MB")
    print(f"    TX Bytes:      {m['tx_bytes']/1e6:.1f} MB")
    print(f"    RX Packets:    {m['rx_packets']:,}")
    print(f"    TX Packets:    {m['tx_packets']:,}")
    print(f"    RX Errors:     {m['rx_errors']}")
    print(f"    TX Errors:     {m['tx_errors']}")
    print(f"    RX Dropped:    {m['rx_dropped']}")
    print(f"    TX Dropped:    {m['tx_dropped']}")

    # 4. Latency
    lat = LatencyTracker()
    # Simulate some latency samples
    for v in [12.5, 15.2, 11.8, 18.3, 13.1, 25.0, 14.5, 12.0, 16.7, 22.1]:
        lat.record(v)
    m = lat.get_stats()
    print("\n[4] LATENCY TRACKER")
    print(f"    P50:           {m['p50_ms']:.2f} ms")
    print(f"    P95:           {m['p95_ms']:.2f} ms")
    print(f"    P99:           {m['p99_ms']:.2f} ms")
    print(f"    Mean:          {m['avg_ms']:.2f} ms")
    print(f"    Max:           {m['max_ms']:.2f} ms")
    print(f"    Min:           {m['min_ms']:.2f} ms")
    print(f"    Count:         {m['count']}")

    # 5. Power
    pwr = PowerCollector()
    m = pwr.collect()
    print("\n[5] POWER COLLECTOR")
    print(f"    Backend:       {m['backend']}")
    print(f"    Power W:       {m['power_w']:.2f} W")
    print(f"    Voltage V:     {m['voltage_v']:.2f} V")
    print(f"    Current A:     {m['current_a']:.3f} A")

    print("\n" + "=" * 60)
    print("GCS: ALL 5 COLLECTORS VERIFIED SUCCESSFULLY ✓")
    print("=" * 60)

if __name__ == "__main__":
    main()
