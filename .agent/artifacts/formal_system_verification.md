# FORMAL SYSTEM VERIFICATION REPORT

**Date:** 2026-01-19
**Target:** `sscheduler/sdrone_bench.py` + `sscheduler/sgcs_bench.py` + `sscheduler/benchmark_policy.py`
**Mode:** Adversarial Property-Based Verification

---

## PROPERTY 1 — DETERMINISM

**Status: NOT VERIFIED**

### Evidence:

#### 1.1 Suite Duration Is Not Fixed

| File | Line | Code |
|:---|:---:|:---|
| `sdrone_bench.py` | 663-664 | `parser.add_argument("--interval", type=float, default=110.0, ...)` |
| `sdrone_bench.py` | 289-292 | `self.policy = BenchmarkPolicy(cycle_interval_s=args.interval, ...)` |
| `benchmark_policy.py` | 132-137 | `self.cycle_interval_s = cycle_interval_s or self.benchmark_cfg.get("cycle_interval_s", 10.0)` |

**Violation:** The CLI flag `--interval` can change suite duration at runtime. Duration is **NOT fixed internally**.

#### 1.2 Randomness in Execution Order

| File | Line | Code |
|:---|:---:|:---|
| `benchmark_policy.py` | 168 | `self.run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")` |

**Finding:** The run ID uses wall-clock time, not monotonic. However, suite order is derived from sorted dict keys (L185-193), which is deterministic.

**Verdict:** No randomness affects **suite order**. Suite order is sorted by `(nist_level, kem_name, sig_name)`.

#### 1.3 Timing Uses Monotonic Clocks

| File | Line | Code |
|:---|:---:|:---|
| `sdrone_bench.py` | 367 | `start_time = self.clock_sync.synced_time() if self.clock_sync.is_synced() else time.monotonic()` |
| `sdrone_bench.py` | 391 | `now = self.clock_sync.synced_time() if self.clock_sync.is_synced() else time.monotonic()` |
| `benchmark_policy.py` | 213-214 | `self.start_time_mono = start_time_mono if start_time_mono is not None else time.monotonic()` |
| `benchmark_policy.py` | 314-315 | `elapsed_on_suite = now_mono - self.last_switch_mono` |

**Finding:** Time comparisons use monotonic clock or synced time. ✅

**Overall Verdict for Property 1:** The suite duration CAN be changed via CLI. **NOT VERIFIED.**

---

## PROPERTY 2 — POLICY AUTHORITY

**Status: VERIFIED**

### Evidence:

#### 2.1 Scheduling Authority Location

| File | Line | Code |
|:---|:---:|:---|
| `sdrone_bench.py` | 379-424 | `_run_loop()` — Drone calls `policy.evaluate(now)` and decides next action. |
| `sdrone_bench.py` | 392 | `output = self.policy.evaluate(now)` |
| `benchmark_policy.py` | 293-365 | `evaluate()` — Self-contained. No external input influences decision. |

**Finding:** The `BenchmarkPolicy` object is instantiated and evaluated ONLY on the Drone. The GCS never imports or calls `BenchmarkPolicy`.

#### 2.2 GCS Commands Analyzed

| Command | GCS Behavior | Can Influence Timing? |
|:---|:---|:---:|
| `ping` | Returns pong | ❌ NO |
| `get_info` | Returns system info | ❌ NO |
| `prepare_rekey` | Stops proxy | ❌ NO |
| `start_proxy` | Starts proxy for suite | ❌ NO (Drone specifies suite) |
| `stop_suite` | Stops proxy, returns metrics | ❌ NO |
| `chronos_sync` | Returns clock offset | ❌ NO (Informational) |

**Finding:** GCS command handlers (`sgcs_bench.py` L581-684) are **reactive only**. They execute Drone commands but have NO mechanism to:
- Request a suite change
- Modify timing intervals
- Inject suite preferences

#### 2.3 No Hidden Override Paths

**Finding:** Grep for "suite_list" and "cycle_interval" modifications:
- `suite_list` is only modified in `__init__` (L143) and `start_benchmark` (L215). No external setter.
- `cycle_interval_s` is set once in `__init__`. No mutation after construction.

**Verdict for Property 2:** Drone is authoritative. GCS is purely reactive. **VERIFIED.**

---

## PROPERTY 3 — EXECUTION INVARIANTS

**Status: VERIFIED**

### Evidence:

#### 3.1 Exactly One Activation Per Suite

