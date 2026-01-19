# Remaining Risks & Mitigations

## 1. Flight Controller Availability
*   **Risk:** `sdrone_bench.py` relies on `/dev/ttyACM0`. If the Pixhawk is unplugged or on a different port (e.g., `/dev/ttyUSB0`), MAVProxy will fail to start.
*   **Mitigation:** Script uses `MAV_FC_DEVICE` from config, defaulting to `/dev/ttyACM0`. Check `ls /dev/tty*` if it fails.
*   **Fallback:** If no FC is present, only `sdrone_mav.py` (sim mode) or synthetic benches work.

## 2. Clock Synchronization
*   **Risk:** Without NTP/PTP, one-way latency metrics are impossible. The previous synthetic bench used "echo" timestamps which were valid relative to the sender.
*   **Impact:** Real MAVLink is one-way (Drone -> GCS). We cannot measure RTT unless we send commands and time the ACK. The current `MavLinkMetricsCollector` does not active-ping.
*   **Acceptance:** We accept that "Latency" metric will be 0, and rely on "Jitter" and "Link Quality" (Sequence Gaps).

## 3. Dead Code in GCS Controller
*   **Risk:** `sgcs_bench.py` still contains the `TrafficGenerator` class and the `start_traffic` command handler. While `sdrone_bench.py` (the controller) has removed the logic to call this, a rogue or legacy controller could still trigger synthetic traffic, confusing the logs.
*   **Mitigation:** `sdrone_bench.py` audit confirmed `start_traffic` call is removed.
*   **Recommendation:** In a future cleanup refactor, remove `TrafficGenerator` from `sgcs_bench.py` entirely to enforce "Correct by Construction".

## 4. Port Conflicts
*   **Risk:** If `sdrone_mav.py` is running simultaneously with `sdrone_bench.py`, both try to grab `/dev/ttyACM0`.
*   **Mitigation:** User must ensure `sdrone_mav.py` is STOPPED before running bench.

## 5. GCS GUI Dependency
*   **Risk:** On some minimal Windows environments or SSH sessions, launching a GUI (`--map --console`) might crash or block.
*   **Mitigation:** `sgcs_bench.py` has a `--no-gui` flag. However, the requirement is "GUI VISIBLE".
