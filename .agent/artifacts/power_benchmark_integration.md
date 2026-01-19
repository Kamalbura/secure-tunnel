# Power Benchmark Integration Analysis

> Phase 0.6 • Generated: 2026-01-18
> Status: CRITICAL BUG IDENTIFIED

---

## Question Answers

| Question | Answer |
|----------|--------|
| Is 1000 Hz implemented? | ✅ Yes, in `core/power_monitor.py` |
| Is 1000 Hz achievable? | ⚠️ Yes, but Python GIL may limit to ~900Hz |
| Is benchmark using it? | ❌ **NO** — wrapper is broken |
| Are raw samples preserved? | ❌ **NO** — no data collected |
| Is energy derived correctly? | ❌ **NO** — based on empty list |

---

## Benchmark Power Integration Path

```
sscheduler/sdrone_bench.py
         │
         ▼
┌─────────────────────────────┐
│   DronePowerMonitor         │ ← BROKEN WRAPPER
│   ._sample_loop()           │
│   calls read_metrics()      │ ← METHOD DOES NOT EXIST
│   time.sleep(0.01)          │ ← Would be 100Hz if working
└─────────────────────────────┘
         │
         ▼
┌─────────────────────────────┐
│   core.power_monitor        │ ← WORKS CORRECTLY
│   create_power_monitor()    │
│   Ina219PowerMonitor        │
│   .capture() or .iter_samples()
│   1000 Hz default           │
└─────────────────────────────┘
```

---

## Code Trace

### 1. Wrapper instantiation (sdrone_bench.py:163-164)

```python
from core.power_monitor import create_power_monitor
self._monitor = create_power_monitor(output_dir=output_dir)
```

This creates a valid `Ina219PowerMonitor` at 1000 Hz.

### 2. Broken sampling call (sdrone_bench.py:195-196)

```python
if self._monitor and hasattr(self._monitor, 'read_metrics'):
    reading = self._monitor.read_metrics()
```

**Problem**: `read_metrics()` is not part of the `PowerMonitor` protocol.

### 3. Protocol definition (core/power_monitor.py:117-134)

```python
class PowerMonitor(Protocol):
    sample_hz: int
    
    def capture(...) -> PowerSummary: ...
    def iter_samples(...) -> Iterator[PowerSample]: ...
```

**`read_metrics()` does not exist.**

---

## Verification

### Method Check

```bash
ssh sshdev@100.101.93.23 "cd ~/secure-tunnel && \
  source ~/cenv/bin/activate && \
  python -c 'from core.power_monitor import Ina219PowerMonitor; \
  print([m for m in dir(Ina219PowerMonitor) if not m.startswith(\"_\")])'"
```

Expected output: `['capture', 'iter_samples', 'sign_factor']`
**NOT `read_metrics`.**

---

## Correct Integration

The wrapper should use `iter_samples()`:

```python
def _sample_loop(self):
    """Background sampling using core module's iter_samples."""
    try:
        for sample in self._monitor.iter_samples(duration_s=None):
            if not self._sampling:
                break
            self._samples.append({
                "ts": sample.timestamp_ns,
                "voltage_v": sample.voltage_v,
                "current_a": sample.current_a,
                "power_w": sample.power_w,
            })
    except Exception as e:
        log(f"[POWER] Sampling error: {e}")
```

This would use the core's 1000 Hz timing automatically.
