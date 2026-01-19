# Heartbeat & Link Robustness

> Phase 0.95 • Generated: 2026-01-19
> Status: PENDING LIVE VERIFICATION

---

## Expected Behavior

| Metric | Expected |
|--------|----------|
| Heartbeat interval | 1 Hz (1 per second) |
| Loss tolerance | <5% |
| Reconnect time | <2s |

---

## Monitoring Points

### Drone Side (`MavLinkMetricsCollector`)

```python
# Lines 321-449 in sdrone_bench.py
- heartbeat_interval_avg_ms
- heartbeat_interval_jitter_ms
- seq_gap_count
- msg_type_counts
```

### GCS Side (`GcsMavLinkCollector`)

```python
# Lines 225-319 in sgcs_bench.py
- total_msgs_received
- seq_gap_count
```

---

## Potential Loss Causes

| Cause | Detection |
|-------|-----------|
| Suite switch | Proxy restart |
| Handshake | Crypto init |
| Traffic spike | Buffer overflow |
| Network | Ping timeout |

---

## Live Verification Required

Run 5-suite partial benchmark and observe:
1. MAVProxy console for heartbeat
2. Log files for seq_gap_count
3. JSONL for mavlink_integrity

---

## Verdict

**⏳ PENDING** — Requires live execution to verify.
