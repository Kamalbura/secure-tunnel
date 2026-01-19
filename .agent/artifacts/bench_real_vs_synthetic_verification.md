# Real MAV Bench Verification: Forensic Report

**Date:** 2026-01-19
**Agent:** Antigravity (Forensic Mode)
**Subject:** Real MAVLink Traffic Enforcement

## Executive Summary
**VERDICT: Benchmark mode contains REAL MAVLink traffic.**

The benchmark system has been successfully audited. Synthetic traffic generators have been removed from the active execution path. REAL MAVLink traffic from `/dev/ttyACM0` is bridged end-to-end to the GCS MAVProxy instance.

## 1. Forensic Classification Table

| Component | File | Present | Behavior | Classification | Evidence |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **MAVProxy (Drone)** | `sdrone_bench.py` | YES | Persistent process, bridges `/dev/ttyACM0` -> `UDP:47003` (Crypto) + `UDP:14552` (Sniffer) | **REAL** | `start_persistent_mavproxy()` (L721), Call site (L660) |
| **Pixhawk Serial** | `sdrone_bench.py` | YES | Configured via `MAV_FC_DEVICE` (default `/dev/ttyACM0`) | **REAL** | `CONFIG.get("MAV_FC_DEVICE", ...)` (L726) |
| **Synthetic Traffic** | `sdrone_bench.py` | **NO** | `UdpEchoServer` removed; `start_traffic` command logic replaced with `time.sleep()` | **REMOVED** | Comment (L454), `run` loop (L878-881) |
| **MAVProxy (GCS)** | `sgcs_bench.py` | YES | Listens on `UDP:47002` (Crypto Output), outputs to `UDP:14550` (QGC) + `UDP:14552` (Sniffer). GUI Enabled. | **REAL** | `MAVLINK_INPUT_PORT = 47002` (L64), `GcsMavProxyManager` (L111) |
| **pymavlink** | `sgcs_bench.py` | YES | Passive observer on `UDP:14552`. Validates sequence numbers and heartbeats. | **REAL (Observer)** | `GcsMavLinkCollector` (L317) |
| **Echo Server (GCS)** | `sgcs_bench.py` | YES (Dead) | Code exists but `start_traffic` is NEVER sent by Drone controller. | **INACTIVE** | `TrafficGenerator` class exists but unused in flow |

## 2. Logic Audit: Bench vs. Standard MAV

The benchmark implementation now mirrors the standard `sdrone_mav.py` control logic:

*   **Drone Side:** `sdrone_bench.py` re-implements the `MavProxyManager` logic inline (`start_persistent_mavproxy`), using the exact same `MAVProxy` command line arguments (`--master`, `--out`, `--dialect`, `--nowait`).
*   **GCS Side:** `sgcs_bench.py` correctly aligns `MAVLINK_INPUT_PORT` with `GCS_PLAINTEXT_RX` (47002), ensuring the decrypted tunnel traffic feeds directly into MAVProxy, just like `sgcs_mav.py` (which uses `auto/mav`).
*   **Key Delta:** The Benchmark Controller (`sdrone_bench`) manages the *lifecycle* (Start/Stop per suite) and *Data Collection* (pyMavLink sniffing), whereas the Standard Controller (`sdrone_mav`) is an infinite loop that just keeps the link up.

## 3. Metric Source Verification

| Metric | Source Component | Validity |
| :--- | :--- | :--- |
| **Throughput (`packets_received`)** | `MavLinkMetricsCollector` (Sniffer) | **VALID** (Counts real UDP payloads on port 14552) |
| **Jitter (`jitter_avg_ms`)** | `MavLinkMetricsCollector` (Heartbeat) | **VALID** (Calculated from `HEARTBEAT` arrival deltas) |
| **Packet Loss** | Inferable via `seq_gap_count` | **VALID** (pymavlink sequence checking) |
| **Latency** | N/A (One-way unsynchronized) | **KNOWN LIMITATION** (Reported as 0 or estimated) |

## 4. Conclusion

The system enforces "Real MAV Bench Mode". Synthetic traffic cannot flow because the generation logic was excised from the Drone controller. Any traffic observed on the GCS **MUST** originate from the Drone's serial port (or a replay log if configured manually, but default is hardware).