| File | Line | Code |
|:---|:---:|:---|
| `sdrone_bench.py` | 381 | `current_suite = self.policy.get_current_suite()` |
| `sdrone_bench.py` | 385 | `if not self._activate_suite(current_suite):` |
| `sdrone_bench.py` | 420 | `current_suite = output.target_suite` |
| `benchmark_policy.py` | 324 | `self.current_index += 1` |

**Finding:** The loop structure ensures each suite index is visited exactly once. `current_index` increments monotonically (L324). No decrement or reset.

#### 3.2 Traffic Start/Stop

**Finding:** In the refactored code, there is NO explicit `TrafficGenerator`. Traffic is real MAVLink flow.
- "Start": MAVProxy is started once (L361).
- "Stop": MAVProxy is stopped in `_cleanup()` (L594-595).

Traffic is NOT started/stopped per suite. It is a continuous stream.

#### 3.3 Metrics Collection Clear Start/Stop

| File | Line | Code |
|:---|:---:|:---|
| `sdrone_bench.py` | 436-437 | `self.metrics_aggregator.start_suite(suite_name, ...)` |
| `sdrone_bench.py` | 523-524 | `self.metrics_aggregator.record_handshake_end(...); self.metrics_aggregator.finalize_suite()` |
| `benchmark_policy.py` | 226-237 | `_start_suite_metrics(suite_id)` |
| `benchmark_policy.py` | 276-291 | `finalize_suite_metrics(success, error_message)` |

**Finding:** Clear start (`start_suite`) and stop (`finalize_suite`) boundaries exist for metrics.

#### 3.4 Final Record Always Emitted

| File | Line | Code |
|:---|:---:|:---|
| `sdrone_bench.py` | 484 | `self._log_result(suite_name, metrics, success=True)` |
| `sdrone_bench.py` | 491 | `self._log_result(suite_name, {}, success=False, error="handshake_timeout")` |

**Finding:** Both success and failure paths call `_log_result()`, ensuring a JSONL entry is written for every activation attempt.

**Verdict for Property 3:** One activation, one record. **VERIFIED.**

---

## PROPERTY 4 — FAILURE HANDLING

**Status: VERIFIED**

### Evidence:

#### 4.1 Handshake Failure Detection

| File | Line | Code |
|:---|:---:|:---|
| `sdrone_bench.py` | 467-493 | `if status.get("status") == "handshake_ok": ... else: ... handshake_timeout` |

**Finding:** Explicit timeout check (45s). Failure is logged to results file (L491).

#### 4.2 Proxy Start Failure Detection

| File | Line | Code |
|:---|:---:|:---|
| `sdrone_bench.py` | 459-462 | `if not self.proxy.start(suite_name): log("Drone proxy failed to start", "ERROR"); self._finalize_metrics(success=False, error="proxy_start_failed"); return False` |

**Finding:** Failure is recorded in metrics.

#### 4.3 GCS Rejection Detection

| File | Line | Code |
|:---|:---:|:---|
| `sdrone_bench.py` | 451-454 | `if resp.get("status") != "ok": log(f"GCS rejected: {resp}", "ERROR"); self._finalize_metrics(success=False, error="gcs_rejected"); return False` |

**Finding:** GCS errors are detected and recorded.

#### 4.4 Partial Execution Handling

| File | Line | Code |
|:---|:---:|:---|
| `sdrone_bench.py` | 385-387 | `if not self._activate_suite(current_suite): log(...); self.policy.finalize_suite_metrics(success=False, error_message="activation_failed")` |

**Finding:** If activation fails, the loop continues to the next suite after logging the failure.

**Verdict for Property 4:** All failure types are detected, logged, and reflected in results. **VERIFIED.**

---

## PROPERTY 5 — METRIC INTEGRITY

**Status: NOT VERIFIED**

### Evidence:

#### 5.1 Pruned GCS Metrics

| File | Line | Code |
|:---|:---:|:---|
| `sgcs_bench.py` | 297-315 | `# NOTE: GCS system resource metrics removed per POLICY REALIGNMENT` |
| `sgcs_bench.py` | 657-661 | Returned payload contains `mavlink_validation` and `proxy_status` only. No `cpu_avg_percent`, `memory_rss_mb`. |

**Finding:** GCS system metrics are **CORRECTLY PRUNED**. ✅

#### 5.2 Drone Metrics Completeness

