# Benchmark Execution Model

> Phase 0.5 • Generated: 2026-01-18
> Status: VERIFIED FROM CODE

---

## End-to-End Flow

```mermaid
sequenceDiagram
    participant Drone as sdrone_bench.py
    participant GCS as sgcs_bench.py
    
    Note over Drone,GCS: STARTUP
    GCS->>GCS: Start ControlServer (TCP:48080)
    GCS->>GCS: Start MAVProxy (GUI optional)
    GCS->>GCS: Start MAVLink monitor
    
    Drone->>GCS: ping
    GCS-->>Drone: ok (run_id)
    
    Drone->>GCS: get_info
    GCS-->>Drone: hostname, kernel, python
    
    Note over Drone,GCS: FOR EACH SUITE
    
    Drone->>Drone: Start power sampling (100Hz)
    Drone->>Drone: Start CPU sampling
    
    Drone->>GCS: prepare_rekey
    GCS-->>Drone: ok
    
    Drone->>GCS: start_proxy(suite)
    GCS->>GCS: Start crypto proxy
    GCS-->>Drone: ok (handshake_start_time)
    
    Drone->>Drone: Start local proxy → Handshake
    
    Drone->>GCS: start_traffic(duration=10s)
    GCS->>GCS: TrafficGenerator.start()
    
    Note over Drone,GCS: TRAFFIC PHASE (10s)
    GCS->>Drone: UDP packets @ 110 Mbps
    Drone->>GCS: Echo packets
    
    Note over Drone: time.sleep(cycle_time)
    
    Drone->>Drone: Stop proxy
    Drone->>GCS: stop_suite
    GCS->>GCS: Collect traffic stats
    GCS-->>Drone: traffic_stats, mavlink_validation
    
    Drone->>Drone: Stop power/CPU sampling
    Drone->>Drone: Compute metrics
    Drone->>Drone: Write to JSONL
```

---

## Timing Model

| Phase | Duration | Trigger |
|-------|----------|---------|
| Handshake | Variable (~1-5s) | Proxy start |
| Traffic | Fixed (10s default) | CLI `--cycle-time` |
| Inter-suite | 2s | Hardcoded delay |
| Total per suite | ~15-17s | Computed |

---

## Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│                         DRONE                                │
├─────────────────────────────────────────────────────────────┤
│  DroneBenchmarkController                                    │
│  ├── DronePowerMonitor → INA219 (100Hz)                      │
│  ├── SystemMetricsCollector → psutil (0.5Hz)                 │
│  ├── MavLinkMetricsCollector → pymavlink                     │
│  ├── UdpEchoServer → latency extraction                      │
│  └── DroneProxyManager → core.run_proxy                      │
│                                                              │
│  Output: logs/benchmarks/{run_id}/benchmark_{run_id}.jsonl   │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           │ TCP:48080 (control)
                           │ UDP:46011/46012 (encrypted)
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                          GCS                                 │
├─────────────────────────────────────────────────────────────┤
│  GcsBenchmarkServer                                          │
│  ├── GcsProxyManager → core.run_proxy                        │
│  ├── TrafficGenerator → UDP blast + timestamp                │
│  ├── GcsMavProxyManager → MAVProxy (optional GUI)            │
│  └── GcsMavLinkCollector → validation only                   │
│                                                              │
│  Returns: JSON via TCP control channel                       │
└─────────────────────────────────────────────────────────────┘
```

---

## Policy Engine

| Property | Value |
|----------|-------|
| Policy Name | `deterministic_rotation` |
| Suite Order | Alphabetical by suite ID |
| Cycle Time | 10s (default) |
| Rekey | None (single suite per cycle) |
| Termination | All suites complete or `--max-suites` reached |

---

## Command Protocol

| Command | Direction | Purpose |
|---------|-----------|---------|
| `ping` | Drone → GCS | Readiness check |
| `get_info` | Drone → GCS | Collect GCS environment |
| `prepare_rekey` | Drone → GCS | Stop previous proxy |
| `start_proxy` | Drone → GCS | Start proxy for suite |
| `start_traffic` | Drone → GCS | Begin traffic generation |
| `stop_suite` | Drone → GCS | Stop and collect metrics |
| `shutdown` | Drone → GCS | Graceful termination |
