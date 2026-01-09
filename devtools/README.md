# Development Tools System

## Overview

This document describes the **DEVELOPMENT-ONLY** tooling system for the PQC Drone-GCS secure proxy. This system is designed for **LAB / LAPTOP TESTING ONLY** and does not affect production behavior when disabled.

## Architecture

```
devtools/
├── __init__.py          # Enable/disable logic, safe imports
├── config.py            # Configuration loader
├── data_bus.py          # Thread-safe observability bus
├── battery_sim.py       # Battery provider abstraction + simulation
├── battery_bridge.py    # Non-invasive injection bridge
├── dashboard.py         # Tkinter GUI dashboard
├── integration.py       # Scheduler integration layer
└── launcher.py          # Entry point for dev mode
```

## Components

### 1. Battery Simulator

**Location:** `devtools/battery_sim.py`

Provides a `BatteryProvider` interface with two implementations:
- `RealBatteryProvider`: Pass-through to MAVLink (production path)
- `SimulatedBatteryProvider`: Configurable simulation for lab testing

**Simulation Modes:**
| Mode | Description | Rate |
|------|-------------|------|
| `stable` | Constant voltage | 0 mV/s |
| `slow_drain` | Slow linear drain | ~5 mV/s |
| `fast_drain` | Fast linear drain | ~20 mV/s |
| `throttle_drain` | Accelerated drain under load | Variable |
| `step_drop` | Sudden voltage drop | One-shot |
| `recovery` | Voltage rebound | ~10 mV/s |

Each mode exposes:
- `battery_mv`: Current voltage in millivolts
- `rate_mv_per_sec`: Rate of change
- `stress_level`: Qualitative level (low/medium/high/critical)

### 2. Data Bus

**Location:** `devtools/data_bus.py`

Thread-safe **SINGLE SOURCE OF TRUTH** for all dev tool consumers.

**Writers:**
- Scheduler (policy state)
- Telemetry receiver (link metrics)
- Battery provider (voltage, rate)
- Proxy (packet stats)

**Readers:**
- GUI dashboard (read-only)
- Integration layer

**Key Features:**
- RLock-protected state
- History retention for timelines
- Event markers for visualization
- Subscription callbacks

### 3. GUI Dashboard

**Location:** `devtools/dashboard.py`

Single-page Tkinter dashboard with 5 panels:

1. **SYSTEM STATUS**: Suite, action, cooldown, armed state
2. **BATTERY**: Voltage graph, rate, mode selector, sliders
3. **TELEMETRY**: rx_pps, gap_p95, blackout_count, age
4. **DATA PLANE**: Encrypted/plaintext PPS, replay drops, handshake
5. **TIMELINE**: Voltage vs time, suite switches, policy markers

**Properties:**
- Non-blocking (separate thread)
- Thread-safe (uses data bus locks)
- Configurable refresh rate (5-10 Hz)
- Completely disabled via config

### 4. Battery Bridge

**Location:** `devtools/battery_bridge.py`

Non-invasive injection point for battery providers.

```python
# Usage in scheduler code:
from devtools.battery_bridge import LocalMonitorBridge

# Automatically uses simulation when enabled:
monitor = LocalMonitorBridge.create_with_devtools()
metrics = monitor.get_metrics()  # Battery comes from provider
```

When disabled, this is 100% pass-through to `LocalMonitor`.

## Configuration

All features controlled via `settings.json`:

```json
{
    "dev_tools": {
        "enabled": false,
        "battery_simulation": {
            "enabled": false,
            "default_mode": "stable",
            "start_mv": 16000,
            "min_mv": 13000,
            "max_mv": 17000,
            "slow_drain_mv_per_sec": 5.0,
            "fast_drain_mv_per_sec": 20.0,
            "throttle_drain_factor": 2.0,
            "step_drop_mv": 2000,
            "recovery_mv_per_sec": 10.0
        },
        "gui": {
            "enabled": false,
            "refresh_hz": 5.0,
            "window_width": 1200,
            "window_height": 800,
            "timeline_points": 300,
            "graph_update_hz": 2.0
        },
        "bus_history_size": 1000,
        "bus_log_enabled": false,
        "bus_log_path": null
    }
}
```

**Rules:**
- When `dev_tools.enabled = false` → **NO DEV CODE ACTIVE**
- No branching scattered across files
- Centralized enablement logic only

## Usage

### Enable Dev Tools for Lab Testing

1. Edit `settings.json`:
```json
{
    "dev_tools": {
        "enabled": true,
        "battery_simulation": { "enabled": true },
        "gui": { "enabled": true }
    }
}
```

2. Run launcher:
```bash
python -m devtools.launcher
```