**Finding:** MetricsAggregator path is conditional:
| File | Line | Code |
|:---|:---:|:---|
| `sdrone_bench.py` | 45-50 | `try: from core.metrics_aggregator import MetricsAggregator; HAS_METRICS_AGGREGATOR = True; except ImportError: HAS_METRICS_AGGREGATOR = False` |
| `sdrone_bench.py` | 497-498 | `if not self.metrics_aggregator: return` |

**Violation:** If `MetricsAggregator` import fails, comprehensive metrics are silently skipped. Only basic JSONL log is written (L559-587). This JSONL does NOT include:
- Power/Energy
- Data plane counters
- System resources

The "completeness" of drone metrics **depends on import success**, which is not guaranteed.

#### 5.3 Suite-Scoped Metrics

| File | Line | Code |
|:---|:---:|:---|
| `sdrone_bench.py` | 441-447 | Status file deletion before activation to prevent stale data. |
| `sgcs_bench.py` | 652-654 | MAVLink monitor reset and restart on `stop_suite`. |

**Finding:** Suite scoping is enforced by status file deletion and monitor reset.

#### 5.4 Cross-Suite Contamination

| File | Line | Code |
|:---|:---:|:---|
| `benchmark_policy.py` | 290-291 | `self.collected_metrics.append(self.current_metrics); self.current_metrics = None` |

**Finding:** `current_metrics` is reset to `None` after finalization. No contamination.

**Overall Verdict for Property 5:** GCS metrics are pruned ✅, but Drone metrics completeness is NOT guaranteed (silent fallback). **NOT VERIFIED.**

---

## PROPERTY 6 — TERMINATION SAFETY

**Status: VERIFIED**

### Evidence:

#### 6.1 Clean Termination Path

| File | Line | Code |
|:---|:---:|:---|
| `sdrone_bench.py` | 373-377 | `except KeyboardInterrupt: log(...); finally: self._cleanup(); self._save_final_summary()` |
| `sdrone_bench.py` | 589-595 | `_cleanup()` stops proxy and MAVProxy. |

**Finding:** `finally` block ensures cleanup runs regardless of exit path.

#### 6.2 No Infinite Loops

| File | Line | Code |
|:---|:---:|:---|
| `sdrone_bench.py` | 383 | `while not self.policy.benchmark_complete:` |
| `benchmark_policy.py` | 327-329 | `if self.current_index >= len(self.suite_list): self.benchmark_complete = True` |

**Finding:** `benchmark_complete` flag is set when `current_index` exceeds list length. Loop terminates.

| File | Line | Code |
|:---|:---:|:---|
| `sdrone_bench.py` | 390-424 | Inner `while True:` loop exits via `return` (L399) or `break` (L421). |

**Finding:** Inner loop has explicit exit conditions.

#### 6.3 Resource Release

| File | Line | Code |
|:---|:---:|:---|
| `sdrone_bench.py` | 641-651 | `_atexit_cleanup()` registered via `atexit.register()`. |
| `sgcs_bench.py` | 742-748 | `_atexit_cleanup()` registered for GCS. |

**Finding:** Both scripts register atexit handlers.

**Verdict for Property 6:** Scripts terminate cleanly with resource cleanup. **VERIFIED.**

---

# FINAL VERIFICATION SUMMARY

| Property | Status |
|:---|:---|
| **1. DETERMINISM** | **NOT VERIFIED** — CLI can change suite duration. |
| **2. POLICY AUTHORITY** | **VERIFIED** — Drone is authoritative. |
| **3. EXECUTION INVARIANTS** | **VERIFIED** — One activation, one record. |
| **4. FAILURE HANDLING** | **VERIFIED** — All failures detected and logged. |
| **5. METRIC INTEGRITY** | **NOT VERIFIED** — Drone completeness depends on import. |
| **6. TERMINATION SAFETY** | **VERIFIED** — Clean exit, no infinite loops. |

---

## **SYSTEM NOT VERIFIED**

Properties 1 and 5 are **NOT VERIFIED**.

### Blocking Issues:

1. **PROPERTY 1 VIOLATION:** The `--interval` CLI flag allows runtime modification of suite duration. If the requirement is that duration MUST be fixed at 10s, this violates determinism.

2. **PROPERTY 5 VIOLATION:** If `core.metrics_aggregator` import fails, comprehensive drone metrics are silently skipped. The basic JSONL log does not contain power, energy, or data plane counters.
