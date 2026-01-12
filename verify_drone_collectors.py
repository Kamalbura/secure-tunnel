#!/usr/bin/env python3
"""Drone metrics collectors verification script."""

import json
import time
from datetime import datetime, timezone

print("=" * 70)
print("DRONE METRICS COLLECTORS VERIFICATION")
print("=" * 70)

from core.metrics_collectors import EnvironmentCollector, SystemCollector, NetworkCollector, LatencyTracker, PowerCollector

print("\n[1/5] ENVIRONMENT COLLECTOR")
print("-" * 40)
env = EnvironmentCollector()
env_data = env.collect()
for k, v in env_data.items():
    print(f"  {k}: {v}")

print("\n[2/5] SYSTEM COLLECTOR")
print("-" * 40)
sys_col = SystemCollector()
sys_data = sys_col.collect()
for k, v in sys_data.items():
    print(f"  {k}: {v}")

print("\n[3/5] NETWORK COLLECTOR")
print("-" * 40)
net = NetworkCollector()
net_data = net.collect()
for k, v in net_data.items():
    print(f"  {k}: {v}")

print("\n[4/5] LATENCY TRACKER")
print("-" * 40)
lat = LatencyTracker()
for i in range(100):
    lat.record(1.0 + (i % 30) * 0.2)
lat_stats = lat.get_stats()
for k, v in lat_stats.items():
    print(f"  {k}: {v}")

print("\n[5/5] POWER COLLECTOR")
print("-" * 40)
power = PowerCollector(backend="auto")
print(f"  backend: {power.backend}")
pwr_data = power.collect()
for k, v in pwr_data.items():
    print(f"  {k}: {v}")

print("\n" + "=" * 70)
print("DRONE VERIFICATION COMPLETE - ALL COLLECTORS WORKING")
print("=" * 70)
