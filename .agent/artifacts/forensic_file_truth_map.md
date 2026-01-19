# Forensic File Truth Map

**Phase:** X - Forensic Reality Check
**Date:** 2026-01-19
**Evidence Type:** Static Code Analysis

## 1. Mandatory Scheduler Files

| File | Exists? | Declared Purpose | Main Entrypoint | Status |
|:---|:---:|:---|:---:|:---|
| `sscheduler/sdrone_mav.py` | ✅ | Drone Scheduler (CONTROLLER) - Synthetic traffic mode | `main()` L689+ | **ACTIVE** (Legacy Mode) |
| `sscheduler/sgcs_mav.py` | ✅ | GCS Scheduler (FOLLOWER) - Synthetic traffic mode | `main()` L714+ | **ACTIVE** (Legacy Mode) |
| `sscheduler/sdrone_bench.py` | ✅ | Drone Benchmark Controller (Real MAV Mode) | `main()` L1037+ | **ACTIVE** (Current Mode) |
| `sscheduler/sgcs_bench.py` | ✅ | GCS Benchmark Server (Real MAV Mode) | `main()` L872+ | **ACTIVE** (Current Mode) |

### Invocation Evidence

| File | Last Invoked? | Evidence |
|:---|:---:|:---|
| `sdrone_mav.py` | **UNKNOWN** | No recent run logs found in `logs/sscheduler/drone/`. |
| `sgcs_mav.py` | **UNKNOWN** | No recent run logs found in `logs/sscheduler/gcs/`. |
| `sdrone_bench.py` | ✅ 2026-01-19 | Run directory `bench_20260119_041244_2dcced9f` exists. JSONL output verified. |
| `sgcs_bench.py` | ✅ 2026-01-19 | Run directory `gcs_bench_20260119_041231_c9dc846f` exists. |

## 2. Core Library Files

| File | Size | Verified Purpose |
|:---|:---:|:---|
| `core/config.py` | 27KB | Central configuration (Ports, Hosts, Params). **ACTIVE.** |
| `core/suites.py` | 28KB | Suite definitions (KEM, SIG, AEAD). **ACTIVE.** |
| `core/handshake.py` | 26KB | TCP Handshake + KEM/SIG Exchange. **ACTIVE.** |
| `core/aead.py` | 18KB | AEAD Encryption (AES-GCM, Ascon, ChaCha). **ACTIVE.** |
| `core/run_proxy.py` | 35KB | Proxy Subprocess Entry Point. **ACTIVE.** |
| `core/process.py` | 10KB | Managed Subprocess Wrapper. **ACTIVE.** |
| `core/metrics_schema.py` | 26KB | Dataclass Definitions (A-R Categories). **ACTIVE.** |
| `core/power_monitor.py` | 37KB | INA219/RPi5 Power Sampling. **ACTIVE (Drone).** |
| `core/power_monitor_full.py` | 70KB | Extended Power Monitor (UNUSED?). **UNKNOWN.** |
| `core/mavlink_collector.py` | 25KB | pymavlink Introspection. **ACTIVE.** |
| `core/metrics_collectors.py` | 26KB | System/Network Collectors. **ACTIVE.** |
| `core/metrics_aggregator.py` | 30KB | Metric Consolidation. **ACTIVE.** |
| `core/logging_utils.py` | 3KB | Logging Helpers. **ACTIVE.** |
| `core/clock_sync.py` | 4KB | NTP Offset Sync. **ACTIVE.** |
| `core/policy_engine.py` | 9KB | Policy Evaluation Logic. **ACTIVE.** |
| `core/control_tcp.py` | 13KB | TCP Control Channel. **ACTIVE.** |
| `core/async_proxy.py` | 68KB | Async UDP/TCP Proxy. **ACTIVE.** |
| `core/exceptions.py` | 1KB | Custom Exceptions. **ACTIVE.** |
| `core/_ascon_native.*` | N/A | C Extension for ASCON. **ACTIVE.** |

## 3. File Status Classification

| Category | Files |
|:---|:---|
| **ACTIVE (Bench Mode)** | `sdrone_bench.py`, `sgcs_bench.py`, `core/*` (22 files) |
| **ACTIVE (Legacy Mode)** | `sdrone_mav.py`, `sgcs_mav.py` |
| **DEAD (No Evidence)** | None identified. |
| **UNKNOWN (Unused?)** | `core/power_monitor_full.py` (No imports found in active paths). |

## 4. Contradiction Check

| Prior Belief (Orchestrator Memory) | Current Evidence | Status |
|:---|:---|:---|
| "Phase 1: Real MAV Mode VERIFIED" | Run `2dcced9f` JSONL exists with 347,885 bytes collected. | ✅ **CONSISTENT** |
| "Awaiting hardware run" | GCS server is still LISTENING on port 48080. | ✅ **CONSISTENT** |
| "Full run authorized" | No new run initiated since `2dcced9f`. | ✅ **CONSISTENT** |

**Verdict:** No contradictions detected. Prior beliefs are supported by current evidence.
