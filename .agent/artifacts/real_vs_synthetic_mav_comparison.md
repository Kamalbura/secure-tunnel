# Real vs Synthetic MAV Comparison

| Metric | Synthetic Mode (Legacy) | Real MAV Mode (New) |
| :--- | :--- | :--- |
| **Traffic Source** | `TrafficGenerator` (Python Blaster) | MAVProxy + Flight Controller (Hardware) |
| **Throughput** | High (110 Mbps target) | Low (Telemetry rate, ~10-50 Kbps) |
| **Packet Content** | `{"ts": ..., "pad": "X"}` | Real MAVLink Packets (HEARTBEAT, ATTITUDE, etc.) |
| **Integrity Check** | JSON decoding + Timestamp | MAVLink CRC + Sequence Numbers (pymavlink) |
| **Latency** | One-Way (Embedded TS) | N/A (Requires Clock Sync or Round Trip) |
| **Jitter** | Inter-arrival variance of UDP packets | Variance of HEARTBEAT arrival intervals |
| **Loss** | Calculated from Echo TX/RX count | Inferred from Sequence Gaps |
| **Goal** | Stress test crypto throughput | Validation of functional correctness & policy impact |

## Key Differences for Analysis
1.  **Metric Magnitude:** Expect `packets_sent` to drop from ~11,000/sec to ~10-50/sec. This is **normal**.
2.  **Latency Missing:** One-way latency will report 0. Use Jitter (`jitter_avg_ms`) as the primary stability metric.
3.  **Policy Impact:** Crypto overhead (encryption/decryption time) is constant per packet, but total CPU load will be lower due to lower packet rate. However, the *latency impact* on a real-time stream is more observable via "Link Down" events in QGC.
