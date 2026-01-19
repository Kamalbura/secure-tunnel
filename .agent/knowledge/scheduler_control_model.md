# Scheduler vs SScheduler Control Model

> [!NOTE]
> This document describes the control flow differences between scheduler and sscheduler.

## Overview

| Property | `scheduler` | `sscheduler` |
|----------|-------------|--------------|
| Location | `scheduler/` | `sscheduler/` |
| Purpose | Basic scheduling | Synchronized scheduling |
| Rekey Control | Timer-based | Event-based |
| Coordination | Loose | Tight |

## Scheduler (Basic)

### Control Flow

```
Timer → Rekey Trigger → Suite Switch → Resume
```

### Characteristics

- Fixed interval rekey (30s default)
- No GCS synchronization
- Possible data loss during switch
- Simpler implementation

### Entry Point

```python
python -m scheduler.sgcs  # GCS side
python -m scheduler.sdrone  # Drone side
```

## SScheduler (Synchronized)

### Control Flow

```
Event → GCS Signal → Drone Ack → Sync Pause → Rekey → Resume
```

### Characteristics

- Event-driven rekey
- GCS-Drone synchronization
- Minimal data loss (blackout window)
- Complex state machine

### Entry Point

```python
python -m sscheduler.sgcs_mav  # GCS side
python -m sscheduler.sdrone_mav  # Drone side
```

## Benchmark Implications

| Metric | Scheduler | SScheduler |
|--------|-----------|------------|
| Rekey Blackout | Higher | Lower |
| Jitter During Rekey | Higher | Lower |
| Implementation Complexity | Lower | Higher |
| Benchmark Reliability | Moderate | High |

## Usage Decision

- **Analysis Mode**: Use `sscheduler` for accurate metrics
- **Development Mode**: Use `scheduler` for simplicity
- **Benchmark Mode**: Always `sscheduler`
