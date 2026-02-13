#!/usr/bin/env python3
"""
INA219 Sensor Quality Assessment
Collects at 1kHz for 3 seconds, analyses:
- Voltage stability (check for undervoltage)
- Current accuracy
- Actual achieved sample rate
- ADC resolution and noise floor
- Detects brownout/throttling events
"""
import sys, time, statistics
sys.path.insert(0, "/home/dev/secure-tunnel")

import board
import adafruit_ina219

# ─── 1. Sensor Init ───
i2c = board.I2C()
sensor = adafruit_ina219.INA219(i2c)

# Check available calibrations
print("=" * 60)
print("INA219 SENSOR QUALITY ASSESSMENT")
print("=" * 60)

# ─── 2. Check initial config ───
print(f"\n[Config Before Calibration]")
print(f"  bus_voltage_range: {sensor.bus_voltage_range}")
print(f"  gain: {sensor.gain}")
print(f"  bus_adc_resolution: {sensor.bus_adc_resolution}")
print(f"  shunt_adc_resolution: {sensor.shunt_adc_resolution}")
print(f"  mode: {sensor.mode}")

# Apply 32V/2A calibration (same as our code does)
sensor.set_calibration_32V_2A()
print(f"\n[Config After set_calibration_32V_2A()]")
print(f"  bus_voltage_range: {sensor.bus_voltage_range}")
print(f"  gain: {sensor.gain}")
print(f"  bus_adc_resolution: {sensor.bus_adc_resolution}")
print(f"  shunt_adc_resolution: {sensor.shunt_adc_resolution}")
print(f"  mode: {sensor.mode}")

# ─── 3. Check RPi voltage throttling status ───
print(f"\n[RPi Throttling Check]")
try:
    import subprocess
    result = subprocess.run(["vcgencmd", "get_throttled"], capture_output=True, text=True, timeout=5)
    throttled = result.stdout.strip()
    print(f"  vcgencmd get_throttled: {throttled}")
    # Parse throttle bits
    if "=" in throttled:
        val = int(throttled.split("=")[1], 0)
        if val & 0x1: print("  ⚠ UNDER-VOLTAGE DETECTED (NOW)")
        if val & 0x2: print("  ⚠ ARM FREQUENCY CAPPED (NOW)")
        if val & 0x4: print("  ⚠ CURRENTLY THROTTLED (NOW)")
        if val & 0x8: print("  ⚠ SOFT TEMPERATURE LIMIT (NOW)")
        if val & 0x10000: print("  ⚠ Under-voltage has occurred (PAST)")
        if val & 0x20000: print("  ⚠ ARM frequency capping has occurred (PAST)")
        if val & 0x40000: print("  ⚠ Throttling has occurred (PAST)")
        if val & 0x80000: print("  ⚠ Soft temperature limit has occurred (PAST)")
        if val == 0:
            print("  ✓ No throttling detected")
except Exception as e:
    print(f"  Could not check: {e}")

# ─── 4. Warmup reads ───
print(f"\n[Warmup - 10 discarded reads]")
for _ in range(10):
    _ = sensor.bus_voltage
    _ = sensor.current
    time.sleep(0.005)
print("  Done")

# ─── 5. Slow baseline (10 reads at 10Hz) ───
print(f"\n[Slow Baseline - 10 reads at ~10Hz]")
baseline_v = []
baseline_i = []
for i in range(10):
    v = sensor.bus_voltage
    c = sensor.current  # mA
    baseline_v.append(v)
    baseline_i.append(c)
    print(f"  [{i}] V={v:.4f}  I={c:.2f} mA  P={v*abs(c)/1000:.4f} W")
    time.sleep(0.1)

print(f"  Voltage: mean={statistics.mean(baseline_v):.4f} stdev={statistics.stdev(baseline_v):.4f}")
print(f"  Current: mean={statistics.mean(baseline_i):.2f} stdev={statistics.stdev(baseline_i):.2f} mA")

# ─── 6. High-speed 1kHz for 3 seconds ───
print(f"\n[1kHz Sampling for 3.0 seconds]")
voltages = []
currents = []
powers = []
timestamps = []
errors = 0

interval = 1.0 / 1000.0  # 1ms target
start = time.perf_counter()
next_tick = start

sample_count = 0
while True:
    elapsed = time.perf_counter() - start
    if elapsed >= 3.0:
        break
    
    try:
        t0 = time.perf_counter()
        v = sensor.bus_voltage
        c = abs(sensor.current) / 1000.0  # mA -> A
        read_time = time.perf_counter() - t0
        
        voltages.append(v)
        currents.append(c)
        powers.append(v * c)
        timestamps.append(time.perf_counter() - start)
        sample_count += 1
    except Exception as e:
        errors += 1
    
    next_tick += interval
    sleep_for = next_tick - time.perf_counter()
    if sleep_for > 0:
        time.sleep(sleep_for)

end = time.perf_counter()
actual_duration = end - start
actual_rate = sample_count / actual_duration

print(f"  Samples collected: {sample_count}")
print(f"  Actual duration: {actual_duration:.3f} s")
print(f"  Actual sample rate: {actual_rate:.1f} Hz")
print(f"  Errors: {errors}")

