#!/usr/bin/env python3
"""Quick test of all collectors."""

from core.metrics_collectors import EnvironmentCollector, SystemCollector, NetworkCollector
import json

print("=" * 60)
print("COLLECTORS TEST")
print("=" * 60)

# Environment
print("\n--- ENVIRONMENT ---")
env = EnvironmentCollector()
env_data = env.collect()
print(f"Hostname: {env_data['hostname']}")
print(f"Python: {env_data['python_version']}")
print(f"Git: {env_data['git_commit']} (dirty: {env_data['git_dirty']})")
print(f"Conda: {env_data['conda_env']}")

# System
print("\n--- SYSTEM ---")
sys_col = SystemCollector()
sys_data = sys_col.collect()
print(f"CPU: {sys_data['cpu_percent']:.1f}%")
print(f"Memory RSS: {sys_data['memory_rss_mb']:.1f} MB")
print(f"System Memory: {sys_data.get('system_memory_percent', 0):.1f}%")
print(f"Temperature: {sys_data.get('temperature_c', 0):.1f}C")
print(f"Load Avg: {sys_data.get('load_avg_1m', 0):.2f}")

# Network
print("\n--- NETWORK ---")
net = NetworkCollector()
stats = net.collect()
print(f"RX: {stats['rx_bytes']/1024/1024:.1f} MB, TX: {stats['tx_bytes']/1024/1024:.1f} MB")
print(f"Packets RX: {stats['rx_packets']}, TX: {stats['tx_packets']}")

# Test aggregator
print("\n--- AGGREGATOR ---")
from core.metrics_aggregator import MetricsAggregator
agg = MetricsAggregator(role='auto')
print(f"Detected role: {agg.role}")
print(f"Output dir: {agg.output_dir}")

print("\n=== ALL COLLECTORS WORKING ===")
