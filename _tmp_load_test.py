#!/usr/bin/env python3
"""Test INA219 reads under different CPU loads to reproduce the 3.4V issue.
The theory: under heavy CPU/I2C load, bus_voltage register reads might
return partially-converted values.
"""
import time, statistics, threading, os

import board, busio
from adafruit_ina219 import INA219, ADCResolution

def sample_ina(ina, duration_s, rate_hz):
    """Sample INA219 and return voltage stats."""
    interval = 1.0 / rate_hz
    voltages = []
    currents = []
    t0 = time.perf_counter()
    next_tick = t0
    while time.perf_counter() - t0 < duration_s:
        next_tick += interval
        try:
            v = ina.bus_voltage
            c = abs(ina.current) / 1000.0
            voltages.append(v)
            currents.append(c)
        except:
            pass
        sleep_for = next_tick - time.perf_counter()
        if sleep_for > 0:
            time.sleep(sleep_for)
    return voltages, currents

# Init
i2c = busio.I2C(board.SCL, board.SDA)
ina = INA219(i2c)
ina.set_calibration_32V_2A()
ina.bus_adc_resolution = ADCResolution.ADCRES_9BIT_1S
ina.shunt_adc_resolution = ADCResolution.ADCRES_9BIT_1S

# Test 1: Idle (no load)
print("=" * 60)
print("TEST 1: IDLE (9-bit, 1kHz, 3s)")
print("=" * 60)
voltages, currents = sample_ina(ina, 3.0, 1000)
print(f"  Samples: {len(voltages)}")
print(f"  Voltage: {statistics.mean(voltages):.4f} ± {statistics.stdev(voltages):.4f} V")
print(f"  Current: {statistics.mean(currents):.4f} A")
print(f"  Range: {min(voltages):.4f} - {max(voltages):.4f} V")

# Test 2: CPU stress (4 threads doing math)
print()
print("=" * 60)
print("TEST 2: CPU STRESS (4 threads, 9-bit, 1kHz, 3s)")
print("=" * 60)
stop_stress = threading.Event()
def cpu_stress():
    x = 0.0
    while not stop_stress.is_set():
        for _ in range(10000):
            x += 0.001
            x *= 1.001

stress_threads = [threading.Thread(target=cpu_stress, daemon=True) for _ in range(4)]
for t in stress_threads:
    t.start()
time.sleep(0.5)  # let stress stabilize

voltages, currents = sample_ina(ina, 3.0, 1000)
stop_stress.set()
for t in stress_threads:
    t.join()
print(f"  Samples: {len(voltages)}")
print(f"  Voltage: {statistics.mean(voltages):.4f} ± {statistics.stdev(voltages):.4f} V")
print(f"  Current: {statistics.mean(currents):.4f} A")
print(f"  Range: {min(voltages):.4f} - {max(voltages):.4f} V")

# Test 3: I2C bus contention (another thread doing rapid I2C reads)
print()
print("=" * 60)
print("TEST 3: I2C CONTENTION (parallel smbus2 reads, 9-bit, 1kHz, 3s)")
print("=" * 60)
import smbus2

stop_i2c = threading.Event()
i2c_reads = [0]
def i2c_spam():
    b = smbus2.SMBus(1)
    while not stop_i2c.is_set():
        try:
            b.read_word_data(0x40, 0x02)  # read bus voltage register
            i2c_reads[0] += 1
        except:
            pass
    b.close()

i2c_thread = threading.Thread(target=i2c_spam, daemon=True)
i2c_thread.start()
time.sleep(0.5)

voltages, currents = sample_ina(ina, 3.0, 1000)
stop_i2c.set()
i2c_thread.join()
print(f"  Samples: {len(voltages)}")
print(f"  I2C contention reads: {i2c_reads[0]}")
print(f"  Voltage: {statistics.mean(voltages):.4f} ± {statistics.stdev(voltages):.4f} V")
print(f"  Current: {statistics.mean(currents):.4f} A")
print(f"  Range: {min(voltages):.4f} - {max(voltages):.4f} V")

# Test 4: Re-init with 12-bit at reduced rate
print()
print("=" * 60)
print("TEST 4: 12-BIT ADC at ~500Hz (no contention)")
print("=" * 60)
ina.set_calibration_32V_2A()
ina.bus_adc_resolution = ADCResolution.ADCRES_12BIT_1S
ina.shunt_adc_resolution = ADCResolution.ADCRES_12BIT_1S
time.sleep(0.1)
voltages, currents = sample_ina(ina, 3.0, 500)
print(f"  Samples: {len(voltages)}")
print(f"  Voltage: {statistics.mean(voltages):.4f} ± {statistics.stdev(voltages):.4f} V")
print(f"  Current: {statistics.mean(currents):.4f} A")
print(f"  Range: {min(voltages):.4f} - {max(voltages):.4f} V")

# Test 5: 12-bit at 1kHz (will alias but let's see how bad)
print()
print("=" * 60)
print("TEST 5: 12-BIT ADC at 1kHz (SHOULD ALIAS)")
print("=" * 60)
voltages, currents = sample_ina(ina, 3.0, 1000)
print(f"  Samples: {len(voltages)}")
print(f"  Voltage: {statistics.mean(voltages):.4f} ± {statistics.stdev(voltages):.4f} V")
print(f"  Current: {statistics.mean(currents):.4f} A")
print(f"  Range: {min(voltages):.4f} - {max(voltages):.4f} V")

# Test 6: Check if set_calibration_32V_2A RESETS the ADC resolution
print()
print("=" * 60)
print("TEST 6: AFTER set_calibration_32V_2A() - does it reset ADC?")
print("=" * 60)
ina.set_calibration_32V_2A()  # Does this reset to 12-bit?
# DON'T set ADC resolution after
import smbus2 as s2
b2 = s2.SMBus(1)
raw_cfg = b2.read_word_data(0x40, 0x00)
raw_cfg = ((raw_cfg & 0xFF) << 8) | ((raw_cfg >> 8) & 0xFF)
badc = (raw_cfg >> 7) & 0xF
sadc = (raw_cfg >> 3) & 0xF
print(f"  Config after set_calibration_32V_2A: 0x{raw_cfg:04X}")
print(f"  BADC=0x{badc:X}  SADC=0x{sadc:X}")
res_names = {0x0: "9-bit", 0x1: "10-bit", 0x2: "11-bit", 0x3: "12-bit",
             0x8: "12-bit", 0x9: "12-bit 2x", 0xA: "12-bit 4x", 
             0xB: "12-bit 8x", 0xC: "12-bit 16x", 0xD: "12-bit 32x",
             0xE: "12-bit 64x", 0xF: "12-bit 128x"}
print(f"  BADC = {res_names.get(badc, 'unknown')}  SADC = {res_names.get(sadc, 'unknown')}")

# Now read at 1kHz with the default (post-calibration) ADC settings
voltages, currents = sample_ina(ina, 3.0, 1000)
print(f"  Samples at 1kHz: {len(voltages)}")
print(f"  Voltage: {statistics.mean(voltages):.4f} ± {statistics.stdev(voltages):.4f} V")
print(f"  Current: {statistics.mean(currents):.4f} A")
print(f"  Range: {min(voltages):.4f} - {max(voltages):.4f} V")
b2.close()

print()
print("=" * 60)
print("DIAGNOSIS COMPLETE")
print("=" * 60)
