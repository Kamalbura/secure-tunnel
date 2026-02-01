# Git Diff Analysis: Main Branch vs Working Branch

## Executive Summary

The working branch (HEAD at 302386e, based on 94749ec) works successfully because it **simplifies and streamlines** the benchmark architecture, removing complex dependencies while keeping the essential components. The main branch (72e28931) fails because it includes **overcomplicated, fragile components** that break easily.

---

## 1. CRITICAL FILE: `core/run_proxy.py`

### Status: **DELETED** in working branch

**Main Branch (72e2893):** Has a 126-line entry point with:
- Complex OQS import logic
- ArgParser with multiple key file options
- Manual PYTHONPATH manipulation
- Separate process entry point for proxies

**Working Branch:** **File deleted entirely**

### Root Cause Analysis:
The main branch tried to use `run_proxy.py` as a subprocess entry point, but this adds:
1. PYTHONPATH environment issues
2. Redundant OQS import validation
3. Extra process startup overhead
4. Fragile path resolution

### Recommendation:
**DO NOT backport** - The working branch correctly embeds proxy logic directly without a separate entry point.

---

## 2. CRITICAL FILE: `core/metrics_schema.py`

### Key Differences

| Field Pattern | Main Branch | Working Branch |
|---------------|-------------|----------------|
| Default Types | `Optional[T] = None` | `T = ""` or `T = 0.0` |
| Missing Values | `None` everywhere | Empty defaults (0, "", False) |
| Clock sync | `clock_offset_method: Optional[str]` | `clock_offset_method: str = "ntp"` |

### Specific Changes:

**RunContextMetrics:**
```python
# MAIN BRANCH (FRAGILE):
git_commit_hash: Optional[str] = None
gcs_hostname: Optional[str] = None
clock_offset_ms: Optional[float] = None

# WORKING BRANCH (ROBUST):
git_commit_hash: str = ""
gcs_hostname: str = ""
clock_offset_ms: float = 0.0
```

**HandshakeMetrics:**
```python
# MAIN BRANCH:
handshake_start_time_drone: Optional[float] = None
handshake_total_duration_ms: Optional[float] = None
protocol_handshake_duration_ms: Optional[float] = None  # REMOVED in working
end_to_end_handshake_duration_ms: Optional[float] = None  # REMOVED in working

# WORKING BRANCH:
handshake_start_time_drone: float = 0.0
handshake_start_time_gcs: float = 0.0  # NEW
handshake_end_time_gcs: float = 0.0    # NEW
handshake_total_duration_ms: float = 0.0
handshake_rtt_ms: float = 0.0          # NEW
```

**SuiteCryptoIdentity (Working branch adds):**
```python
kem_parameter_set: str = ""
sig_parameter_set: str = ""
aead_mode: str = ""
suite_tier: str = ""
suite_order_index: int = 0
```

**LatencyJitterMetrics (COMPLETELY RESTRUCTURED):**
```python
# MAIN BRANCH (MAVLink-based):
one_way_latency_avg_ms: Optional[float] = None
one_way_latency_p95_ms: Optional[float] = None
latency_sample_count: Optional[int] = None
latency_invalid_reason: Optional[str] = None
one_way_latency_valid: Optional[bool] = None
rtt_avg_ms: Optional[float] = None
rtt_valid: Optional[bool] = None

# WORKING BRANCH (Tracker-based):
one_way_latency_avg_ms: float = 0.0
one_way_latency_p50_ms: float = 0.0  # NEW percentile
one_way_latency_p95_ms: float = 0.0
one_way_latency_max_ms: float = 0.0  # NEW
round_trip_latency_avg_ms: float = 0.0  # Renamed
round_trip_latency_p50_ms: float = 0.0
round_trip_latency_p95_ms: float = 0.0
round_trip_latency_max_ms: float = 0.0
latency_samples: List[float] = field(default_factory=list)  # RAW SAMPLES
```

### Root Cause Analysis:
Main branch uses `Optional[T] = None` everywhere, requiring **null checks on every access**. When any metric isn't collected, the code fails with `TypeError: unsupported operand type(s) for +: 'NoneType' and 'float'`.

Working branch uses **default values** so arithmetic operations always work.

### Recommendation:
**MUST BACKPORT** the `Optional -> default` pattern from working branch.

---

## 3. CRITICAL FILE: `core/metrics_aggregator.py`

### Major Differences

