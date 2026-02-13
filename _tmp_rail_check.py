#!/usr/bin/env python3
"""
The voltage readings are consistently 3.9-4.1V (NOT 5V) right from the start.
This suggests the problem is in how bus_voltage is read AFTER setting 9-bit ADC.

Hypothesis: The adafruit library's bus_voltage property is computing the value
incorrectly, OR reading from the wrong register, OR the calibration register
is affecting the voltage calculation.

Let me:
1. Read the raw bus voltage register via smbus2
2. Compare to adafruit's bus_voltage property
3. Check the calibration register
4. Check if there's a scaling issue
"""
import time
import smbus2
import board, busio
from adafruit_ina219 import INA219, ADCResolution

def read_reg_16(addr, reg):
    """Read raw 16-bit register."""
    b = smbus2.SMBus(1)
    raw = b.read_word_data(addr, reg)
    b.close()
    return ((raw & 0xFF) << 8) | ((raw >> 8) & 0xFF)

# Initialize the same way the code does
i2c = busio.I2C(board.SCL, board.SDA)
ina = INA219(i2c)
ina.set_calibration_32V_2A()
ina.bus_adc_resolution = ADCResolution.ADCRES_9BIT_1S
ina.shunt_adc_resolution = ADCResolution.ADCRES_9BIT_1S

print("=" * 70)
print("COMPARING ADAFRUIT PROPERTY vs RAW REGISTER")
print("=" * 70)

# Check calibration
cfg_raw = read_reg_16(0x40, 0x00)
cal_raw = read_reg_16(0x40, 0x05)
print(f"Config register: 0x{cfg_raw:04X}")
print(f"Calibration register: {cal_raw} (0x{cal_raw:04X})")

# Let's read the bus voltage register as-is
bus_reg = read_reg_16(0x40, 0x02)
print(f"\nBUS VOLTAGE REGISTER: 0x{bus_reg:04X}")

# Parse it according to INA219 datasheet
# Bits [15:3] = voltage in 4mV units, bits [2:0] = reserved
bus_v_raw = (bus_reg >> 3)  # extract 13-bit value
bus_v_volts = bus_v_raw * 0.004  # 4mV per LSB
print(f"  Raw 13-bit value: 0x{bus_v_raw:04X} = {bus_v_raw}")
print(f"  Calculated voltage: {bus_v_volts:.4f}V")

# Now compare to adafruit's bus_voltage
adafruit_bv = ina.bus_voltage
print(f"  Adafruit bus_voltage property: {adafruit_bv:.4f}V")

# Check if they match
if abs(adafruit_bv - bus_v_volts) < 0.01:
    print(f"  ✓ MATCH")
else:
    print(f"  *** MISMATCH: adafruit={adafruit_bv}, raw_calc={bus_v_volts} ***")

# Read shunt voltage register for comparison
shunt_reg = read_reg_16(0x40, 0x01)
shunt_v_raw = shunt_reg
if shunt_v_raw > 32767:
    shunt_v_raw -= 65536
shunt_v_volts = shunt_v_raw * 0.00001  # 10µV per LSB
print(f"\nSHUNT VOLTAGE REGISTER: 0x{shunt_reg:04X}")
print(f"  Raw value (signed): {shunt_v_raw}")
print(f"  Calculated voltage: {shunt_v_volts:.6f}V")
adafruit_sv = ina.shunt_voltage
print(f"  Adafruit shunt_voltage property: {adafruit_sv:.6f}V")

# What if we're somehow reading shunt_voltage as bus_voltage?
# Or what if the 4mV scaling is wrong?
# Let's try other scalings
print(f"\nTrying different 4mV/LSB scalings:")
for shift in range(15):
    v = (bus_reg >> shift) * 0.004
    if 4.5 < v < 5.5:  # Look for values near 5V
        print(f"  Shift={shift}: ({bus_reg} >> {shift}) * 0.004 = {v:.4f}V")

# Check if the register is being read in the wrong byte order
bus_reg_swapped = ((bus_reg & 0xFF) << 8) | ((bus_reg >> 8) & 0xFF)
bus_v_swapped = (bus_reg_swapped >> 3) * 0.004
print(f"\nIf bytes were swapped: raw_reg=0x{bus_reg:04X} -> swapped=0x{bus_reg_swapped:04X}")
print(f"  -> voltage = {bus_v_swapped:.4f}V")

# Let's do a slow read (500ms apart) and check if voltage changes
print(f"\n" + "=" * 70)
print("SLOW READS (500ms apart, checking for stabilization)")
print("=" * 70)
for i in range(5):
    time.sleep(0.5)
    v_prop = ina.bus_voltage
    v_reg = (read_reg_16(0x40, 0x02) >> 3) * 0.004
    c = abs(ina.current)
    print(f"  [{i}] Property={v_prop:.4f}V  Register={v_reg:.4f}V  Current={c:.0f}mA")

# Try resetting the config to defaults and re-reading
print(f"\n" + "=" * 70)
print("RESET AND RE-INIT")
print("=" * 70)

# Write config to default 16V range, 12-bit, continuous
default_cfg = 0x399F  # BRNG=1, PGA=3, BADC=3, SADC=3, MODE=7
b = smbus2.SMBus(1)
b.write_word_data(0x40, 0x00, ((default_cfg & 0xFF) << 8) | ((default_cfg >> 8) & 0xFF))
time.sleep(0.1)
b.close()

# Re-create sensor object
del i2c, ina

i2c = busio.I2C(board.SCL, board.SDA)
ina = INA219(i2c)
ina.set_calibration_32V_2A()
time.sleep(0.1)

