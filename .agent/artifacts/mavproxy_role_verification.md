# MAVProxy Role Verification

> Phase 0.95 • Generated: 2026-01-19
> Status: ✅ CORRECT

---

## Expected Roles

| System | MAVProxy Mode | GUI |
|--------|---------------|-----|
| Drone | Headless | ❌ |
| GCS | Interactive | ✅ `--map --console` |

---

## Drone Side: `sdrone_bench.py`

**No MAVProxy references found** — confirmed headless.

The drone uses pymavlink directly for telemetry sniffing:
```python
# MavLinkMetricsCollector uses pymavlink, NOT MAVProxy
self._conn = mavutil.mavlink_connection(...)
```

---

## GCS Side: `sgcs_bench.py`

**GUI enabled by default:**

```python
# Line 75
MAVPROXY_ENABLE_GUI = True  # Enable --map and --console

# Lines 144-146
if self.enable_gui:
    cmd.extend(["--map", "--console"])
    log("[MAVPROXY] Starting with GUI (map + console)")
```

---

## Verification

| Role | Expected | Actual |
|------|----------|--------|
| Drone headless | ✅ | ✅ No MAVProxy |
| GCS GUI | ✅ | ✅ `--map --console` |

---

## Verdict

**✅ CORRECT** — MAVProxy roles match specification.
