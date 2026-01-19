# Root Cause Only Report

**Phase:** X - Forensic Reality Check
**Date:** 2026-01-19
**Evidence Type:** Structural Failures Only (No Recommendations)

## 1. Identified Root Causes

### RC-001: Crypto Primitive Instrumentation Gap

| Field | Value |
|:---|:---|
| **File** | `sscheduler/sdrone_bench.py` |
| **Location** | L889-906 |
| **Exact Reason** | The C-based `core.run_proxy` subprocess does not write `handshake_metrics` to `drone_status.json`. The Python scheduler reads an empty or missing object. |
| **Exact Consequence** | All `crypto_primitives.*` fields are `-1`. No KEM/SIG timing data is available for policy synthesis. |

---

### RC-002: GCS Handshake End Time Not Reported

| Field | Value |
|:---|:---|
| **File** | `sscheduler/sgcs_bench.py` |
| **Location** | `_handle_command("stop_suite")` response |
| **Exact Reason** | The `stop_suite` handler does not include `handshake_end_time_gcs` in its response dictionary. |
| **Exact Consequence** | `handshake.handshake_end_time_gcs` is always `0.0` in JSONL. Cross-side handshake RTT cannot be computed. |

---

### RC-003: Silent Exception Swallowing in Power Monitor

| Field | Value |
|:---|:---|
| **File** | `sscheduler/sdrone_bench.py` |
| **Location** | L169 `DronePowerMonitor.__init__` |
| **Exact Reason** | `except Exception: pass` hides initialization failures. |
| **Exact Consequence** | If INA219 is unavailable (e.g., disconnected), all power metrics are silently `0.0` with no log entry. |

---

### RC-004: Thread Count Hardcoded to Zero

| Field | Value |
|:---|:---|
| **File** | `sscheduler/sdrone_bench.py` |
| **Location** | L296 `SystemMetricsCollector.stop_sampling` |
| **Exact Reason** | `psutil.Process().num_threads()` crashes on some Linux kernels (IndexError). Patched with `except: thread_count = 0`. |
| **Exact Consequence** | `system_drone.thread_count` is always `0`. Real thread count is unavailable. |

---

### RC-005: JSONL Entry Skipped on Suite Failure

| Field | Value |
|:---|:---|
| **File** | `sscheduler/sdrone_bench.py` |
| **Location** | L698-701 `_benchmark_suite` exception handler |
| **Exact Reason** | If an exception occurs anywhere in `_benchmark_suite`, the `result.to_json()` write (L695) is skipped. |
| **Exact Consequence** | Failed suites produce no JSONL entry. The failure is logged but not persisted for analysis. |

---

## 2. Non-Issues (Confirmed Correct Behavior)

| Observation | Reason Not an Issue |
|:---|:---|
| `system_gcs.*` = 0 | Policy: GCS resources are non-constrained. Intentionally disabled. |
| `rekey.*` = 0 | Expected: Suite duration (10s) < Rekey interval. No rekey triggered. |
| `run_end_time_wall` = "" | Expected: Not populated until run completes. |

---

## 3. Report Constraints

> [!CAUTION]
> This report contains ONLY root causes.
> NO recommendations, fixes, or future tense statements are included.