# Try reading WITHOUT setting ADC (use default 12-bit)
v_default_12bit = ina.bus_voltage
print(f"After fresh init (default 12-bit): {v_default_12bit:.4f}V")

# Now set to 9-bit
ina.bus_adc_resolution = ADCResolution.ADCRES_9BIT_1S
ina.shunt_adc_resolution = ADCResolution.ADCRES_9BIT_1S
time.sleep(0.1)

v_after_9bit = ina.bus_voltage
print(f"After setting to 9-bit: {v_after_9bit:.4f}V")

# Read raw register
v_reg_9bit = (read_reg_16(0x40, 0x02) >> 3) * 0.004
print(f"Raw register calculation (9-bit): {v_reg_9bit:.4f}V")

print("\n" + "=" * 70)
"""
Check INA219 wiring: which rail is it on?
Measure bus voltage vs RPi rail voltages.
"""
import sys, time, subprocess
sys.path.insert(0, "/home/dev/secure-tunnel")

import board
import adafruit_ina219

i2c = board.I2C()
sensor = adafruit_ina219.INA219(i2c)
sensor.set_calibration_32V_2A()

print("=" * 60)
print("INA219 RAIL IDENTIFICATION")
print("=" * 60)

# 1. Multiple calibrations to see if first-read artifact
print("\n[First-read test - 20 rapid reads WITHOUT sleep]")
for i in range(20):
    v = sensor.bus_voltage
    c = sensor.current
    print(f"  [{i:2d}] Vbus={v:.4f}V  I={c:.2f}mA  Vshunt={sensor.shunt_voltage:.6f}V")

# 2. Try different calibrations
print("\n[Calibration 16V/400mA - higher resolution]")
sensor.set_calibration_16V_400mA()
time.sleep(0.1)
for i in range(5):
    v = sensor.bus_voltage
    c = sensor.current
    sh = sensor.shunt_voltage
    print(f"  [{i}] Vbus={v:.4f}V  I={c:.4f}mA  Vshunt={sh:.6f}V  Full={v+sh:.4f}V")
    time.sleep(0.05)

print("\n[Back to 32V/2A calibration]")
sensor.set_calibration_32V_2A()
time.sleep(0.1)
for i in range(5):
    v = sensor.bus_voltage
    c = sensor.current
    sh = sensor.shunt_voltage
    print(f"  [{i}] Vbus={v:.4f}V  I={c:.4f}mA  Vshunt={sh:.6f}V  Full={v+sh:.4f}V")
    time.sleep(0.05)

# 3. Check RPi supply voltage from sysfs
print("\n[RPi System Voltages]")
try:
    result = subprocess.run(["vcgencmd", "measure_volts", "core"], capture_output=True, text=True, timeout=5)
    print(f"  Core voltage: {result.stdout.strip()}")
except: pass
try:
    result = subprocess.run(["vcgencmd", "measure_volts", "sdram_c"], capture_output=True, text=True, timeout=5)
    print(f"  SDRAM_C voltage: {result.stdout.strip()}")
except: pass
try:
    result = subprocess.run(["vcgencmd", "measure_volts", "sdram_i"], capture_output=True, text=True, timeout=5)
    print(f"  SDRAM_I voltage: {result.stdout.strip()}")
except: pass
try:
    result = subprocess.run(["vcgencmd", "measure_volts", "sdram_p"], capture_output=True, text=True, timeout=5)
    print(f"  SDRAM_P voltage: {result.stdout.strip()}")
except: pass

# 4. Read rpi_volt brownout alarm
try:
    with open("/sys/class/hwmon/hwmon1/in0_lcrit_alarm") as f:
        alarm = f.read().strip()
    print(f"  RPi voltage brownout alarm (hwmon1): {alarm}")
except: pass

# 5. Check CPU temp
try:
    with open("/sys/class/hwmon/hwmon0/temp1_input") as f:
        temp = int(f.read().strip()) / 1000.0
    print(f"  CPU temperature: {temp:.1f}°C")
except: pass

# 6. Check throttle details  
try:
    result = subprocess.run(["vcgencmd", "get_throttled"], capture_output=True, text=True, timeout=5)
    val_str = result.stdout.strip().split("=")[1]
    val = int(val_str, 0)
    print(f"\n[Throttle Status: {val_str}]")
    flags = {
        0x1: "Under-voltage NOW",
        0x2: "ARM freq capped NOW", 
        0x4: "Currently throttled NOW",
        0x8: "Soft temp limit NOW",
        0x10000: "Under-voltage PAST",
        0x20000: "ARM freq capping PAST",
        0x40000: "Throttling PAST",
        0x80000: "Soft temp limit PAST",
    }
    for bit, desc in flags.items():
        status = "YES" if val & bit else "no"
        print(f"  {desc}: {status}")
except: pass

# 7. Final assessment
print(f"\n{'='*60}")
mean_v = sum(sensor.bus_voltage for _ in range(10)) / 10
print(f"Mean bus voltage (10 reads): {mean_v:.4f}V")
if 3.0 < mean_v < 3.6:
    print(">>> INA219 Vin+ is connected to 3.3V rail")
    print(">>> Power readings are valid for 3.3V rail consumption")
    print(">>> To measure total system power, connect Vin+ to 5V USB supply")
elif 4.5 < mean_v < 5.5:
    print(">>> INA219 Vin+ is connected to 5V supply rail") 
    print(">>> Power readings represent total system power")
else:
    print(f">>> Unusual voltage {mean_v:.2f}V - check wiring")
print()
