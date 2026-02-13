#!/usr/bin/env python3
"""
Test INA219 with 9-bit ADC at 1kHz - verify aliasing is gone.
"""
import sys, time, statistics
sys.path.insert(0, "/home/dev/secure-tunnel")

from core.metrics_collectors import PowerCollector, _INA219_BACKEND

print("=" * 60)
print("INA219 9-BIT ADC QUALITY TEST")
print("=" * 60)
print(f"Backend lib: {_INA219_BACKEND}")

pc = PowerCollector(backend="auto")
print(f"Detected: {pc.backend}")
print(f"ADC res bus: {pc._ina219.bus_adc_resolution}")
print(f"ADC res shunt: {pc._ina219.shunt_adc_resolution}")

# Single read
r = pc.collect()
print(f"\nSingle read: V={r['voltage_v']:.4f} A={r['current_a']:.4f} W={r['power_w']:.4f}")

# 1kHz for 3 seconds via start_sampling (same as benchmark)
print(f"\n[Sampling at 1kHz for 3 seconds via start_sampling()]")
pc.start_sampling(rate_hz=1000.0)
time.sleep(3.0)
samples = pc.stop_sampling()

n = len(samples)
dur = samples[-1]["mono_time"] - samples[0]["mono_time"] if n > 1 else 0
rate = (n - 1) / dur if dur > 0 else 0

voltages = [s["voltage_v"] for s in samples if s.get("voltage_v") is not None]
currents = [s["current_a"] for s in samples if s.get("current_a") is not None]
powers = [s["power_w"] for s in samples if s.get("power_w") is not None]
errors = [s for s in samples if "error" in s]

print(f"  Samples: {n}")
print(f"  Duration: {dur:.3f} s")
print(f"  Actual rate: {rate:.1f} Hz")
print(f"  Errors: {len(errors)}")

print(f"\n[Voltage (bus)]")
print(f"  Mean: {statistics.mean(voltages):.4f} V")
print(f"  Stdev: {statistics.stdev(voltages):.4f} V")
print(f"  Min: {min(voltages):.4f} V")
print(f"  Max: {max(voltages):.4f} V")
print(f"  Range: {max(voltages)-min(voltages):.4f} V")
cv = statistics.stdev(voltages) / statistics.mean(voltages) * 100
print(f"  CV: {cv:.2f}%")

print(f"\n[Current]")
print(f"  Mean: {statistics.mean(currents)*1000:.2f} mA")
print(f"  Stdev: {statistics.stdev(currents)*1000:.2f} mA")
print(f"  Min: {min(currents)*1000:.2f} mA")
print(f"  Max: {max(currents)*1000:.2f} mA")

print(f"\n[Power]")
print(f"  Mean: {statistics.mean(powers):.4f} W")
print(f"  Stdev: {statistics.stdev(powers):.4f} W")
print(f"  Min: {min(powers):.4f} W")  
print(f"  Max: {max(powers):.4f} W")

# Voltage distribution
v_bins = {"3.2-3.4V": 0, "3.4-3.6V": 0, "3.6-4.0V": 0, "4.0-4.5V": 0, ">4.5V": 0}
for v in voltages:
    if v < 3.4: v_bins["3.2-3.4V"] += 1
    elif v < 3.6: v_bins["3.4-3.6V"] += 1
    elif v < 4.0: v_bins["3.6-4.0V"] += 1
    elif v < 4.5: v_bins["4.0-4.5V"] += 1
    else: v_bins[">4.5V"] += 1
print(f"\n[Voltage Distribution]")
for k, v in v_bins.items():
    pct = v / len(voltages) * 100
    bar = "█" * int(pct / 2)
    print(f"  {k:>10}: {v:5d} ({pct:5.1f}%) {bar}")

# Inter-sample timing
timestamps = [s["mono_time"] for s in samples]
deltas = [timestamps[i] - timestamps[i-1] for i in range(1, len(timestamps))]
print(f"\n[Inter-Sample Timing]")
print(f"  Mean: {statistics.mean(deltas)*1000:.3f} ms")
print(f"  Stdev: {statistics.stdev(deltas)*1000:.3f} ms")
print(f"  Min: {min(deltas)*1000:.3f} ms")
print(f"  Max: {max(deltas)*1000:.3f} ms")

# Energy stats
stats = pc.get_energy_stats(samples)
print(f"\n[Energy Stats (from get_energy_stats)]")
for k, v in stats.items():
    if v is not None and isinstance(v, float):
        print(f"  {k}: {v:.6f}")
    else:
        print(f"  {k}: {v}")

# Verdict
print(f"\n{'='*60}")
print("VERDICT")
print(f"{'='*60}")
mean_v = statistics.mean(voltages)
std_v = statistics.stdev(voltages)
if std_v / mean_v < 0.02:
    print(f"  ✓ Voltage stable: {mean_v:.3f}V ± {std_v:.4f}V (CV={cv:.1f}%)")
else:
    print(f"  ⚠ Voltage noisy: {mean_v:.3f}V ± {std_v:.4f}V (CV={cv:.1f}%)")

if 3.0 < mean_v < 3.6:
    print(f"  ℹ INA219 is on the 3.3V rail (not 5V supply)")
    print(f"  ℹ Power readings represent 3.3V rail consumption only")
    
if rate >= 950:
    print(f"  ✓ Sample rate OK: {rate:.0f} Hz")
else:
    print(f"  ⚠ Sample rate low: {rate:.0f} Hz (target 1000)")

print(f"  Energy: {stats.get('energy_total_j', 0):.4f} J over {dur:.1f}s")
print(f"  Avg power: {stats.get('power_avg_w', 0):.4f} W")
print()
