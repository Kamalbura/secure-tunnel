# Detective Bug Dossier

> Phase 0.9 • Generated: 2026-01-19
> Status: ANALYSIS COMPLETE

---

## Confirmed Bugs (Fixed)

| Bug | Location | Fix |
|-----|----------|-----|
| `read_metrics()` non-existent | `sdrone_bench.py:195` | ✅ Fixed (Phase 0.7) |

---

## Suspected Issues (Low Risk)

### 1. Crypto Primitive Timing Often Zero

**Location**: `benchmark_policy.py:251-255`

**Issue**: Primitive timings (`kem_keygen_ms`, `sig_sign_ms`, etc.) are read from status file but may not be populated by the proxy.

**Risk**: Low — affects detailed breakdown only, not aggregate metrics.

**Evidence**:
```python
m.kem_keygen_ms = handshake_metrics.get("kem_keygen_max_ms", 0.0)
m.kem_encaps_ms = handshake_metrics.get("kem_encaps_max_ms", 0.0)
```

---

### 2. Clock Sync Assumed, Not Verified

**Location**: One-way latency calculation

**Issue**: Latency is computed from embedded `ts_ns` in UDP packets, which requires synchronized clocks between GCS and Drone.

**Risk**: Medium — affects latency accuracy.

**Mitigation**: Run NTP sync before benchmark: `sudo ntpdate time.google.com`

---

### 3. No Explicit Error on Power Monitor Failure

**Location**: `sdrone_bench.py:168`

**Issue**: If INA219 init fails, `_available` is set to `False` but benchmark continues silently with zero power data.

**Risk**: Low — power data will be zeros, but other metrics collected.

**Evidence**:
```python
except Exception as e:
    log(f"[POWER] Not available: {e}")
```

---

## Risky Assumptions

| Assumption | Risk | Validation |
|------------|------|------------|
| GCS always faster than Drone | Low | GCS is Windows PC |
| 10s is enough for handshake | Low | Typical <5s |
| INA219 at I2C 0x40 | Low | Previously verified |
| MAVProxy starts in 2s | Medium | May vary |

---

## Race Conditions (None Found)

Threading is used for:
- Power sampling (`DronePowerMonitor._sample_loop`)
- System metrics (`SystemMetricsCollector._sample_loop`)
- MAVLink collection (`MavLinkMetricsCollector._listen_loop`)

All use proper `threading.Event()` for stop signaling and safe list appends.

---

## Timing Drift Analysis

**Policy enforcement**: `benchmark_policy.py:319`
```python
if elapsed_on_suite >= self.cycle_interval_s:
```

Uses `time.monotonic()` which is immune to system clock changes.

**Drift risk**: None — monotonic clock is stable.

---

## Comparison to Secure Systems Best Practices

| Practice | This System | Status |
|----------|-------------|--------|
| Hardware timestamping | No | Software OK for benchmark |
| Replay protection | Yes (AEAD nonce) | ✅ |
| Forward secrecy | Yes (per-session KEM) | ✅ |
| MAVLink integrity | Sequence gaps tracked | ✅ |
| Power monitoring | INA219 @ 1000Hz | ✅ |
| Deterministic testing | 10s fixed intervals | ✅ |

---

## Verdict

**No critical bugs remaining.** System is production-ready for data collection.
