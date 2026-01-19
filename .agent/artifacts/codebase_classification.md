# Phase 0: Codebase Classification

> Generated: 2026-01-18T23:24
> Status: IN PROGRESS

---

## Repository Structure

```
secure-tunnel/
├── core/                 ← PRIORITY #1 (18 Python files)
├── sscheduler/           ← PRIORITY #2 (16 Python files)
├── scheduler/            ← Secondary (3 Python files)
├── bench/                ← Secondary (17+ files)
├── devtools/             ← Low priority
├── scripts/              ← Low priority
├── tools/                ← Low priority
└── [root files]          ← Utility scripts
```

---

## Priority 1: core/ (MANDATORY DEEP READ)

| File | Size | Assigned Agent | Status |
|------|------|----------------|--------|
| `__init__.py` | 121B | Orchestrator | ⏳ |
| `aead.py` | 17KB | Crypto NIST | ⏳ |
| `async_proxy.py` | 67KB | Orchestrator | ⏳ |
| `clock_sync.py` | 4KB | Energy | ⏳ |
| `config.py` | 27KB | Orchestrator | ⏳ |
| `control_tcp.py` | 12KB | Rekey | ⏳ |
| `exceptions.py` | 615B | Orchestrator | ⏳ |
| `handshake.py` | 26KB | Crypto NIST | ⏳ |
| `logging_utils.py` | 3KB | Performance | ⏳ |
| `mavlink_collector.py` | 25KB | Performance | ⏳ |
| `metrics_aggregator.py` | 30KB | Performance | ⏳ |
| `metrics_collectors.py` | 26KB | Performance | ⏳ |
| `metrics_schema.py` | 25KB | Performance | ⏳ |
| `policy_engine.py` | 8KB | Rekey | ⏳ |
| `power_monitor.py` | 36KB | Energy | ⏳ |
| `power_monitor_full.py` | 69KB | Energy | ⏳ |
| `process.py` | 10KB | Orchestrator | ⏳ |
| `run_proxy.py` | 35KB | Orchestrator | ⏳ |
| `suites.py` | 28KB | Crypto NIST | ⏳ |

---

## Priority 2: sscheduler/ (MANDATORY DEEP READ)

| File | Size | Assigned Agent | Status |
|------|------|----------------|--------|
| `__init__.py` | 93B | Orchestrator | ⏳ |
| `benchmark_policy.py` | 24KB | Rekey | ⏳ |
| `control_security.py` | 1KB | Rekey | ⏳ |
| `gcs_metrics.py` | 15KB | Performance | ⏳ |
| `local_mon.py` | 6KB | Energy | ⏳ |
| `policy.py` | 14KB | Rekey | ⏳ |
| `sdrone.py` | 18KB | Rekey | ⏳ |
| `sdrone_bench.py` | 43KB | Rekey | ⏳ |
| `sdrone_mav.py` | 26KB | **ALL** (Entry) | ⏳ |
| `sgcs.py` | 20KB | Rekey | ⏳ |
| `sgcs_bench.py` | 29KB | Rekey | ⏳ |
| `sgcs_mav.py` | 27KB | **ALL** (Entry) | ⏳ |
| `telemetry_window.py` | 7KB | Performance | ⏳ |

---

## Secondary: scheduler/

| File | Size | Notes |
|------|------|-------|
| `__init__.py` | 36B | Module marker |
| `sdrone.py` | 22KB | Basic scheduler (not sscheduler) |
| `sgcs.py` | 21KB | Basic scheduler (not sscheduler) |

---

## Agent Assignment Summary

| Agent | Assigned Files |
|-------|----------------|
| **Performance Analysis** | `logging_utils.py`, `mavlink_collector.py`, `metrics_*.py`, `gcs_metrics.py`, `telemetry_window.py` |
| **Crypto & NIST** | `aead.py`, `handshake.py`, `suites.py` |
| **Rekey & Stability** | `policy_engine.py`, `policy.py`, `benchmark_policy.py`, `control_*.py`, `sdrone*.py`, `sgcs*.py` |
| **Energy & Drone** | `power_monitor*.py`, `clock_sync.py`, `local_mon.py` |

---

## Entry Points (ALL AGENTS MUST READ)

1. `sscheduler/sgcs_mav.py` — GCS entry point
2. `sscheduler/sdrone_mav.py` — Drone entry point
