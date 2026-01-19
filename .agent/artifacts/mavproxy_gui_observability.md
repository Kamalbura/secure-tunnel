# MAVProxy GUI Observability

> Phase 0.9 • Generated: 2026-01-19
> Status: ✅ ALREADY ENABLED

---

## Configuration

| Setting | Value | Location |
|---------|-------|----------|
| `MAVPROXY_ENABLE_GUI` | `True` | `sgcs_bench.py:75` |
| GUI flags | `--map --console` | `sgcs_bench.py:145` |
| Input port | UDP 14550 | `MAVLINK_INPUT_PORT` |
| Output port | UDP 14552 | `MAVLINK_SNIFF_PORT` |

---

## GcsMavProxyManager Implementation

```python
# sgcs_bench.py:144-148
if self.enable_gui:
    cmd.extend(["--map", "--console"])
    log("[MAVPROXY] Starting with GUI (map + console)")
else:
    log("[MAVPROXY] Starting headless")
```

---

## Observable Components

| Component | Visible | How |
|-----------|---------|-----|
| Live map | ✅ | `--map` flag |
| Console | ✅ | `--console` flag |
| Heartbeat | ✅ | MAVLink HEARTBEAT messages |
| GPS status | ✅ | Map display |
| Arm/Disarm | ✅ | Console output |

---

## Command Line Override

```powershell
# Headless mode (if needed)
python -m sscheduler.sgcs_bench --no-gui
```

This sets `MAVPROXY_ENABLE_GUI = False` via argparse (line 772-774).

---

## Verdict

**✅ No changes needed** — MAVProxy GUI is already enabled by default.
