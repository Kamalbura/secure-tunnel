# Benchmark Gaps and Actions

> Phase 0.5 • Generated: 2026-01-18
> Status: REQUIRES DECISION

---

## Critical Gaps

### 1. Rekey Metrics Not Captured

| Field | Status | Impact |
|-------|--------|--------|
| `rekey_attempts` | ❌ | Cannot measure rekey overhead |
| `rekey_success` | ❌ | Cannot assess rekey reliability |
| `rekey_blackout_duration_ms` | ❌ | Cannot measure data blackout |

**Cause**: Current benchmarks run one suite per cycle without rekey.

**Action**: 
- Option A: Add multi-suite-per-run benchmark mode with rekey
- Option B: Accept gap — rekey metrics from sscheduler runtime only

---

### 2. Crypto Primitive Metrics Unreliable

| Field | Status | Issue |
|-------|--------|-------|
| `kem_keygen_time_ms` | ⚠️ | Read from status file, often 0 |
| `kem_encaps/decaps_ms` | ⚠️ | Proxy may not emit these |
| `sig_sign/verify_ms` | ⚠️ | Same issue |

**Cause**: `core.run_proxy` status file not consistently populated with timing.

**Action**:
- Verify `core/handshake.py` emits metrics to status file
- Or instrument `core.run_proxy` to write metrics atomically

---

### 3. Clock Synchronization Not Verified

| Metric | Status | Issue |
|--------|--------|-------|
| `one_way_latency_*` | ⚠️ | Requires synced clocks |
| `clock_offset_ms` | ⚠️ | Not populated in benchmarks |

**Cause**: Latency extracted from embedded timestamps assumes clock sync.

**Action**:
- Run NTP sync before benchmarks
- Or use RTT (round-trip) instead of one-way latency

---

### 4. Jitter During Rekey Not Measured

Currently jitter is computed from inter-arrival times during traffic phase.
Jitter **during rekey transition** is not captured.

**Action**: Out of scope for deterministic benchmarks (no rekey).

---

## Minor Gaps

| Gap | Status | Action |
|-----|--------|--------|
| GCS system metrics removed | By design | Policy decision — do not restore |
| FC telemetry sparse | ⚠️ | Depends on Pixhawk sending HEARTBEAT |
| AEAD encrypt/decrypt timing | ⚠️ | Not in status file |

---

## Pre-Data-Freeze Checklist

| Check | Required | Status |
|-------|----------|--------|
| Power monitor initializes on drone | ✅ | Verified in code |
| JSONL output path exists | ✅ | `mkdir(parents=True)` |
| Proxy status file written | ⚠️ | Verify at runtime |
| Clock sync between GCS/Drone | ⚠️ | Recommend NTP check |
| All 18 categories in schema | ✅ | Verified |
| Deterministic 10s enforced | ✅ | `time.sleep(cycle_time)` |

---

## Recommended Actions Before Phase A

1. **Verify proxy status file** contains crypto primitive timings
2. **Run NTP sync** on drone: `sudo ntpdate -s time.google.com`
3. **Test single-suite run** to confirm JSONL output
4. **Check INA219 connectivity** via `python -m core.power_monitor`
