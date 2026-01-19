# GCS Real MAV Bench Report

## Implementation Status: COMPLETE

The `sgcs_bench.py` server has been updated to fix the critical port mismatch and support **Real MAVLink Bench Mode**.

### 1. Port Alignment Fix
*   **Old Behavior:** Listened on `14550` (Incorrect).
*   **New Behavior:** Listens on `47002` (Correct, matches `GCS_PLAINTEXT_RX` output from Crypto Proxy).
*   **Impact:** MAVProxy now correctly receives decrypted MAVLink traffic from the proxy.

### 2. Output Configuration
*   **Output 1:** `udp:127.0.0.1:14552` (Sniff Port for Metrics).
*   **Output 2:** `udp:127.0.0.1:14550` (QGC/Local Tools).
*   **Benefit:** Enables simultaneous automated metric collection (via `GcsMavLinkCollector`) and human observability (via QGC).

### 3. GUI Enablement
*   **Status:** `MAVPROXY_ENABLE_GUI = True` verified.
*   **Flags:** `--map --console` passed to `MAVProxy.mavproxy`.
*   **Observability:** Human operator can verify "Link 1 down/up" messages and map updates.

### 4. Metric Collector
*   **Status:** `GcsMavLinkCollector` listens on `14552`.
*   **Data Flow:** Proxy (47002) -> MAVProxy -> UDP Out (14552) -> Collector.
*   **Verification:** `benchmark_gcs_*.json` output should contain `mavlink_validation` block with `total_msgs_received > 0`.
