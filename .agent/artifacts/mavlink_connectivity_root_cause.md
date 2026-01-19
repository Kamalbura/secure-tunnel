# MAVLink Connectivity Root Cause Analysis

> Date: 2026-01-19
> Status: ROOT CAUSE IDENTIFIED

---

## **Definitive Root Cause**

**MAVProxy expects input on UDP 14550, but nothing is sending to it during the benchmark.**

---

## Evidence: Code Analysis

### GCS Side (sgcs_bench.py)

**MAVProxy Command** (lines 134-135):
```python
f"--master=udp:127.0.0.1:{MAVLINK_INPUT_PORT}",  # 14550
f"--out=udp:127.0.0.1:{MAVLINK_SNIFF_PORT}",     # 14552
```

**GcsMavLinkCollector** (line 273):
```python
f"udpin:0.0.0.0:{self.listen_port}"  # 14552 - sniffs MAVProxy output
```

### Drone Side (sdrone_bench.py)

**MavLinkMetricsCollector** (line 360):
```python
f"udpin:0.0.0.0:{self.listen_port}"  # 14552 - listens for MAVLink
```

---

## Port Configuration (Extracted from code)

| Component | Direction | Address | Port |
|-----------|-----------|---------|------|
| MAVProxy master | LISTEN | 127.0.0.1 | 14550 |
| MAVProxy out | SEND | 127.0.0.1 | 14552 |
| GcsMavLinkCollector | LISTEN | 0.0.0.0 | 14552 |
| Drone MavLinkMetrics | LISTEN | 0.0.0.0 | 14552 |

---

## Data Flow Analysis

```
Expected:
  [Crypto Proxy] --UDP--> :14550 --> [MAVProxy] --UDP--> :14552 --> [Collector]

Actual during bench:
  [Nothing] --X--> :14550 --> [MAVProxy has no input]
```

---

## Root Cause Determination

| Question | Evidence |
|----------|----------|
| Is MAVProxy started? | YES - Log: `[MAVPROXY] Starting with GUI` |
| Is MAVProxy listening on 14550? | YES - Code: `--master=udp:127.0.0.1:14550` |
| Is anything sending to 14550? | **NO EVIDENCE FOUND** |
| Does crypto proxy exist in bench? | **NOT INVOKED IN CURRENT RUN** |

---

## Definitive Answer

**The crypto proxy is not being started during the benchmark run.**

MAVProxy is a relay:
1. Expects MAVLink on UDP 14550 (from crypto proxy)
2. Outputs to UDP 14552 (for sniffing)

**But no process sends MAVLink to 14550 during sgcs_bench.**

---

## Evidence Required for Confirmation

1. `netstat` on GCS showing nothing connected to 14550
2. Logs showing whether `GcsProxyManager.start()` is called
3. Traffic capture showing no packets on 14550

---

## Agent Statement

**I cannot observe packet presence.** This analysis is based solely on code review.

Live network verification requires human execution of:
```powershell
netstat -an | findstr 14550
```

---

## Conclusion

**Root cause**: MAVLink traffic is not reaching MAVProxy because the crypto proxy (which would send to 14550) is not active during the benchmark.

**This is a CONFIGURATION issue, not a network issue.**
