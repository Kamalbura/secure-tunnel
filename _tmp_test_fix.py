#!/usr/bin/env python3
"""
Test the fixed PowerCollector to verify it now reads correct voltage.
"""
import time
import sys
sys.path.insert(0, '/home/ubuntu/secure_tunnel')

from core.metrics_collectors import PowerCollector

print("=" * 70)
print("TESTING FIXED POWERCOLLECTOR")
print("=" * 70)

# Create a power collector
pc = PowerCollector(backend="auto")

print(f"Detected backend: {pc.backend}")
if pc.backend != "ina219":
    print("ERROR: INA219 not detected!")
    sys.exit(1)

print("\nCollecting 10 samples...")
voltages = []
for i in range(10):
    sample = pc.collect()
    v = sample.get("voltage_v")
    c = sample.get("current_a")
    p = sample.get("power_w")
    if v is not None:
        voltages.append(v)
        print(f"  [{i}] {v:.4f}V {c*1000:.1f}mA {p:.3f}W")
    else:
        print(f"  [{i}] ERROR: {sample.get('error', 'Unknown')}")
    time.sleep(0.1)

if voltages:
    avg_v = sum(voltages) / len(voltages)
    min_v = min(voltages)
    max_v = max(voltages)
    print(f"\nResults:")
    print(f"  Average voltage: {avg_v:.4f}V")
    print(f"  Min voltage: {min_v:.4f}V")
    print(f"  Max voltage: {max_v:.4f}V")
    
    if avg_v > 4.8 and avg_v < 5.2:
        print("✓ PASS: Voltage reading is correct (~5.0V)")
    elif avg_v > 3.5 and avg_v < 4.0:
        print("✗ FAIL: Voltage still reading low (~3.9V, bug not fixed)")
    else:
        print(f"? UNKNOWN: Got {avg_v:.2f}V (expected ~5.0V)")
else:
    print("ERROR: No valid samples collected")
    sys.exit(1)
