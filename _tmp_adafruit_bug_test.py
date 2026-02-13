#!/usr/bin/env python3
"""
Test to isolate whether the issue is in:
1. adafruit's set_calibration_32V_2A() method
2. adafruit's bus_voltage property calculation
3. An interaction between them
"""
import time
import smbus2
import board
import busio
from adafruit_ina219 import INA219, ADCResolution

def read_reg_u16(addr, reg):
    """Read 16-bit register via smbus2 (handles byte order)."""
    b = smbus2.SMBus(1)
    hi, lo = b.read_i2c_block_data(addr, reg, 2)
    b.close()
    return (hi << 8) | lo

def write_reg_u16(addr, reg, val):
    """Write 16-bit register via smbus2."""
    b = smbus2.SMBus(1)
    b.write_i2c_block_data(addr, reg, [(val >> 8) & 0xFF, val & 0xFF])
    b.close()

def calc_bus_voltage_correct(raw):
    """Calculate bus voltage the correct way."""
    return ((raw >> 3) & 0x1FFF) * 0.004

print("=" * 70)
print("SCENARIO 1: Default initialization (no calibration, no ADC change)")
print("=" * 70)

i2c = busio.I2C(board.SCL, board.SDA)
ina = INA219(i2c)
time.sleep(0.1)

bv_prop = ina.bus_voltage
bv_raw = read_reg_u16(0x40, 0x02)
bv_calc = calc_bus_voltage_correct(bv_raw)

print(f"adafruit property: {bv_prop:.4f}V")
print(f"raw register: 0x{bv_raw:04X} = {bv_raw}")
print(f"calculated: {bv_calc:.4f}V")
print(f"Match: {abs(bv_prop - bv_calc) < 0.01}")

print("\n" + "=" * 70)
print("SCENARIO 2: After set_calibration_32V_2A() (but no ADC change)")
print("=" * 70)

ina.set_calibration_32V_2A()
time.sleep(0.1)

bv_prop = ina.bus_voltage
bv_raw = read_reg_u16(0x40, 0x02)
bv_calc = calc_bus_voltage_correct(bv_raw)
cfg_raw = read_reg_u16(0x40, 0x00)
cal_raw = read_reg_u16(0x40, 0x05)

print(f"adafruit property: {bv_prop:.4f}V")
print(f"raw register: 0x{bv_raw:04X} = {bv_raw}")
print(f"calculated: {bv_calc:.4f}V")
print(f"config register: 0x{cfg_raw:04X}")
print(f"calibration register: {cal_raw} (0x{cal_raw:04X})")
print(f"Match: {abs(bv_prop - bv_calc) < 0.01}")

print("\n" + "=" * 70)
print("SCENARIO 3: After setting bus_adc_resolution to 9-bit")
print("=" * 70)

ina.bus_adc_resolution = ADCResolution.ADCRES_9BIT_1S
time.sleep(0.2)  # Give time for conversion

bv_prop = ina.bus_voltage
bv_raw = read_reg_u16(0x40, 0x02)
bv_calc = calc_bus_voltage_correct(bv_raw)
cfg_raw = read_reg_u16(0x40, 0x00)

print(f"adafruit property: {bv_prop:.4f}V  <-- EXPECTED ~5.0V, GOT ~3.9V?")
print(f"raw register: 0x{bv_raw:04X} = {bv_raw}")
print(f"calculated: {bv_calc:.4f}V")
print(f"config register: 0x{cfg_raw:04X}")
print(f"Match: {abs(bv_prop - bv_calc) < 0.01}")

if abs(bv_prop - bv_calc) >= 0.01:
    print(f"\n*** MISMATCH DETECTED ***")
    print(f"Difference: {bv_prop - bv_calc:.4f}V")
    print(f"Ratio: {bv_prop / bv_calc:.4f}")
    
print("\n" + "=" * 70)
print("SCENARIO 4: Fresh INA219 with config written directly via smbus2")
print("=" * 70)

del ina, i2c
time.sleep(0.1)

# Create fresh sensor
i2c = busio.I2C(board.SCL, board.SDA)
ina = INA219(i2c)
time.sleep(0.1)

# Write config and calibration directly via smbus2 instead of using set_calibration_32V_2A()
# Config for 32V, 3A, 12-bit: 0x399F
# Calibration for 0.1Ω shunt, 32V range: 4096
write_reg_u16(0x40, 0x00, 0x399F)
write_reg_u16(0x40, 0x05, 4096)
time.sleep(0.1)

bv_prop = ina.bus_voltage
bv_raw = read_reg_u16(0x40, 0x02)
bv_calc = calc_bus_voltage_correct(bv_raw)

print(f"After direct register write (12-bit):")
print(f"adafruit property: {bv_prop:.4f}V")
print(f"calculated: {bv_calc:.4f}V")

# Now set 9-bit
ina.bus_adc_resolution = ADCResolution.ADCRES_9BIT_1S
time.sleep(0.1)

bv_prop = ina.bus_voltage
bv_raw = read_reg_u16(0x40, 0x02)
bv_calc = calc_bus_voltage_correct(bv_raw)

print(f"After setting 9-bit ADC:")
print(f"adafruit property: {bv_prop:.4f}V")
print(f"calculated: {bv_calc:.4f}V")
print(f"Match: {abs(bv_prop - bv_calc) < 0.01}")

print("\n" + "=" * 70)
print("HYPOTHESIS CHECK: Is the problem in set_calibration_32V_2A()?")
print("=" * 70)

# Create a new sensor and set ONLY the ADC resolution without calibration
del ina, i2c

i2c = busio.I2C(board.SCL, board.SDA)
ina = INA219(i2c)
time.sleep(0.1)

# Set 9-bit WITHOUT calling set_calibration_32V_2A()
ina.bus_adc_resolution = ADCResolution.ADCRES_9BIT_1S
time.sleep(0.1)

bv_prop = ina.bus_voltage
bv_raw = read_reg_u16(0x40, 0x02)
bv_calc = calc_bus_voltage_correct(bv_raw)

print(f"After setting 9-bit without calibration:")
print(f"adafruit property: {bv_prop:.4f}V")
print(f"calculated: {bv_calc:.4f}V")
print(f"Match: {abs(bv_prop - bv_calc) < 0.01}")

print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)
print("""
If all scenarios show Match=False for 9-bit, then:
- The bug is in adafruit's bus_voltage property when BADC=0 (9-bit)
- The property is calculating voltage wrong, not the hardware

If scenario 4 shows Match=True but scenario 3 shows Match=False, then:
- The bug is in set_calibration_32V_2A() interaction with the property
- OR there's a caching issue in the property

If scenario 5 shows Match=True, then:
- set_calibration_32V_2A() is the culprit
""")