**1. Power Sampling (Line ~235):**
```python
# MAIN BRANCH (Role-restricted):
if self.role == "drone" and self.power_collector and self.power_collector.backend != "none":

# WORKING BRANCH (Flexible):
if self.power_collector and self.power_collector.backend != "none":
```

**2. Handshake Recording (Lines ~256-281):**
```python
# MAIN BRANCH (Drone-only timestamps):
h.handshake_start_time_drone = now
h.handshake_end_time_drone = now
h.end_to_end_handshake_duration_ms = h.handshake_total_duration_ms

# WORKING BRANCH (Role-aware timestamps):
if self.role == "gcs":
    h.handshake_start_time_gcs = now
    h.handshake_end_time_gcs = now
else:
    h.handshake_start_time_drone = now
    h.handshake_end_time_drone = now
```

**3. Null-Safe Arithmetic (Lines ~339-450):**
```python
# MAIN BRANCH (Complex null handling):
if cp.kem_keygen_time_ms is not None and cp.kem_encapsulation_time_ms is not None...:
    cp.total_crypto_time_ms = sum(total_parts)
else:
    cp.total_crypto_time_ms = None

# WORKING BRANCH (Simple addition):
cp.total_crypto_time_ms = (
    cp.kem_keygen_time_ms + 
    cp.kem_encapsulation_time_ms + 
    cp.kem_decapsulation_time_ms +
    cp.signature_sign_time_ms +
    cp.signature_verify_time_ms
)
```

**4. Data Plane Metrics (Lines ~371-420):**
```python
# MAIN BRANCH (Null propagation nightmare):
dp.ptx_in = counters.get("ptx_in")  # Can be None!
if dp.packets_sent is not None and dp.packets_dropped is not None and dp.packets_sent > 0:
    dp.packet_loss_ratio = dp.packets_dropped / dp.packets_sent
else:
    dp.packet_loss_ratio = None

# WORKING BRANCH (Safe defaults):
dp.ptx_in = counters.get("ptx_in", 0)
if dp.packets_sent > 0:
    dp.packet_loss_ratio = dp.packets_dropped / dp.packets_sent
```

**5. Latency Collection (Lines ~419-530):**
```python
# MAIN BRANCH (MAVLink-dependent):
m.latency_jitter.one_way_latency_avg_ms = mavlink_metrics.get("one_way_latency_avg_ms")
# Requires MavLinkMetricsCollector to be working

# WORKING BRANCH (Internal tracker):
lat_stats = self.latency_tracker.get_stats()
m.latency_jitter.one_way_latency_avg_ms = lat_stats["avg_ms"]
# Uses self-contained LatencyTracker
```

**6. Massive Null-Setting Blocks (Lines ~530-750 - REMOVED):**
Main branch has ~220 lines of code that explicitly sets fields to `None` when data isn't collected:
```python
# MAIN BRANCH (Example of bloat):
m.data_plane.achieved_throughput_mbps = None
m.data_plane.goodput_mbps = None
m.data_plane.wire_rate_mbps = None
m.data_plane.packets_sent = None
# ... 50 more lines like this
self._mark_metric_status("data_plane", "not_collected", "proxy_counters_missing")
```

**Working branch removes ALL of this** because default values handle it.

### Root Cause Analysis:
Main branch's aggregator is **defensively overengineered** with null checks everywhere. This makes:
1. Code 3x longer
2. Any missing piece causes cascading `None` values
3. `_mark_metric_status()` tracking adds overhead without benefit

### Recommendation:
**MUST BACKPORT** the simplified aggregator from working branch.

---

## 4. CRITICAL FILE: `sscheduler/sgcs_bench.py`

### Key Differences

**1. Import Changes:**
```python
# MAIN BRANCH:
from core.mavlink_collector import MavLinkMetricsCollector, HAS_PYMAVLINK
from core.metrics_collectors import SystemCollector
from core.metrics_aggregator import MetricsAggregator

# WORKING BRANCH:
# All removed - uses simplified GcsMavLinkCollector inline
```

**2. GcsSystemMetricsCollector Class (Lines ~305-370):**
```python
# MAIN BRANCH: 60-line class with threading, sampling, CPU/memory collection
class GcsSystemMetricsCollector:
    def __init__(self, sample_interval_s: float = 0.5):
        self._collector = SystemCollector()
        ...

# WORKING BRANCH: DELETED
# Comment: "GcsSystemMetricsCollector REMOVED - GCS resources not policy-relevant"
```

