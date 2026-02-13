"""
VOLTAGE READING BUG - DIAGNOSIS AND FIX

=============================================================================
PROBLEM STATEMENT
=============================================================================

The INA219 power monitor in metrics_collectors.py reads drastically incorrect
voltages when 9-bit ADC resolution is enabled:

- Expected: ~5.04V (actual 5V USB power rail)
- Actual reading (9-bit ADC): ~3.9V
- Error: -23% (reads 3.9 instead of 5.0)

This affects all power measurements since P = V × I, causing systematic
undercounting of power consumption by ~23%.

Benchmark data affected:
- no-ddos phase: 3.448V (should be ~5.04V)
- ddos-xgboost: 3.461V (should be ~5.04V)
- ddos-txt: 3.838V (should be ~5.04V)


=============================================================================
ROOT CAUSE IDENTIFIED
=============================================================================

BUG LOCATION: adafruit_ina219 library bus_voltage property

When ADCRES_9BIT_1S is set via:
    ina.bus_adc_resolution = ADCResolution.ADCRES_9BIT_1S

The adafruit_ina219 library's bus_voltage property returns incorrect values.

AFFECTED CODE PATH:
    core/metrics_collectors.py, PowerCollector.collect():
    ```python
    metrics["voltage_v"] = self._ina219.bus_voltage  # <-- BUG HERE
    ```

EVIDENCE:
1. Direct register reads (smbus2) return correct 5.04V
2. Slow reads at 12-bit ADC return correct 5.04V ✓
3. 9-bit ADC setting via adafruit property returns wrong 3.9V ✗
4. Raw config register 0x3807 is correct (BADC=0, SADC=0 = 9-bit) ✓
5. Diagnostic test (_tmp_drift_test.py) reproduced bug with metrics_collectors.py

The bug is NOT:
- Hardware issue (register reads work fine)
- Configuration issue (settings are correct)
- I2C contention (CPU/I2C stress tests pass)
- ADC conversion time issue (all safe rates tested)


=============================================================================
FIX IMPLEMENTED
=============================================================================

FILE: core/metrics_collectors.py

CHANGE 1: Add smbus2 import
    - Import smbus2 library for direct I2C register access
    - Gracefully handle if smbus2 is not available

CHANGE 2: Add PowerCollector._read_ina219_bus_voltage_direct() method
    - Reads the bus voltage register (0x02) directly via smbus2
    - Applies correct calculation: ((raw >> 3) & 0x1FFF) * 0.004
    - Returns None if smbus2 unavailable (falls back to property)

CHANGE 3: Update PowerCollector.collect() method
    - When using adafruit backend, call _read_ina219_bus_voltage_direct() first
    - Falls back to self._ina219.bus_voltage if direct read fails
    - Current reading still uses adafruit property (not affected by bug)

CODE DIFF:
    Before:
        metrics["voltage_v"] = self._ina219.bus_voltage
    
    After:
        voltage_v = self._read_ina219_bus_voltage_direct()
        if voltage_v is None:
            voltage_v = self._ina219.bus_voltage
        metrics["voltage_v"] = voltage_v


=============================================================================
VERIFICATION
=============================================================================

Expected behavior after fix:
1. PowerCollector.collect() returns ~5.0V voltage readings
2. Power calculations use correct voltage
3. Benchmark data will show ~30-50% higher power (scaling from 3.6V to 5.0V)
4. Can now re-run benchmarks with correct power collection

Testing:
- Deployment script: _tmp_test_fix.py
- Expected output: "PASS: Voltage reading is correct (~5.0V)"


=============================================================================
NEXT STEPS
=============================================================================

1. ✓ Identify root cause (adafruit_ina219 bus_voltage property bug)
2. ✓ Implement fix (use direct register read workaround)
3. ⏳ Deploy to drone and verify fix works
4. ⏳ Re-run full benchmark (72 suites × 3 phases) with corrected power
5. ⏳ Verify convergence test still passes with new data
6. ⏳ Update dashboard with corrected power metrics


=============================================================================
IMPACT ANALYSIS
=============================================================================

Files modified:
- core/metrics_collectors.py (+30 lines, -3 lines)

Backward compatibility:
- ✓ Falls back to adafruit property if smbus2 unavailable
- ✓ No API changes to PowerCollector interface
- ✓ Existing code calling collect() continues to work

Dependencies:
- smbus2 already required by the codebase (used in core/power_monitor.py)
- No new external dependencies introduced


=============================================================================
TECHNICAL NOTES
=============================================================================

INA219 Register Layout for Bus Voltage (Register 0x02):
  Bits [15:3]   = Bus voltage (13-bit unsigned)
  Bits [2:0]    = Reserved (always 0)
  Resolution    = 4 mV per LSB
  Formula       = raw_value * 4 mV
                = (register >> 3) * 0.004 V

Example reading:
  Register 0x02 = 0x5248 (binary: 0101001001001000)
  Shifted right 3: 0x5248 >> 3 = 0x0A49 = 2633 decimal
  Voltage = 2633 * 0.004 V = 10.532V ✓

The adafruit library's bug appears to be in how it handles the property
getter when BADC configuration has been changed. The workaround reads
the register directly, bypassing the buggy property implementation.


=============================================================================
WORKAROUND LIMITATIONS
=============================================================================

This fix is a workaround, not a fix to the adafruit library itself.

Ideal solution would be to:
1. Report bug to adafruit/circuitpython repository
2. Submit PR to fix bus_voltage property with 9-bit ADC
3. Update to fixed version once available

For now, the direct register read is reliable and matches the method
used in core/power_monitor.py which has proven to work correctly.
"""
