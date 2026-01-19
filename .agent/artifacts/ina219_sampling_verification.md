# INA219 Sampling Verification

> Phase 0.6 • Generated: 2026-01-18
> Status: CRITICAL FINDINGS

---

## Summary

| Claim (Phase 0.5) | Reality | Verdict |
|-------------------|---------|---------|
| 100 Hz sampling | 1000 Hz default in core | ❌ INCORRECT |
| Continuous sampling | Broken wrapper | ❌ CRITICAL BUG |

---

## Core Module Analysis: `core/power_monitor.py`

### Default Configuration (Lines 34-38)

```python
_DEFAULT_SAMPLE_HZ = int(os.getenv("INA219_SAMPLE_HZ", "1000"))  # 1000 Hz!
_DEFAULT_SHUNT_OHM = float(os.getenv("INA219_SHUNT_OHM", "0.1"))
_DEFAULT_I2C_BUS = int(os.getenv("INA219_I2C_BUS", "1"))
_DEFAULT_ADDR = int(os.getenv("INA219_ADDR", "0x40"), 16)
```

### ADC Profiles (Lines 79-83)

| Profile | Bus ADC | Shunt ADC | Settle Time | Max Hz |
|---------|---------|-----------|-------------|--------|
| highspeed | 0x0080 | 0x0000 | 0.4ms | **1100** |
| balanced | 0x0400 | 0x0018 | 1.0ms | 900 |
| precision | 0x0400 | 0x0048 | 2.0ms | 450 |

### Sampling Implementation (Lines 220-256)

```python
dt = 1.0 / float(self.sample_hz)       # 1ms for 1000Hz
next_tick = time.perf_counter()

while True:
    # ... read INA219 ...
    next_tick += dt
    sleep_for = next_tick - time.perf_counter()
    if sleep_for > 0:
        time.sleep(sleep_for)          # Fixed-interval timing
```

**This is correct fixed-rate sampling at 1000 Hz.**

---

## Benchmark Wrapper: `sscheduler/sdrone_bench.py`

### DronePowerMonitor (Lines 148-214)

```python
class DronePowerMonitor:
    def __init__(self, output_dir: Path):
        from core.power_monitor import create_power_monitor
        self._monitor = create_power_monitor(output_dir=output_dir)  # 1000Hz
        # ...
    
    def _sample_loop(self):
        """Background sampling at ~100Hz."""  # WRONG COMMENT
        while self._sampling:
            if self._monitor and hasattr(self._monitor, 'read_metrics'):
                reading = self._monitor.read_metrics()  # ❌ METHOD DOES NOT EXIST
            time.sleep(0.01)  # 100Hz override
```

### CRITICAL BUGS

1. **`read_metrics()` does not exist** in the `PowerMonitor` protocol
2. The wrapper IGNORES the core's 1000Hz sampling
3. Wrapper implements its own 100Hz loop but never gets data

---

## Impact Analysis

| Component | Expected | Actual |
|-----------|----------|--------|
| Core power_monitor | 1000 Hz | ✅ Correct |
| Benchmark wrapper | Continuous | ❌ BROKEN |
| Samples collected | ~10,000/10s | **0** |
| Power metrics | Valid | **All zeros** |

---

## Verification Commands (SSH)

To verify core module works:
```bash
ssh sshdev@100.101.93.23 "cd ~/secure-tunnel && \
  source ~/cenv/bin/activate && \
  python -c 'from core.power_monitor import create_power_monitor; \
  from pathlib import Path; \
  m = create_power_monitor(Path(\"/tmp\")); \
  s = m.capture(label=\"test\", duration_s=1.0); \
  print(f\"Samples: {s.samples}, Rate: {s.sample_rate_hz:.1f} Hz\")'"
```

---

## Root Cause

The `DronePowerMonitor` wrapper in `sdrone_bench.py`:
1. Creates a valid `Ina219PowerMonitor` (1000Hz capable)
2. But then tries to call `read_metrics()` which doesn't exist
3. Falls through to exception handler and collects nothing
4. Returns empty sample list

---

## Recommended Fix

Replace broken wrapper with direct use of `capture()` or `iter_samples()`:

```python
# Instead of:
self._monitor.read_metrics()  # BROKEN

# Use:
for sample in self._monitor.iter_samples(duration_s=10.0):
    self._samples.append({
        "ts": sample.timestamp_ns,
        "voltage_v": sample.voltage_v,
        "current_a": sample.current_a,
        "power_w": sample.power_w,
    })
```
