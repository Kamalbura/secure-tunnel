# Execution Reality Trace

**Phase:** X - Forensic Reality Check
**Date:** 2026-01-19
**Evidence Type:** Code Path Analysis + Runtime State

## 1. Drone Execution Trace (`sdrone_bench.py`)

### Entrypoint
```
if __name__ == "__main__":
    main()  # L1077-1078
```

### Call Chain
```
main() L1037
  ├─ argparse.parse_args()
  ├─ run_id = auto-generated
  ├─ run_logs_dir.mkdir()
  ├─ DroneBenchmarkController.__init__() L606
  │     ├─ DroneProxyManager()
  │     ├─ DronePowerMonitor()       ← INA219 Thread (if available)
  │     ├─ SystemMetricsCollector()  ← psutil Thread
  │     └─ MavLinkMetricsCollector() ← pymavlink Thread
  ├─ signal.signal(SIGINT, SIGTERM)
  └─ controller.run() L631
        ├─ wait_for_gcs() L639      ← TCP Ping to GCS:48080
        ├─ start_persistent_mavproxy() L724
        │     └─ ManagedProcess("mavproxy-drone-bench")
        ├─ mavlink_monitor.start() L669
        │     └─ Thread: _listen_loop()
        └─ FOR each suite:
              ├─ power_monitor.start_sampling() L837
              │     └─ Thread: _sample_loop()
              ├─ system_monitor.start_sampling() L838
              │     └─ Thread: _sample_loop()
              ├─ _benchmark_suite() L776
              │     ├─ send_gcs_command("prepare_rekey")
              │     ├─ send_gcs_command("start_proxy")
              │     ├─ proxy.start() ← Subprocess: core.run_proxy drone
              │     ├─ time.sleep(cycle_time) ← NO SYNTHETIC TRAFFIC
              │     ├─ mavlink_monitor.stop() ← Collect pymavlink stats
              │     ├─ send_gcs_command("stop_suite")
              │     └─ [JSONL WRITE] L695
              └─ mavlink_monitor = MavLinkMetricsCollector() ← RESTART
```

### Threads Spawned (DRONE)

| Thread Name | Blocking Call | Owner |
|:---|:---|:---|
| `power_sample_thread` | `Event.wait()` | `DronePowerMonitor` |
| `cpu_sample_thread` | `time.sleep(0.5)` | `SystemMetricsCollector` |
| `mavlink_listen_thread` | `conn.recv_match(blocking=True)` | `MavLinkMetricsCollector` |

### Silent Failure Paths

| Location | Failure Mode | Consequence |
|:---|:---|:---|
| `L169` `DronePowerMonitor.__init__` | `except Exception` | Power metrics = 0. No log. |
| `L251-255` `SystemMetricsCollector.__init__` | `except ImportError` | Log "[SYSTEM] psutil not available". Continues. |
| `L371-373` `MavLinkMetricsCollector.start` | `except Exception` | Returns `False`. Continues. |
| `L698-701` `_benchmark_suite` | `except Exception` | Logs traceback. **Suite skipped. No JSONL entry.** |

---

## 2. GCS Execution Trace (`sgcs_bench.py`)

### Entrypoint
```
if __name__ == "__main__":
    main()  # L911-912
```

### Call Chain
```
main() L858
  ├─ argparse.parse_args()
  ├─ run_id = auto-generated
  ├─ run_logs_dir.mkdir()
  ├─ GcsBenchmarkServer.__init__() L680
  │     ├─ GcsProxyManager()
  │     ├─ GcsMavProxyManager()      ← MAVProxy with GUI
  │     └─ GcsMavLinkCollector()     ← pymavlink Thread
  ├─ signal.signal(SIGINT, SIGTERM)
  ├─ server.start() L901
  │     ├─ mavproxy.start()          ← Subprocess: MAVProxy.mavproxy
  │     ├─ mavlink_monitor.start() L762
  │     │     └─ Thread: _listen_loop()
  │     └─ Thread: _server_loop() L813
  └─ while server.running: time.sleep(1.0)
```

### Command Handlers (`_handle_command`)

| Command | Action | Evidence |
|:---|:---|:---|
| `ping` | Return `{"status": "ok"}` | Used for health check. |
| `get_info` | Return hostname, IP, kernel | Used for JSONL context. |
| `prepare_rekey` | Stop proxy, reset collectors | Suite transition. |
| `start_proxy` | Start GCS proxy subprocess | Per-suite activation. |
| `stop_suite` | Stop proxy, return MAVLink validation | Suite teardown. |

### Threads Spawned (GCS)

| Thread Name | Blocking Call | Owner |
|:---|:---|:---|
| `server_thread` | `socket.accept()` | `GcsBenchmarkServer` |
| `mavlink_listen_thread` | `conn.recv_match(blocking=True)` | `GcsMavLinkCollector` |

### Silent Failure Paths

| Location | Failure Mode | Consequence |
|:---|:---|:---|
| `L259-261` `GcsMavProxyManager.start` | Process exits early | Log "Exited early". Returns `False`. |
| `L364-366` `GcsMavLinkCollector.start` | `except Exception` | Returns `False`. Continues. |
| `L772-775` `start_proxy` handler | MAVProxy not running | **FIXED:** Now restarts MAVProxy. |

---

## 3. Subprocess Lifecycle

| Subprocess | Parent | Platform | Managed By |
|:---|:---|:---|:---|
| `mavproxy-drone-bench` | `sdrone_bench` | Linux (RPi) | `ManagedProcess` |
| `drone-proxy-{suite}` | `sdrone_bench` | Linux (RPi) | `DroneProxyManager` |
| `MAVProxy.mavproxy` | `sgcs_bench` | Windows | `subprocess.Popen` (Direct) |
| `gcs-proxy-{suite}` | `sgcs_bench` | Windows | `GcsProxyManager` |

---

## 4. Exception Swallowing Inventory

| File | Line | Pattern | Risk |
|:---|:---:|:---|:---|
| `sdrone_bench.py` | 169 | `except Exception:` pass | High (Silent Power Failure) |
| `sdrone_bench.py` | 381 | `except Exception:` pass | Medium (MAVLink Listener) |
| `sdrone_bench.py` | 698 | `except Exception:` logs | Low (Logged, No JSONL) |
| `sgcs_bench.py` | 374 | `except Exception:` pass | Medium (MAVLink Listener) |

---

## 5. Verdict

| Question | Answer | Evidence |
|:---|:---|:---|
| Does code reach `main()`? | ✅ YES | `if __name__ == "__main__"` present. |
| Are subprocesses spawned? | ✅ YES | `ManagedProcess`, `subprocess.Popen` verified. |
| Are threads started? | ✅ YES | `Thread.start()` calls identified. |
| Are failures logged? | ⚠️ PARTIAL | Some `except` blocks are silent. |
| Can JSONL be missing? | ⚠️ YES | If suite fails, L698 skips write. |
