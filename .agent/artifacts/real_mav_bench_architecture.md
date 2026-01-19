# Real MAV Bench Mode: System Architecture

**Status:** IMPLEMENTED & VERIFIED
**Date:** 2026-01-19

## Overview
This architecture replaces the synthetic UDP traffic generation with a real MAVLink telemetry stream originating from the Flight Controller (Pixhawk).

## Data Flow Pipeline

1.  **Source (Drone):**
    *   **Hardware:** Pixhawk 6C (or compatible) via USB Serial.
    *   **Interface:** `/dev/ttyACM0` (Configurable via `MAV_FC_DEVICE`).
    *   **Process:** `MAVProxy` (Headless, Persistent).
    *   **Arguments:** `--master=/dev/ttyACM0 --dialect=ardupilotmega --nowait --daemon`.
    *   **Output 1 (Tunnel):** `udp:127.0.0.1:47003` (Target: Drone Crypto Proxy).
    *   **Output 2 (Local):** `udp:127.0.0.1:14552` (Target: `MavLinkMetricsCollector` for validation).

2.  **Tunnel (Crypto Layer):**
    *   **Drone Proxy:** Listens `47003`, Encrypts -> UDP Network (`46011`).
    *   **GCS Proxy:** Listens `46011` (Network), Decrypts -> `udp:127.0.0.1:47002` (`GCS_PLAINTEXT_RX`).

3.  **Sink (GCS):**
    *   **Process:** `MAVProxy` (GUI Enabled).
    *   **Input:** `udp:127.0.0.1:47002` (From GCS Crypto Proxy).
    *   **Flags:** `--map --console`.
    *   **Output 1 (QGC):** `udp:127.0.0.1:14550` (Target: QGroundControl).
    *   **Output 2 (Local):** `udp:127.0.0.1:14552` (Target: `GcsMavLinkCollector` for validation).

## Component Lifecycle

| Phase | Drone Controller (`sdrone_bench.py`) | GCS Server (`sgcs_bench.py`) |
| :--- | :--- | :--- |
| **Pre-Flight** | Starts `start_persistent_mavproxy()` (Once) | Starts MAVProxy with GUI (Once) |
| **Suite Start** | Selects Suite, Starts Drone PQC Proxy | Receives 'start_proxy', Starts GCS PQC Proxy |
| **Handshake** | Performs PQC KEM Handshake | Authenticates Peer |
| **Traffic** | Sleeps 10s (Allows MAVLink to flow) | Passive (Observers MAVLink packet counts) |
| **Suite Stop** | Stops Drone PQC Proxy | Stops GCS PQC Proxy |
| **Post-Flight** | Stops MAVProxy | Stops MAVProxy |

## Observability & Metrics

*   **Human:**
    *   GCS Screen: MAVProxy Map & Console active.
    *   QGroundControl (Optional): Connects to UDP 14550.
*   **Automated (JSONL):**
    *   `packets_received`: Sourced from `MavLinkMetricsCollector` (Port 14552).
    *   `jitter`: Calculated from `HEARTBEAT` arrival intervals.
    *   `integrity`: Sequence gaps detected by `pymavlink` parser.
