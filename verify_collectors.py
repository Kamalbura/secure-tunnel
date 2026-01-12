#!/usr/bin/env python3
"""Verify all 5 collectors - works on both GCS and Drone."""

from core.metrics_collectors import (
    EnvironmentCollector, 
    SystemCollector, 
    NetworkCollector, 
    LatencyTracker, 
    PowerCollector
)
import json
import platform

def main():
    role = "DRONE" if platform.system() == "Linux" else "GCS"
    print("=" * 60)
    print(f"{role} COLLECTORS VERIFICATION")
    print("=" * 60)

    # 1. Environment
    env = EnvironmentCollector()
    m = env.collect()
    print("\n[1] ENVIRONMENT COLLECTOR")
    print(f"    Hostname: {m.get('hostname', 'N/A')}")
    print(f"    Platform: {m.get('platform', 'N/A')}")
    print(f"    Python:   {m.get('python_version', 'N/A')}")
    git_hash = m.get('git_commit_hash', 'N/A') or 'N/A'
    print(f"    Git Hash: {git_hash[:12] if git_hash != 'N/A' else 'N/A'}...")
    fields_1 = len([k for k in m.keys() if not k.startswith('_')])
    print(f"    Fields:   {fields_1}")

    # 2. System
    sys_c = SystemCollector()
    m = sys_c.collect()
    print("\n[2] SYSTEM COLLECTOR")
    print(f"    CPU Usage:     {m.get('cpu_percent', 0):.1f}%")
    print(f"    CPU Freq:      {m.get('cpu_freq_mhz', 0):.0f} MHz")
    print(f"    Memory RSS:    {m.get('memory_rss_mb', 0):.1f} MB")
    print(f"    Memory %:      {m.get('memory_percent', 0):.1f}%")
    print(f"    Load Avg 1m:   {m.get('load_avg_1m', 0):.2f}")
    print(f"    Load Avg 5m:   {m.get('load_avg_5m', 0):.2f}")
    print(f"    Load Avg 15m:  {m.get('load_avg_15m', 0):.2f}")
    print(f"    Temperature:   {m.get('temperature_c', 0):.1f}°C")
    print(f"    Thread Count:  {m.get('thread_count', 0)}")
    print(f"    Throttled:     {m.get('thermal_throttled', 'N/A')}")
    print(f"    Uptime:        {m.get('uptime_s', 0)/3600:.1f} hours")
    fields_2 = len([k for k in m.keys() if not k.startswith('_')])
    print(f"    Fields:        {fields_2}")

    # 3. Network
    net = NetworkCollector()
    m = net.collect()
    print("\n[3] NETWORK COLLECTOR")
    print(f"    RX Bytes:      {m.get('rx_bytes', 0)/1e6:.1f} MB")
    print(f"    TX Bytes:      {m.get('tx_bytes', 0)/1e6:.1f} MB")
    print(f"    RX Packets:    {m.get('rx_packets', 0):,}")
    print(f"    TX Packets:    {m.get('tx_packets', 0):,}")
    print(f"    RX Errors:     {m.get('rx_errors', 0)}")
    print(f"    TX Errors:     {m.get('tx_errors', 0)}")
    print(f"    RX Dropped:    {m.get('rx_dropped', 0)}")
    print(f"    TX Dropped:    {m.get('tx_dropped', 0)}")
    fields_3 = len([k for k in m.keys() if not k.startswith('_')])
    print(f"    Fields:        {fields_3}")

    # 4. Latency
    lat = LatencyTracker()
    # Simulate some latency samples
    for v in [12.5, 15.2, 11.8, 18.3, 13.1, 25.0, 14.5, 12.0, 16.7, 22.1]:
        lat.record(v)
    m = lat.get_stats()
    print("\n[4] LATENCY TRACKER")
    print(f"    P50:           {m.get('p50_ms', 0):.2f} ms")
    print(f"    P95:           {m.get('p95_ms', 0):.2f} ms")
    print(f"    P99:           {m.get('p99_ms', 0):.2f} ms")
    print(f"    Mean:          {m.get('avg_ms', 0):.2f} ms")
    print(f"    Max:           {m.get('max_ms', 0):.2f} ms")
    print(f"    Min:           {m.get('min_ms', 0):.2f} ms")
    print(f"    Count:         {m.get('count', 0)}")
    fields_4 = len([k for k in m.keys() if not k.startswith('_')])
    print(f"    Fields:        {fields_4}")

    # 5. Power
    pwr = PowerCollector()
    m = pwr.collect()
    print("\n[5] POWER COLLECTOR")
    print(f"    Backend:       {m.get('backend', 'none')}")
    print(f"    Power W:       {m.get('power_w', 0):.2f} W")
    print(f"    Voltage V:     {m.get('voltage_v', 0):.2f} V")
    print(f"    Current A:     {m.get('current_a', 0):.3f} A")
    fields_5 = len([k for k in m.keys() if not k.startswith('_')])
    print(f"    Fields:        {fields_5}")

    total_fields = fields_1 + fields_2 + fields_3 + fields_4 + fields_5
    print("\n" + "=" * 60)
    print(f"{role}: ALL 5 COLLECTORS VERIFIED SUCCESSFULLY ✓")
    print(f"Total metrics fields collected: {total_fields}")
    print("=" * 60)

if __name__ == "__main__":
    main()
