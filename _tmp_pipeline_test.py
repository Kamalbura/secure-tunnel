#!/usr/bin/env python3
"""
Simulate exactly what MetricsAggregator does:
1. Create PowerCollector
2. start_sampling(rate_hz=1000)
3. Wait 10 seconds (simulating a suite)
4. stop_sampling()
5. get_energy_stats()
6. Print the voltage_avg_v and compare to true value
"""
import sys, os, time

# Ensure we import from the right place
sys.path.insert(0, os.path.expanduser("~/secure-tunnel"))

from core.metrics_collectors import PowerCollector

print("Creating PowerCollector...")
pc = PowerCollector()
print(f"  Backend: {pc.backend}")
print(f"  INA219: {pc._ina219}")

# Do a quick sanity single collect
single = pc.collect()
print(f"  Single collect: V={single.get('voltage_v')}, I={single.get('current_a')}, P={single.get('power_w')}")

# Start sampling at 1kHz
print(f"\nStarting 1kHz sampling for 10 seconds...")
pc.start_sampling(rate_hz=1000.0)
time.sleep(10)
samples = pc.stop_sampling()
print(f"  Got {len(samples)} samples")

if samples:
    # Check first 5 and last 5 samples
    print("\n  First 5 samples:")
    for s in samples[:5]:
        print(f"    V={s.get('voltage_v'):.4f}  I={s.get('current_a'):.4f}  P={s.get('power_w'):.4f}")
    print("  Last 5 samples:")
    for s in samples[-5:]:
        print(f"    V={s.get('voltage_v'):.4f}  I={s.get('current_a'):.4f}  P={s.get('power_w'):.4f}")

    # Get energy stats
    stats = pc.get_energy_stats(samples)
    print(f"\n  Energy stats:")
    for k, v in stats.items():
        print(f"    {k}: {v}")

    # Manual voltage check
    voltages = [s.get("voltage_v", 0) for s in samples if s.get("voltage_v") is not None]
    if voltages:
        import statistics
        v_mean = statistics.mean(voltages)
        v_std = statistics.stdev(voltages)
        print(f"\n  Manual voltage check:")
        print(f"    Mean: {v_mean:.4f} V")
        print(f"    Stdev: {v_std:.4f} V")
        print(f"    Min: {min(voltages):.4f} V")
        print(f"    Max: {max(voltages):.4f} V")
        print(f"    Expected: ~5.04 V")
        error = abs(v_mean - 5.04) / 5.04 * 100
        print(f"    Error: {error:.1f}%")
        if error > 5:
            print(f"    *** VOLTAGE IS WRONG! Expected ~5V, got {v_mean:.2f}V ***")
        else:
            print(f"    ✓ Voltage is correct")
