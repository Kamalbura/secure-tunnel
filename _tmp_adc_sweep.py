#!/usr/bin/env python3
"""Test different ADC resolutions at 1kHz to find which gives accurate 5V readings."""
import time, statistics

import board, busio
from adafruit_ina219 import INA219, ADCResolution

i2c = busio.I2C(board.SCL, board.SDA)
ina = INA219(i2c)

configs = [
    ("9-bit",  ADCResolution.ADCRES_9BIT_1S),
    ("10-bit", ADCResolution.ADCRES_10BIT_1S),
    ("11-bit", ADCResolution.ADCRES_11BIT_1S),
    ("12-bit", ADCResolution.ADCRES_12BIT_1S),
    ("12-bit 2x avg", ADCResolution.ADCRES_12BIT_2S),
    ("12-bit 4x avg", ADCResolution.ADCRES_12BIT_4S),
]

for label, adc_res in configs:
    ina.set_calibration_32V_2A()
    ina.bus_adc_resolution = adc_res
    ina.shunt_adc_resolution = adc_res

    # Determine conversion time
    conv_us = {
        ADCResolution.ADCRES_9BIT_1S: 84,
        ADCResolution.ADCRES_10BIT_1S: 148,
        ADCResolution.ADCRES_11BIT_1S: 276,
        ADCResolution.ADCRES_12BIT_1S: 532,
        ADCResolution.ADCRES_12BIT_2S: 1060,
        ADCResolution.ADCRES_12BIT_4S: 2130,
    }.get(adc_res, 532)

    # Total conversion = bus + shunt
    total_conv_us = conv_us * 2
    safe_interval_ms = max(total_conv_us / 1000 * 1.2, 1.0)  # 20% margin

    # Sample for 2 seconds at max safe rate
    target_hz = min(1000, 1000.0 / safe_interval_ms)
    interval = 1.0 / target_hz
    duration = 2.0

    time.sleep(0.1)  # let ADC settle

    voltages = []
    currents = []
    powers = []
    t0 = time.perf_counter()
    next_tick = t0

    while time.perf_counter() - t0 < duration:
        next_tick += interval
        try:
            v = ina.bus_voltage
            c = abs(ina.current)
            voltages.append(v)
            currents.append(c)
            powers.append(v * c / 1000)
        except:
            pass
        sleep_for = next_tick - time.perf_counter()
        if sleep_for > 0:
            time.sleep(sleep_for)

    elapsed = time.perf_counter() - t0
    actual_hz = len(voltages) / elapsed

    v_mean = statistics.mean(voltages)
    v_std = statistics.stdev(voltages) if len(voltages) > 1 else 0
    v_min = min(voltages)
    v_max = max(voltages)
    v_cv = v_std / v_mean * 100

    c_mean = statistics.mean(currents)
    p_mean = statistics.mean(powers)

    # How far is the mean from the true 5.04V?
    error_pct = abs(v_mean - 5.04) / 5.04 * 100

    print(f"\n{'='*60}")
    print(f"ADC: {label}  |  conv={conv_us}µs  |  safe_rate={target_hz:.0f}Hz")
    print(f"{'='*60}")
    print(f"  Samples: {len(voltages)}  Rate: {actual_hz:.0f}Hz")
    print(f"  Voltage: {v_mean:.4f} ± {v_std:.4f}V  "
          f"(min={v_min:.4f} max={v_max:.4f}  CV={v_cv:.1f}%)")
    print(f"  ERROR from true 5.04V: {error_pct:.1f}%")
    print(f"  Current: {c_mean:.1f}mA  Power: {p_mean:.3f}W")
    if error_pct > 5:
        print(f"  *** WARNING: Voltage error > 5% — ADC aliasing! ***")
    elif error_pct > 2:
        print(f"  *** CAUTION: Voltage error > 2% ***")
    else:
        print(f"  ✓ Voltage accurate (< 2% error)")

print(f"\n{'='*60}")
print("CONCLUSION")
print(f"{'='*60}")
print("The INA219 is on the 5V USB supply rail (bus_voltage ~5.04V).")
print("9-bit ADC at 1kHz creates register aliasing, producing fake ~3.4V.")
print("Need to find the right ADC/rate combo that gives accurate 5V readings.")