# ─── 7. Voltage Analysis ───
print(f"\n[Voltage Analysis]")
print(f"  Mean: {statistics.mean(voltages):.4f} V")
print(f"  Stdev: {statistics.stdev(voltages):.4f} V")
print(f"  Min: {min(voltages):.4f} V")
print(f"  Max: {max(voltages):.4f} V")
print(f"  P5: {sorted(voltages)[len(voltages)//20]:.4f} V")
print(f"  P95: {sorted(voltages)[len(voltages)*19//20]:.4f} V")

# Count voltage bins
v_bins = {"<3.0V": 0, "3.0-3.3V": 0, "3.3-4.0V": 0, "4.0-4.5V": 0, "4.5-5.5V": 0, ">5.5V": 0}
for v in voltages:
    if v < 3.0: v_bins["<3.0V"] += 1
    elif v < 3.3: v_bins["3.0-3.3V"] += 1
    elif v < 4.0: v_bins["3.3-4.0V"] += 1
    elif v < 4.5: v_bins["4.0-4.5V"] += 1
    elif v < 5.5: v_bins["4.5-5.5V"] += 1
    else: v_bins[">5.5V"] += 1
print(f"  Voltage Distribution:")
for k, v in v_bins.items():
    pct = v / len(voltages) * 100
    bar = "█" * int(pct / 2)
    print(f"    {k:>10}: {v:5d} ({pct:5.1f}%) {bar}")

# ─── 8. Undervoltage events ───
UNDERVOLT_THRESHOLD = 4.5  # RPi4 nominal is 5.0V, <4.63V triggers warning
undervolt_events = sum(1 for v in voltages if v < UNDERVOLT_THRESHOLD)
print(f"\n[Undervoltage Events (< {UNDERVOLT_THRESHOLD}V)]")
print(f"  Count: {undervolt_events} / {len(voltages)} ({undervolt_events/len(voltages)*100:.1f}%)")

# ─── 9. Current Analysis ───
print(f"\n[Current Analysis]")
print(f"  Mean: {statistics.mean(currents)*1000:.2f} mA")
print(f"  Stdev: {statistics.stdev(currents)*1000:.2f} mA")
print(f"  Min: {min(currents)*1000:.2f} mA")
print(f"  Max: {max(currents)*1000:.2f} mA")

# ─── 10. Power Analysis ───
print(f"\n[Power Analysis]")
print(f"  Mean: {statistics.mean(powers):.4f} W")
print(f"  Stdev: {statistics.stdev(powers):.4f} W")
print(f"  Min: {min(powers):.4f} W")
print(f"  Max: {max(powers):.4f} W")

# ─── 11. Inter-sample timing ───
if len(timestamps) > 1:
    deltas = [timestamps[i] - timestamps[i-1] for i in range(1, len(timestamps))]
    print(f"\n[Inter-Sample Timing]")
    print(f"  Mean interval: {statistics.mean(deltas)*1000:.3f} ms (target: 1.000 ms)")
    print(f"  Stdev: {statistics.stdev(deltas)*1000:.3f} ms")
    print(f"  Min: {min(deltas)*1000:.3f} ms")
    print(f"  Max: {max(deltas)*1000:.3f} ms")
    jitter_pct = statistics.stdev(deltas) / statistics.mean(deltas) * 100
    print(f"  Jitter: {jitter_pct:.1f}%")

# ─── 12. Check if INA219 is measuring bus vs shunt ───
print(f"\n[INA219 Bus vs Shunt Voltage]")
print(f"  bus_voltage (Vbus pin): {sensor.bus_voltage:.4f} V")
print(f"  shunt_voltage (across shunt): {sensor.shunt_voltage:.6f} V")
print(f"  The bus_voltage measures voltage AFTER the shunt resistor")
print(f"  Full supply voltage = bus_voltage + shunt_voltage")
full_v = sensor.bus_voltage + sensor.shunt_voltage
print(f"  Full supply = {full_v:.4f} V")

# ─── 13. Verdict ───
print(f"\n{'='*60}")
print(f"VERDICT")
print(f"{'='*60}")
mean_v = statistics.mean(voltages)
if mean_v < 3.5:
    print(f"  ❌ CRITICAL: Mean voltage {mean_v:.2f}V - severe undervoltage!")
    print(f"     Check power supply, USB cable, and INA219 wiring.")
    print(f"     RPi4 needs 5.0V ±5%. This is NOT a valid reading for system power.")
    print(f"     The INA219 may be measuring a DIFFERENT rail (3.3V or downstream).")
elif mean_v < 4.63:
    print(f"  ⚠ WARNING: Mean voltage {mean_v:.2f}V - below RPi4 threshold (4.63V)")
    print(f"     The INA219 may be on a 3.3V rail, not the 5V supply.")
elif mean_v < 5.5:
    print(f"  ✓ OK: Mean voltage {mean_v:.2f}V - normal 5V supply range")
else:
    print(f"  ❌ ABNORMAL: Mean voltage {mean_v:.2f}V - above expected range")

if actual_rate >= 900:
    print(f"  ✓ Sample rate {actual_rate:.0f} Hz achievable (target 1000)")
elif actual_rate >= 500:
    print(f"  ⚠ Sample rate {actual_rate:.0f} Hz - below 1kHz target")
else:
    print(f"  ❌ Sample rate {actual_rate:.0f} Hz - much too low for 1kHz")

print()