### Standalone GUI Mode

Run GUI without scheduler (for testing):
```bash
python -m devtools.launcher --standalone
```

### Data Bus Only

Enable observability without GUI:
```bash
python -m devtools.launcher --data-bus-only
```

## Safety Guarantees

### Production Path Unchanged

When `dev_tools.enabled = false`:
1. `devtools.is_enabled()` returns `False`
2. `get_integration()` returns `NullIntegration` (all methods are no-ops)
3. `LocalMonitorBridge.create_with_devtools()` returns pure pass-through
4. No GUI threads started
5. No battery simulation active
6. Zero performance impact

### Isolation Guarantees

1. **GUI cannot affect policy decisions** - GUI is read-only from data bus
2. **Simulation cannot leak** - Battery provider only active when explicitly enabled
3. **No scheduler/policy modifications** - All dev code in separate `devtools/` module
4. **No hidden dev flags** - All configuration explicit in `settings.json`

### Verification

Run the verification script:
```bash
python -c "
import devtools
from devtools.integration import get_integration, NullIntegration

# When disabled:
assert devtools.is_enabled() == False
assert isinstance(get_integration(), NullIntegration)
print('Production behavior verified: dev tools inactive')
"
```

## Integration Points

### Scheduler Integration

```python
from devtools.integration import get_integration

# Creates NullIntegration if disabled
integration = get_integration()

# Safe to call unconditionally (no-op when disabled)
integration.update_policy(
    current_suite=suite_name,
    current_action=action,
    target_suite=target,
    confidence=0.95
)

integration.update_telemetry(
    rx_pps=10.0,
    gap_p95_ms=150.0,
    telemetry_age_ms=200.0
)
```

### Battery Provider Bridge

```python
from devtools.battery_bridge import get_local_monitor

# Returns LocalMonitorBridge with auto-configured provider
monitor = get_local_monitor()
monitor.start()

# get_metrics() returns LocalMetrics with battery from:
#   - MAVLink (when dev_tools disabled)
#   - SimulatedBatteryProvider (when battery_simulation enabled)
metrics = monitor.get_metrics()
```

## File Structure

```
secure-tunnel/
├── devtools/                    # DEV-ONLY MODULE
│   ├── __init__.py              # Enable/disable gate
│   ├── config.py                # Configuration
│   ├── data_bus.py              # Observability bus
│   ├── battery_sim.py           # Battery simulation
│   ├── battery_bridge.py        # Injection bridge
│   ├── dashboard.py             # Tkinter GUI
│   ├── integration.py           # Scheduler hooks
│   └── launcher.py              # Entry point
│
├── settings.json                # Configuration (has dev_tools section)
│
├── sscheduler/                  # PRODUCTION (UNCHANGED)
│   ├── sdrone.py                # Drone scheduler
│   ├── sgcs.py                  # GCS scheduler
│   ├── policy.py                # Policy engine
│   └── local_mon.py             # Local monitor
│
└── core/                        # PRODUCTION (UNCHANGED)
    ├── async_proxy.py           # Proxy engine
    ├── handshake.py             # PQC handshake
    └── ...
```

## Testing

### Test All Imports
```bash
python -c "from devtools import is_enabled; print(f'enabled={is_enabled()}')"
```

### Test Battery Simulation
```bash
python -c "
from devtools.battery_sim import SimulatedBatteryProvider, SimulationMode
from devtools.config import BatterySimConfig

config = BatterySimConfig(enabled=True)
provider = SimulatedBatteryProvider(config)
provider.start()
provider.set_mode(SimulationMode.FAST_DRAIN)
import time; time.sleep(1)
print(f'Voltage after 1s drain: {provider.get_battery_mv()} mV')
provider.stop()
"
```

### Test GUI (Manual)
```bash
# Enable in settings.json first, then:
python -m devtools.launcher --standalone
```

## Troubleshooting

### GUI Not Starting
1. Check `dev_tools.enabled` is `true`
2. Check `dev_tools.gui.enabled` is `true`
3. Ensure Tkinter is installed: `python -c "import tkinter"`

### Battery Simulation Not Active
1. Check `dev_tools.enabled` is `true`
2. Check `dev_tools.battery_simulation.enabled` is `true`
3. Verify with: `python -c "import devtools; print(devtools.get_battery_provider().is_simulated())"`

### Scheduler Not Using Dev Tools
Ensure scheduler uses `LocalMonitorBridge.create_with_devtools()` or `get_local_monitor()`.

## Removal

To completely remove dev tools from the codebase:
1. Delete `devtools/` directory
2. Remove `dev_tools` section from `settings.json`
3. No other changes required (production code has no dependencies)
