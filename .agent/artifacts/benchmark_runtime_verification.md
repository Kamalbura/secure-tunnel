# Benchmark Runtime Verification

> Phase 0.7 • Generated: 2026-01-18
> Status: READY FOR SSH VERIFICATION

---

## Verification Commands

### 1. Verify Power Monitor Fix

```bash
ssh sshdev@100.101.93.23 "cd ~/secure-tunnel && \
  source ~/cenv/bin/activate && \
  python -c '
from sscheduler.sdrone_bench import DronePowerMonitor
from pathlib import Path
import time

m = DronePowerMonitor(Path(\"/tmp\"))
print(f\"Monitor available: {m.available}\")
print(f\"Sensor type: {m.sensor_type}\")

m.start_sampling()
time.sleep(1.0)
samples = m.stop_sampling()

print(f\"Samples collected: {len(samples)}\")
print(f\"Effective rate: {len(samples)/1.0:.0f} Hz\")
if samples:
    print(f\"First sample: {samples[0]}\")
'"
```

**Expected**: ~1000 samples in 1 second, sensor_type = "ina219"

### 2. Verify GCS Server Starts

```powershell
# On GCS (Windows)
cd C:\Users\burak\ptojects\secure-tunnel
conda activate oqs-dev
python -m sscheduler.sgcs_bench --help
```

### 3. Verify Drone Client Starts

```bash
ssh sshdev@100.101.93.23 "cd ~/secure-tunnel && \
  source ~/cenv/bin/activate && \
  python -m sscheduler.sdrone_bench --help"
```

---

## Integration Test (Manual)

1. Start GCS server:
   ```powershell
   python -m sscheduler.sgcs_bench
   ```

2. Start Drone client:
   ```bash
   ssh sshdev@100.101.93.23 "cd ~/secure-tunnel && \
     source ~/cenv/bin/activate && \
     python -m sscheduler.sdrone_bench --max-suites 1"
   ```

3. Verify output:
   - Check `logs/benchmarks/{run_id}/benchmark_{run_id}.jsonl`
   - Confirm power metrics are populated
   - Confirm sample_hz ≈ 1000

---

## Expected Results After Fix

| Metric | Before | After |
|--------|--------|-------|
| `power_avg_w` | 0 | > 0 |
| `power_peak_w` | 0 | > 0 |
| `energy_total_j` | 0 | > 0 |
| `sample_hz` | 0 | ~1000 |
| Samples per 10s | 0 | ~10,000 |
