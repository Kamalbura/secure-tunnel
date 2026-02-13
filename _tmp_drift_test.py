#!/usr/bin/env python3
"""
Diagnose WHY voltage drifts from 5V to 3.5V over time.
Hypothesis: the 9-bit ADC setting is getting reset during operation.
"""
import time, statistics
import smbus2
import board, busio
from adafruit_ina219 import INA219, ADCResolution

def read_config():
    """Read INA219 config register via smbus2."""
    b = smbus2.SMBus(1)
    raw = b.read_word_data(0x40, 0x00)
    raw = ((raw & 0xFF) << 8) | ((raw >> 8) & 0xFF)
    b.close()
    return raw

def parse_config(raw):
    brng = (raw >> 13) & 1
    pga = (raw >> 11) & 3
    badc = (raw >> 7) & 0xF
    sadc = (raw >> 3) & 0xF
    mode = raw & 7
    res_names = {0x0: "9-bit", 0x1: "10-bit", 0x2: "11-bit", 0x3: "12-bit",
                 0x9: "12-bit 2x", 0xA: "12-bit 4x", 0xB: "12-bit 8x",
                 0xC: "12-bit 16x", 0xD: "12-bit 32x", 0xE: "12-bit 64x",
                 0xF: "12-bit 128x"}
    return {
        "raw": f"0x{raw:04X}",
        "brng": brng,
        "pga": pga,
        "badc": badc,
        "badc_name": res_names.get(badc, f"?{badc}"),
        "sadc": sadc,
        "sadc_name": res_names.get(sadc, f"?{sadc}"),
        "mode": mode,
    }

# Initialize
i2c = busio.I2C(board.SCL, board.SDA)
ina = INA219(i2c)

# Check config BEFORE calibration
cfg0 = parse_config(read_config())
print(f"Config BEFORE calibration: {cfg0}")

ina.set_calibration_32V_2A()
cfg1 = parse_config(read_config())
print(f"Config AFTER set_calibration_32V_2A: {cfg1}")

ina.bus_adc_resolution = ADCResolution.ADCRES_9BIT_1S
ina.shunt_adc_resolution = ADCResolution.ADCRES_9BIT_1S
cfg2 = parse_config(read_config())
print(f"Config AFTER setting 9-bit: {cfg2}")

# Now do rapid reads for 10 seconds, checking config every 1000 reads
print(f"\nSampling at 1kHz for 10 seconds, checking config register periodically...")
print(f"{'Time':>6s}  {'Voltage':>8s}  {'Config':>8s}  {'BADC':>6s}  {'SADC':>6s}  {'Note'}")

interval = 0.001
t0 = time.perf_counter()
next_tick = t0
count = 0
voltages_per_sec = {}

while time.perf_counter() - t0 < 10:
    next_tick += interval
    v = ina.bus_voltage
    c = abs(ina.current)
    count += 1
    
    sec = int(time.perf_counter() - t0)
    if sec not in voltages_per_sec:
        voltages_per_sec[sec] = []
    voltages_per_sec[sec].append(v)
    
    # Check config every 2000 samples
    if count % 2000 == 0:
        cfg = parse_config(read_config())
        elapsed = time.perf_counter() - t0
        note = ""
        if cfg["badc"] != 0x0:  # 9-bit = 0x0
            note = "*** ADC CHANGED! ***"
        print(f"  {elapsed:5.1f}s  {v:7.4f}V  {cfg['raw']}  {cfg['badc_name']:>6s}  {cfg['sadc_name']:>6s}  {note}")
    
    sleep_for = next_tick - time.perf_counter()
    if sleep_for > 0:
        time.sleep(sleep_for)

# Print per-second voltage averages
print(f"\nPer-second voltage means:")
for sec in sorted(voltages_per_sec.keys()):
    vs = voltages_per_sec[sec]
    if vs:
        print(f"  t={sec}s: V={statistics.mean(vs):.4f} ± {statistics.stdev(vs):.4f}  "
              f"(n={len(vs)}, min={min(vs):.4f}, max={max(vs):.4f})")

# Final config check
cfg_final = parse_config(read_config())
print(f"\nFinal config: {cfg_final}")
