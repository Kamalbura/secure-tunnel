#!/usr/bin/env python3
"""
Analyze the adafruit_ina219 library code to understand the bus_voltage property.

The issue: After setting ADCRES_9BIT_1S, bus_voltage reads ~3.9V instead of ~5.0V
The symptom: 3.9/5.0 ≈ 0.773

This suggests a register scaling error or the property reading the wrong register.
"""

# Let's examine what the adafruit library actually does
# by inspecting the source code

try:
    import adafruit_ina219
    print("✓ adafruit_ina219 imported successfully")
    print(f"  Module location: {adafruit_ina219.__file__}")
except ImportError as e:
    print(f"✗ Failed to import: {e}")
    exit(1)

# Let's check the INA219 class
from adafruit_ina219 import INA219, ADCResolution
import inspect

print("\n" + "=" * 70)
print("BUS_VOLTAGE PROPERTY DEFINITION")
print("=" * 70)

# Get the bus_voltage property
bv_prop = getattr(INA219, 'bus_voltage')
print(f"bus_voltage type: {type(bv_prop)}")
print(f"bus_voltage is property: {isinstance(bv_prop, property)}")

if isinstance(bv_prop, property):
    # Get the getter
    getter = bv_prop.fget
    print(f"\nGetter source code:")
    try:
        source = inspect.getsource(getter)
        print(source)
    except Exception as e:
        print(f"Could not get source: {e}")

# Let's check for any scaling factors or constants
print("\n" + "=" * 70)
print("INA219 CLASS ATTRIBUTES AND METHODS")
print("=" * 70)

# List all attributes that might be related to voltage calculation
for name in dir(INA219):
    if 'volt' in name.lower() or 'scale' in name.lower() or 'lsb' in name.lower() or 'calibr' in name.lower():
        try:
            val = getattr(INA219, name)
            if not callable(val) and not name.startswith('_'):
                print(f"  {name}: {val}")
        except:
            pass

# Let's check the module-level constants
print("\n" + "=" * 70)
print("MODULE-LEVEL CONSTANTS")
print("=" * 70)

adafruit_ina219_module = __import__('adafruit_ina219')
for name in dir(adafruit_ina219_module):
    if not name.startswith('_'):
        try:
            val = getattr(adafruit_ina219_module, name)
            if isinstance(val, (int, float)):
                print(f"  {name}: {val}")
        except:
            pass

# Let's check what happens with the calibration register
print("\n" + "=" * 70)
print("CHECKING CALIBRATION BEHAVIOR")
print("=" * 70)

print("""
When set_calibration_32V_2A() is called:
- It sets calibration register to configure the scaling
- The default formula for bus voltage is: voltage = (raw_value >> 3) * 0.004V per LSB

When ADCRES_9BIT_1S is set:
- The config register bits [12:9] change from 0011 (12-bit) to 0000 (9-bit)
- This affects the ADC conversion TIME, not the register format
- The register format should STILL be 13-bit >> 3 = raw value

HYPOTHESIS: The adafruit library might be caching a scaling factor that gets 
invalidated when ADC resolution changes, OR there's a bug in how it reads
the register after the config change.
""")

# Let's try to instantiate and see what happens
print("\n" + "=" * 70)
print("DYNAMIC TEST: Create instance and inspect")
print("=" * 70)

import board
import busio

try:
    i2c = busio.I2C(board.SCL, board.SDA)
    ina = INA219(i2c)
    
    print("\nAfter initialization (defaults):")
    print(f"  bus_voltage: {ina.bus_voltage:.4f}V")
    print(f"  Current backend: {ina._Ina219__i2c_device}")
    
    # Check if there are any cached values
    print("\nInstance attributes that might cache values:")
    for attr in dir(ina):
        if attr.startswith('_') and not attr.startswith('__'):
            try:
                val = getattr(ina, attr)
                if isinstance(val, (int, float, type(None))):
                    print(f"  {attr}: {val}")
            except:
                pass
    
    # Now set calibration
    ina.set_calibration_32V_2A()
    print(f"\nAfter set_calibration_32V_2A():")
    print(f"  bus_voltage: {ina.bus_voltage:.4f}V")
    
    # Now set 9-bit
    ina.bus_adc_resolution = ADCResolution.ADCRES_9BIT_1S
    print(f"\nAfter setting bus_adc_resolution = ADCRES_9BIT_1S:")
    print(f"  bus_voltage: {ina.bus_voltage:.4f}V")
    
    # Read the raw config register via smbus2 to see what actually happened
    import smbus2
    bus = smbus2.SMBus(1)
    raw_config = bus.read_word_data(0x40, 0x00)
    # smbus2 returns little-endian, so swap bytes
    config = ((raw_config & 0xFF) << 8) | ((raw_config >> 8) & 0xFF)
    print(f"  Config register: 0x{config:04X}")
    print(f"    Bits [15:14] (BRNG): {(config >> 14) & 0x3}")
    print(f"    Bits [13:11] (PGA): {(config >> 11) & 0x7}")
    print(f"    Bits [10:7] (BADC): {(config >> 7) & 0xF}")
    print(f"    Bits [6:3] (SADC): {(config >> 3) & 0xF}")
    print(f"    Bits [2:0] (MODE): {config & 0x7}")
    
    # Read the bus voltage register
    raw_bv = bus.read_word_data(0x40, 0x02)
    bv_register = ((raw_bv & 0xFF) << 8) | ((raw_bv >> 8) & 0xFF)
    print(f"  Bus voltage register: 0x{bv_register:04X}")
    print(f"    Bits [15:3] (value): {bv_register >> 3}")
    print(f"    Calculated: ({bv_register >> 3}) * 0.004 = {(bv_register >> 3) * 0.004:.4f}V")
    
    bus.close()
    
except Exception as e:
    print(f"Error during test: {e}")
    import traceback
    traceback.print_exc()
