# INA219 Power Sensor Verification

> [!IMPORTANT]
> This document records the verified state of INA219 power monitoring.

## Verification Status

| Check | Status | Date |
|-------|--------|------|
| I2C Bus Detection | ✅ PASS | Verified |
| INA219 Address (0x40) | ✅ PASS | Verified |
| Voltage Reading | ✅ PASS | Verified |
| Current Reading | ✅ PASS | Verified |
| Power Calculation | ✅ PASS | Verified |

## Hardware Configuration

```
Device: INA219
I2C Bus: 1
Address: 0x40
Shunt Resistor: 0.1Ω
Max Current: 3.2A
```

## Calibration

| Parameter | Value |
|-----------|-------|
| `calibration_value` | 4096 |
| `current_lsb` | 0.1 mA |
| `power_lsb` | 2 mW |

## Measurement Accuracy

| Metric | Accuracy |
|--------|----------|
| Voltage | ±0.5% |
| Current | ±1% |
| Power | ±1.5% |

## Integration Points

- Source: `core/power_monitor.py`
- Data Path: `logs/drone_power_*.jsonl`
- Sample Rate: 10 Hz (100ms interval)

## Known Limitations

1. High-frequency transients not captured (>10 Hz)
2. USB-powered development may show anomalous readings
3. Battery voltage affects calibration at <3.3V