**3. GcsBenchmarkServer Initialization:**
```python
# MAIN BRANCH:
self.mavlink_monitor = MavLinkMetricsCollector(role="gcs") if HAS_PYMAVLINK else None
self.mavlink_available = HAS_PYMAVLINK
self.system_metrics = GcsSystemMetricsCollector()
self.metrics_aggregator = MetricsAggregator(role="gcs", output_dir=...)
self._handshake_timeout_s = 45.0

# WORKING BRANCH:
self.mavlink_monitor = GcsMavLinkCollector()  # Simplified inline class
# No system_metrics
# No metrics_aggregator
# No handshake_timeout
```

**4. Proxy Start Logic:**
```python
# MAIN BRANCH (Complex):
env = os.environ.copy()
project_root = str(Path(__file__).parent.parent.absolute())
existing_pp = env.get("PYTHONPATH", "")
if project_root not in existing_pp:
    sep = ";" if sys.platform.startswith("win") else ":"
    env["PYTHONPATH"] = f"{project_root}{sep}{existing_pp}"
self.managed_proc = ManagedProcess(cmd=cmd, ..., env=env)

# WORKING BRANCH (Simple):
self.managed_proc = ManagedProcess(cmd=cmd, ..., stderr=subprocess.STDOUT)
# No PYTHONPATH manipulation
```

**5. Handshake Timeout Logic (REMOVED in working):**
```python
# MAIN BRANCH:
if self._wait_for_handshake_ok(timeout_s=self._handshake_timeout_s):
    self.metrics_aggregator.record_handshake_end(success=True)
else:
    self.metrics_aggregator.record_handshake_end(success=False, failure_reason="handshake_timeout")

# WORKING BRANCH:
# Simply removed - no timeout checking on GCS side
```

**6. MAVLink Monitor API:**
```python
# MAIN BRANCH:
self.mavlink_monitor.start_sniffing(port=MAVLINK_SNIFF_PORT)
mavlink_metrics = self.mavlink_monitor.stop()

# WORKING BRANCH:
self.mavlink_monitor.start()
self.mavlink_monitor.reset()
mavlink_metrics = self.mavlink_monitor.stop()
```

### Root Cause Analysis:
Main branch's GCS benchmark server tries to:
1. Collect GCS system metrics (unnecessary per policy)
2. Run a full MetricsAggregator (redundant with drone-side)
3. Wait for handshake confirmation (creates race conditions)
4. Manage complex PYTHONPATH (breaks on path issues)

Working branch **eliminates all non-essential complexity**.

### Recommendation:
**MUST BACKPORT** the simplified GcsBenchmarkServer.

---

## 5. CRITICAL FILE: `sscheduler/sdrone_bench.py`

### Key Differences

**1. MAVProxy Flags:**
```python
# MAIN BRANCH (Broken lifecycle):
cmd = [
    python_exe, "-m", "MAVProxy.mavproxy",
    f"--master={mav_master}",
    f"--out={out_proxy}",
    f"--out={out_sniff}",
    # "--nowait",  # REMOVED: Bind lifecycle to parent
    # "--daemon",  # REMOVED: Bind lifecycle to parent
]

# WORKING BRANCH (Proper daemon mode):
cmd = [
    python_exe, "-m", "MAVProxy.mavproxy",
    f"--master={mav_master}",
    f"--out={out_proxy}",
    f"--out={out_sniff}",
    "--nowait",
    "--daemon",
]
```

**2. Proxy Start (Same PYTHONPATH issue):**
```python
# MAIN BRANCH:
env = os.environ.copy()
project_root = str(Path(__file__).parent.parent.absolute())
# ... PYTHONPATH manipulation ...
self.managed_proc = ManagedProcess(..., env=env)

# WORKING BRANCH:
self.managed_proc = ManagedProcess(..., stderr=subprocess.STDOUT)
```

**3. Cleanup Aggressiveness:**
```python
# MAIN BRANCH:
cleanup_environment(aggressive=True)  # Kills everything

# WORKING BRANCH:
cleanup_environment(aggressive=False)  # Light cleanup only
```

**4. GCS Metrics Collection:**
```python
# MAIN BRANCH:
gcs_info: Dict[str, Any] = {}
try:
    info_resp = send_gcs_command("get_info")
    if info_resp.get("status") == "ok":
        gcs_info = info_resp
except Exception:
    gcs_info = {}
# ... later ...
if gcs_info:
    resp = dict(resp)
    resp["gcs_info"] = gcs_info

# WORKING BRANCH:
# REMOVED - gcs_info collection eliminated
```

