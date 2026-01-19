# Real MAV Bench Mode: Verification Report

**Date:** 2026-01-19
**Subject:** Real MAVLink Traffic Enforcement Verification
**Status:** **VERIFIED**

## 1. Executive Summary
The `sdrone_bench.py` and `sgcs_bench.py` scripts have been forensically audited and compared against the target architecture. The system **GUARANTEES** that only real MAVLink traffic (from the Flight Controller) will flow through the encrypted tunnel during benchmarking. All usage of synthetic traffic generators (`UdpEchoServer`, `TrafficGenerator`) has been removed from the active execution path.

## 2. Architecture Verification

### 2.1 Drone Side (`sdrone_bench.py`)
*   **MAVLink Source:** Real Hardware.
    *   **Evidence:** Calls `start_persistent_mavproxy()` at L660.
    *   **Configuration:** Uses `MAV_FC_DEVICE` (default `/dev/ttyACM0`).
    *   **Routing:** MAVProxy bridges Serial -> `UDP:47003` (Crypto Input) + `UDP:14552` (Sniffer).
    *   **Lifecycle:** Started once at benchmarks start, persistent across suites.
*   **Synthetic Logic:** REMOVED.
    *   **Evidence:** `UdpEchoServer` class body replaced with comment "REMOVED for Real MAV Bench Mode" (L454).
    *   **Execution:** The `_benchmark_suite` traffic phase (L874) contains only a `time.sleep(self.cycle_time)`, allowing the background MAVProxy stream to provide the load.

### 2.2 GCS Side (`sgcs_bench.py`)
*   **MAVLink Sink:** Real MAVProxy Instance.
    *   **Evidence:** `GcsMavProxyManager` starts `MAVProxy` listening on `MAVLINK_INPUT_PORT`.
    *   **Port Alignment:** `MAVLINK_INPUT_PORT` == `GCS_PLAINTEXT_RX` (47002), matching `core/config.py`.
    *   **GUI:** Enabled via `MAVPROXY_ENABLE_GUI = True` and passed `--map --console` flags.
*   **Synthetic Logic:** DORMANT.
    *   **Evidence:** `TrafficGenerator` class exists, but the `start_traffic` command is **NEVER SENT** by the drone controller (verified in `sdrone_bench.py` `_benchmark_suite`).
    *   **Risk:** Low. Code is dead and unreachable in this flow.

### 2.3 Data Flow
1.  **Drone FC** (`/dev/ttyACM0`) -> **Drone MAVProxy**
2.  **Drone MAVProxy** -> **Port 47003** (UDP)
3.  **Port 47003** -> **Drone PQC Proxy** (Encrypts)
4.  **Network** -> **GCS PQC Proxy** (Decrypts)
5.  **GCS PQC Proxy** -> **Port 47002** (UDP)
6.  **Port 47002** -> **GCS MAVProxy**
7.  **GCS MAVProxy** -> **GUI** + **Port 14550** (QGC) + **Port 14552** (Metrics)

## 3. Metric Integrity

| Metric | Origin Code | Verification |
| :--- | :--- | :--- |
| **Throughput (RX)** | `MavLinkMetricsCollector` | **VALID.** Counts physical packets arriving on sniffer port 14552. |
| **Packet Loss** | `MavLinkMetricsCollector` | **VALID.** Uses `pymavlink` sequence number inspection (`seq_gap_count`). |
| **Jitter** | `MavLinkMetricsCollector` | **VALID.** Calculates standard deviation of `HEARTBEAT` arrival intervals. |
| **Latency** | `sdrone_bench.py` L923 | **ZEROED.** One-way latency cannot be measured without synchronized clocks. Reported as 0. |

## 4. Conclusion
The implementation faithfully adheres to the "Real MAV Bench Mode" requirements.
*   **NO** synthetic traffic is generated.
*   **REAL** MAVLink devices are required.
*   **MAVPROXY** infrastructure is correctly managed.

**Recommendation:** Proceed to hardware execution.
