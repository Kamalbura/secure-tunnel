#!/usr/bin/env python3
"""Quick Pi status check."""
import subprocess, os

t = 0x50000
print("=== Throttle decode (0x{:x}) ===".format(t))
print(f"  Bit 16 - under-voltage occurred:    {bool(t & (1<<16))}")
print(f"  Bit 17 - arm freq capped occurred:  {bool(t & (1<<17))}")
print(f"  Bit 18 - throttled occurred:         {bool(t & (1<<18))}")
print(f"  Bit 19 - soft temp limit occurred:   {bool(t & (1<<19))}")
print(f"  Bit 0  - currently under-voltage:    {bool(t & 1)}")
print(f"  Bit 1  - arm freq currently capped:  {bool(t & (1<<1))}")
print(f"  Bit 2  - currently throttled:         {bool(t & (1<<2))}")
print(f"  Bit 3  - soft temp limit active:      {bool(t & (1<<3))}")

# Read available governors
with open("/sys/devices/system/cpu/cpu0/cpufreq/scaling_available_governors") as f:
    print(f"\n=== Available governors: {f.read().strip()}")

# All CPUs governor
for i in range(4):
    with open(f"/sys/devices/system/cpu/cpu{i}/cpufreq/scaling_governor") as f:
        print(f"  CPU{i}: {f.read().strip()}")
    with open(f"/sys/devices/system/cpu/cpu{i}/cpufreq/scaling_cur_freq") as f:
        print(f"    Current: {int(f.read().strip())/1000:.0f} MHz")
