# Partial Run: 5 Suites Report

> Phase 0.95 • Generated: 2026-01-19
> Status: PENDING EXECUTION

---

## Configuration

| Setting | Value |
|---------|-------|
| Suites to run | 5 |
| Time per suite | 10s |
| Total duration | ~60s (with handshakes) |
| Command | `python -m sscheduler.sdrone_bench --max-suites 5` |

---

## Expected Metrics Per Suite

| Metric | Source |
|--------|--------|
| handshake_total_ms | Proxy status |
| packets_sent/received | Echo server |
| latency_avg_ms | Embedded ts |
| power_avg_w | INA219 @ 1000Hz |
| cpu_usage_avg | psutil |
| seq_gap_count | MAVLink |

---

## Verification Checklist

After run, verify:
- [ ] JSONL file created
- [ ] 5 suite entries present
- [ ] Power samples > 0
- [ ] Latency values realistic
- [ ] No handshake failures

---

## Execution Command

### Drone
```bash
ssh dev@100.101.93.23 "cd ~/secure-tunnel && \
  source ~/cenv/bin/activate && \
  python -m sscheduler.sdrone_bench --max-suites 5"
```

### GCS
```powershell
conda activate oqs-dev && python -m sscheduler.sgcs_bench
```

---

## Verdict

**⏳ PENDING** — Awaiting user decision to execute.
