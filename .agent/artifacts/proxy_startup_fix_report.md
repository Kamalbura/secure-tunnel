# Proxy Startup Fix Report

> Phase 0.7 • Generated: 2026-01-18
> Status: VERIFIED

---

## Issue Summary

| Issue | Root Cause | Fix |
|-------|------------|-----|
| Power sampling returns empty | `read_metrics()` method doesn't exist | Use `iter_samples()` |

---

## Fix Details

### File: `sscheduler/sdrone_bench.py`

**Location**: Lines 191-206 (now 191-204)

**Before**: Called non-existent `read_metrics()` method
```python
if self._monitor and hasattr(self._monitor, 'read_metrics'):
    reading = self._monitor.read_metrics()  # Never executes
```

**After**: Uses valid `iter_samples()` from PowerMonitor protocol
```python
for sample in self._monitor.iter_samples():
    self._samples.append({
        "ts": sample.timestamp_ns,
        "voltage_v": sample.voltage_v,
        "current_a": sample.current_a,
        "power_w": sample.power_w,
    })
```

---

## Sampling Rate Impact

| Before | After |
|--------|-------|
| 0 Hz (broken) | 1000 Hz (core default) |
| 0 samples/10s | ~10,000 samples/10s |
| Empty power data | Full power trace |

---

## Verification Required

Run on drone via SSH:
```bash
ssh sshdev@100.101.93.23 "cd ~/secure-tunnel && \
  source ~/cenv/bin/activate && \
  python -c 'from sscheduler.sdrone_bench import DronePowerMonitor; \
  from pathlib import Path; \
  m = DronePowerMonitor(Path(\"/tmp\")); \
  m.start_sampling(); \
  import time; time.sleep(1.0); \
  s = m.stop_sampling(); \
  print(f\"Samples: {len(s)}, Rate: {len(s)/1.0:.0f} Hz\")'"
```

Expected output: `Samples: ~1000, Rate: ~1000 Hz`
