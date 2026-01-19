# Benchmark Readiness Update

> Phase 0.6 • Generated: 2026-01-18
> Status: **NOT READY**

---

## Verdict: ❌ NOT READY

**Critical bug prevents valid power data collection.**

---

## Phase 0.5 → Phase 0.6 Delta

| Claim | Phase 0.5 | Phase 0.6 Verification |
|-------|-----------|------------------------|
| Power sampling rate | 100 Hz | **1000 Hz in core, 100 Hz attempted in wrapper** |
| Power data collected | Yes | **NO — wrapper calls non-existent method** |
| Samples per 10s cycle | ~1000 | **0 (empty list)** |
| Energy calculation | avg_power × duration | **0.0 (based on empty samples)** |

---

## Blocking Issues

### 1. `DronePowerMonitor.read_metrics()` does not exist

```python
# sdrone_bench.py:195-196
if self._monitor and hasattr(self._monitor, 'read_metrics'):
    reading = self._monitor.read_metrics()  # ❌ NEVER EXECUTES
```

The `hasattr()` check fails because `read_metrics` is not in the protocol.

### 2. Empty sample list returned

```python
# sdrone_bench.py:214
return self._samples.copy()  # Returns []
```

### 3. All power metrics are zero

```python
# sdrone_bench.py:218-223
if not samples or duration_s <= 0:
    return {
        "power_avg_w": 0, "power_peak_w": 0,
        "energy_total_j": 0, ...
    }
```

---

## Required Fix Before Data Freeze

The `DronePowerMonitor._sample_loop()` in `sscheduler/sdrone_bench.py` must be fixed to use valid PowerMonitor methods:

**Option A**: Use `iter_samples()` for streaming

**Option B**: Use `capture()` for batch

---

## Updated Readiness Matrix

| Metric Category | Status |
|-----------------|--------|
| A. Run Context | ✅ Ready |
| B. Crypto Identity | ✅ Ready |
| C. Lifecycle | ✅ Ready |
| D. Handshake | ✅ Ready |
| E. Crypto Primitives | ⚠️ Partial |
| F. Rekey | N/A |
| G. Data Plane | ✅ Ready |
| H. Latency | ✅ Ready |
| I-L. MAVLink | ✅ Ready |
| M. Control Plane | ✅ Ready |
| N. System Drone | ✅ Ready |
| O. System GCS | Removed |
| **P. Power/Energy** | ❌ **BROKEN** |
| Q. Observability | ⚠️ Depends on P |
| R. Validation | ✅ Ready |

---

## Action Required

1. **Fix `DronePowerMonitor._sample_loop()`** to use `iter_samples()` or `capture()`
2. **Verify fix** via SSH test run
3. **Re-run Phase 0.6** verification
4. **Update readiness** to READY

---

## Decision

**DO NOT proceed to Data Freeze (Phase A)** until power monitoring is fixed.