### Root Cause Analysis:

**MAVProxy `--daemon --nowait` is CRITICAL:**
- Without `--daemon`: MAVProxy blocks, preventing proper lifecycle
- Without `--nowait`: MAVProxy waits for connection indefinitely
- Main branch comments suggest removal was intentional but WRONG

**Aggressive cleanup BREAKS things:**
- `aggressive=True` kills ALL python processes matching patterns
- Can kill the proxy/benchmark itself during restart

### Recommendation:
**MUST BACKPORT** the `--daemon --nowait` flags and `aggressive=False`.

---

## 6. OQS Import Patterns

### Status: **IDENTICAL** between branches

Both branches use the same fallback pattern in `core/handshake.py`:
```python
try:
    from oqs.oqs import KeyEncapsulation, Signature
except (ImportError, ModuleNotFoundError):
    try:
        from oqs import KeyEncapsulation, Signature
    except (ImportError, ModuleNotFoundError):
        try:
            import oqs
            KeyEncapsulation = oqs.KeyEncapsulation
            Signature = oqs.Signature
        except (ImportError, ModuleNotFoundError, AttributeError):
            pass
```

### Not a Root Cause:
OQS imports are NOT causing the main branch failure - they're identical.

---

## 7. Port Configuration

Both branches use the same ports:
- GCS Control: TCP 48080
- Plaintext TX: UDP 47003
- Plaintext RX: UDP 47004
- MAVLink Sniff: UDP 47005
- MAVLink Master: UDP 14550
- MAVLink Listen: UDP 14552

### Not a Root Cause:
Port configuration is identical.

---

## 8. IP Address Handling

The IP addresses are configuration-driven from `core/config.py`:
- `_GCS_HOST_LAN = "192.168.0.104"` (working branch, updated by 302386e)
- `_DRONE_HOST_LAN = "192.168.0.103"` (working branch, updated by 94749ec)

Main branch may have different values, but this is **trivially fixable** via config.

---

## Summary: Root Causes

| Priority | Root Cause | Files Affected | Fix |
|----------|-----------|----------------|-----|
| **P0** | `Optional[T] = None` schema defaults | metrics_schema.py | Change to `T = default` |
| **P0** | Missing `--daemon --nowait` MAVProxy flags | sdrone_bench.py | Add flags back |
| **P0** | PYTHONPATH manipulation in subprocess | sgcs_bench.py, sdrone_bench.py | Remove env manipulation |
| **P1** | `aggressive=True` cleanup | sdrone_bench.py | Change to `aggressive=False` |
| **P1** | GcsSystemMetricsCollector complexity | sgcs_bench.py | Remove class entirely |
| **P1** | MetricsAggregator on GCS side | sgcs_bench.py | Remove GCS-side aggregator |
| **P1** | Handshake timeout blocking | sgcs_bench.py | Remove `_wait_for_handshake_ok()` |
| **P2** | Null-checking arithmetic in aggregator | metrics_aggregator.py | Simplify to direct arithmetic |
| **P2** | `_mark_metric_status()` tracking | metrics_aggregator.py | Remove status tracking |
| **P2** | `run_proxy.py` entry point | core/run_proxy.py | Delete file |

---

## Recommended Backport Order

1. **Schema defaults** - Change all `Optional[T] = None` to `T = default_value`
2. **MAVProxy flags** - Add `--daemon --nowait` back
3. **Remove PYTHONPATH manipulation** - Let Python find modules normally
4. **Set `aggressive=False`** - Don't kill running processes
5. **Simplify GCS benchmark server** - Remove MetricsAggregator, SystemCollector
6. **Delete `run_proxy.py`** - Not needed
7. **Simplify metrics_aggregator.py** - Remove null-checking complexity

---

## Conclusion

The working branch succeeds because it follows the **"Policy Realignment"** principle (commit 6fe052d):
> GCS is a non-constrained observer; only drone-side resources influence policy decisions.

By removing unnecessary GCS-side metrics collection, simplifying MAVLink monitoring, and using safe defaults throughout, the working branch eliminates multiple failure modes that plague the main branch.

The main branch's approach of "collect everything, check for null everywhere" creates a fragile system where any missing component cascades into failures.
