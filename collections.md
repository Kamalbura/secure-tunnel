# Scientific Metrics Collection Schema

## 1. Drone Metrics (Producer)
**Source**: `sscheduler/sdrone.py` (Sensor Fusion Loop)
**Transport**: UDP Payload (JSON) -> Tunnel -> GCS

### Power (INA219)
- `pwr.v`: Bus Voltage (V)
- `pwr.i`: Current (mA)
- `pwr.p`: Power (mW) [Derived]
- `pwr.e`: Energy (mJ) [Derived]

### Avionics (MAVLink)
- `mav.alt`: Relative Altitude (m)
- `mav.hdg`: Heading (deg)
- `mav.batt`: Battery Remaining (%)
- `mav.lat`: Latitude (int)
- `mav.lon`: Longitude (int)

### System
- `sys.cpu`: CPU Usage (%)
- `sys.temp`: CPU Temperature (C)
- `sys.ram`: Memory Usage (%)

### Crypto & Network
- `crypto.suite`: Current PQC Suite ID
- `sync.ts`: Synchronized Timestamp (Epoch Float)
- `sync.offset`: Calculated Clock Offset (s)

## 2. GCS Metrics (Consumer)
**Source**: `sscheduler/sgcs.py` (Chronos Listener)
**Storage**: `logs/chronos_full.jsonl`

### Validation Metrics
- `_gcs_rx_ts`: GCS Reception Timestamp (Local Monotonic/Epoch)
- `latency`: `_gcs_rx_ts - sync.ts` (One-Way Delay)
- `throughput`: Calculated derived from packet rate.

### Derived Analysis (Post-Process)
- **Voltage Drop vs Latency**: Correlation between `pwr.v` sag and `latency` spikes during re-keying.
- **Energy Cost per Suite**: Integrate `pwr.p` over `crypto.suite` duration.
