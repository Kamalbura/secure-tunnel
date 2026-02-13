#!/usr/bin/env python3
"""Careful INA219 rail voltage diagnosis.
Determine if the sensor is on 3.3V or 5V rail.
"""
import time

# ── Part 1: Slow reads via adafruit (no aliasing) ──
print("=" * 60)
print("PART 1: SLOW READS (adafruit, 500ms apart, 12-bit)")
print("=" * 60)
try:
    import board, busio
    from adafruit_ina219 import INA219

    i2c = busio.I2C(board.SCL, board.SDA)
    ina = INA219(i2c)
    ina.set_calibration_32V_2A()

    for i in range(10):
        time.sleep(0.5)
        bv = ina.bus_voltage
        sv = ina.shunt_voltage
        cur = ina.current
        print(f"  [{i}] bus={bv:.4f}V  shunt={sv:.6f}V  "
              f"full={bv+sv:.4f}V  I={cur:.1f}mA")
except Exception as e:
    print(f"  ERROR: {e}")

# ── Part 2: Raw register reads via smbus2 ──
print()
print("=" * 60)
print("PART 2: RAW REGISTER READS (smbus2, 500ms apart)")
print("=" * 60)
import smbus2

bus = smbus2.SMBus(1)

def read_reg_16(addr, reg):
    raw = bus.read_word_data(addr, reg)
    return ((raw & 0xFF) << 8) | ((raw >> 8) & 0xFF)

# Read config
raw_cfg = read_reg_16(0x40, 0x00)
brng = (raw_cfg >> 13) & 1
pga = (raw_cfg >> 11) & 3
badc = (raw_cfg >> 7) & 0xF
sadc = (raw_cfg >> 3) & 0xF
mode = raw_cfg & 7
print(f"  CONFIG: 0x{raw_cfg:04X}")
print(f"    BRNG={brng} ({'32V' if brng else '16V'} range)")
print(f"    PGA={pga} (gain: {['±40mV','±80mV','±160mV','±320mV'][pga]})")
print(f"    BADC=0x{badc:X}  SADC=0x{sadc:X}")
print(f"    MODE={mode} ({'shunt+bus continuous' if mode==7 else mode})")

raw_cal = read_reg_16(0x40, 0x05)
print(f"    Calibration: {raw_cal}")
print()

for i in range(10):
    time.sleep(0.5)
    raw_bus = read_reg_16(0x40, 0x02)
    voltage = (raw_bus >> 3) * 0.004
    cnvr = (raw_bus >> 1) & 1
    ovf = raw_bus & 1

    raw_shunt = read_reg_16(0x40, 0x01)
    if raw_shunt > 32767:
        raw_shunt -= 65536
    shunt_v = raw_shunt * 0.00001

    print(f"  [{i}] raw=0x{raw_bus:04X}  bus={voltage:.4f}V  "
          f"cnvr={cnvr} ovf={ovf}  shunt={shunt_v:.6f}V  "
          f"total={voltage+shunt_v:.4f}V")

# ── Part 3: Force a known config and re-read ──
print()
print("=" * 60)
print("PART 3: FORCE 32V/2A CALIBRATION + 12-BIT + SLOW READ")
print("=" * 60)

# Write config: BRNG=1(32V), PGA=3(±320mV), BADC=3(12-bit), SADC=3(12-bit), MODE=7
# Config = 0b0_01_11_0011_0011_111 = 0x399F
new_cfg = 0x399F
bus.write_word_data(0x40, 0x00, ((new_cfg & 0xFF) << 8) | ((new_cfg >> 8) & 0xFF))
time.sleep(0.1)

# Write calibration for 32V/2A: Cal = trunc(0.04096 / (Current_LSB * Rshunt))
# For 2A max, Current_LSB = 2/32768 = 61.035µA
# Rshunt = 0.1Ω (standard for most INA219 modules)
# Cal = trunc(0.04096 / (0.00006104 * 0.1)) = trunc(6711.5) = 6711
cal_val = 4096  # adafruit uses 4096 for 32V/2A
bus.write_word_data(0x40, 0x05, ((cal_val & 0xFF) << 8) | ((cal_val >> 8) & 0xFF))
time.sleep(0.1)

# Verify config
raw_cfg2 = read_reg_16(0x40, 0x00)
raw_cal2 = read_reg_16(0x40, 0x05)
print(f"  Config after write: 0x{raw_cfg2:04X}")
print(f"  Calibration after write: {raw_cal2}")
print()

for i in range(10):
    time.sleep(0.5)
    raw_bus = read_reg_16(0x40, 0x02)
    voltage = (raw_bus >> 3) * 0.004
    cnvr = (raw_bus >> 1) & 1
    ovf = raw_bus & 1

    raw_shunt = read_reg_16(0x40, 0x01)
    if raw_shunt > 32767:
        raw_shunt -= 65536
    shunt_v = raw_shunt * 0.00001

    raw_cur = read_reg_16(0x40, 0x04)
    if raw_cur > 32767:
        raw_cur -= 65536

    print(f"  [{i}] bus={voltage:.4f}V  shunt={shunt_v:.6f}V  "
          f"total={voltage+shunt_v:.4f}V  cnvr={cnvr}  "
          f"raw_current={raw_cur}")

bus.close()

# ── Part 4: Check RPi GPIO voltages for reference ──
print()
print("=" * 60)
print("PART 4: REFERENCE VOLTAGES (vcgencmd)")
print("=" * 60)
import subprocess
try:
    r = subprocess.run(["vcgencmd", "measure_volts", "core"],
                       capture_output=True, text=True, timeout=2)
    print(f"  Core voltage: {r.stdout.strip()}")
except:
    print("  Core voltage: unavailable")

try:
    r = subprocess.run(["vcgencmd", "measure_volts", "sdram_c"],
                       capture_output=True, text=True, timeout=2)
    print(f"  SDRAM-C voltage: {r.stdout.strip()}")
except:
    print("  SDRAM-C voltage: unavailable")

try:
    r = subprocess.run(["vcgencmd", "get_throttled"],
                       capture_output=True, text=True, timeout=2)
    val = r.stdout.strip()
    print(f"  Throttle status: {val}")
    if "0x" in val:
        v = int(val.split("=")[1], 16)
        flags = {
            0: "Under-voltage NOW",
            1: "Freq capped NOW",
            2: "Throttled NOW",
            3: "Soft temp limit NOW",
            16: "Under-voltage occurred",
            17: "Freq capped occurred",
            18: "Throttled occurred",
            19: "Soft temp limit occurred",
        }
        for bit, desc in flags.items():
            if v & (1 << bit):
                print(f"    [{bit}] {desc}")
except:
    print("  Throttle status: unavailable")

# ── Part 5: Read /sys voltage info if available ──
print()
print("=" * 60)
print("PART 5: SYSFS VOLTAGE INFO")
print("=" * 60)
import os, glob
for pat in ["/sys/class/hwmon/*/name",
            "/sys/class/hwmon/*/in*_input",
            "/sys/bus/iio/devices/*/in_voltage*_raw"]:
    for path in sorted(glob.glob(pat)):
        try:
            val = open(path).read().strip()
            print(f"  {path} = {val}")
        except:
            pass

# Also check what i2c devices exist
print()
print("=" * 60)
print("PART 6: I2C DEVICE SCAN")
print("=" * 60)
try:
    r = subprocess.run(["i2cdetect", "-y", "1"],
                       capture_output=True, text=True, timeout=5)
    print(r.stdout)
except:
    print("  i2cdetect not available")

print()
print("=" * 60)
print("DIAGNOSIS COMPLETE")
print("=" * 60)
