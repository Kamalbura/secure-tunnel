# Drone Real MAV Bench Report

## Implementation Status: COMPLETE

The `sdrone_bench.py` controller has been refactored to support **Real MAVLink Bench Mode**.

### 1. Persistent MAVProxy Integration
*   **Method:** `start_persistent_mavproxy()` added to controller.
*   **Source:** `/dev/ttyACM0` (or `MAV_FC_DEVICE` config).
*   **Output 1:** `udp:127.0.0.1:47003` (To Drone Crypto Proxy).
*   **Output 2:** `udp:127.0.0.1:14552` (To Local Metrics Collector).
*   **Flags:** `--nowait --daemon --dialect=ardupilotmega`.
*   **Lifecycle:** Starts at benchmark init, stops at benchmark end.

### 2. Removal of Synthetic Traffic
*   **Component:** `UdpEchoServer` class and instance **removed**.
*   **Logic:** The "Traffic Phase" no longer generates dummy UDP packets. Instead, the loop simply sleeps for `cycle_time` while the MAVProxy background process continuously forwards data from the Flight Controller.
*   **Impact:** Throughput metrics (`packets_sent`) now reflect actual telemetry rates (approx 2-10 Hz depending on stream rates) rather than synthetic blaster rates.

### 3. Metric Realignment
*   **Data Plane:** `packets_received` now populated from `MavLinkMetricsCollector` (sniffing port 14552).
*   **Latency:** One-way latency cannot be measured directly (no synchronized echo timestamps). Jitter is estimated via heartbeat arrival variance.
*   **Integrity:** Sequence gaps are tracked via `pymavlink`.

### 4. Verification Check
*   **Process:** Requires `mavproxy.py` to be running.
*   **Hardware:** Requires `/dev/ttyACM0` to be physically connected.
*   **Success Criteria:** `mavproxy_drone_bench_*.log` should show connection messages. `benchmark_*.jsonl` should show `mavproxy_drone_total_msgs_received > 0` and `fc_mode`.
