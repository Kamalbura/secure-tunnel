# Execution Plan

> Phase 1 • Generated: 2026-01-19
> Status: AUTHORITATIVE

---

## Execution Authority

| Agent | Role |
|-------|------|
| Benchmark Execution Authority (BEA) | Run execution |
| Execution Integrity Supervisor (EIS) | Monitor & certify |

---

## Pre-Conditions Met

| Phase | Status |
|-------|--------|
| Phase 0.5 | ✅ Benchmark coverage verified |
| Phase 0.6 | ✅ Power monitor bug found |
| Phase 0.7 | ✅ Power monitor bug **FIXED** |
| Phase 0.8 | ✅ Runtime verified |
| Phase 0.9 | ✅ Observability verified |
| Phase 0.95 | ✅ Pre-flight SAFE |

---

## Execution Parameters

| Parameter | Value |
|-----------|-------|
| Time per suite | 10 seconds |
| Power sampling | 1000 Hz |
| Clock sync | <1 second drift |
| JSONL output | `logs/benchmarks/{run_id}/` |

---

## Suite Order

Deterministic, sorted by:
1. NIST Level (L1 → L3 → L5)
2. KEM family
3. Signature family

---

## Run Modes

### Partial Run (5 suites)
```bash
# Drone
ssh dev@100.101.93.23 "cd ~/secure-tunnel && \
  source ~/cenv/bin/activate && \
  python -m sscheduler.sdrone_bench --max-suites 5"
```

### Full Run (all suites)
```bash
# Drone
ssh dev@100.101.93.23 "cd ~/secure-tunnel && \
  source ~/cenv/bin/activate && \
  python -m sscheduler.sdrone_bench"
```

---

## Stop Conditions

| Condition | Action |
|-----------|--------|
| Suite count reached | STOP |
| Handshake failure ×3 | ABORT |
| Power sampling < 500 Hz | ABORT |
| Clock drift > 5s | ABORT |

---

## Integrity Checks

EIS will verify:
- [ ] JSONL contains expected suite count
- [ ] Power samples > (suites × 10s × 800)
- [ ] Latency values realistic (1-100ms)
- [ ] No handshake failures
- [ ] Heartbeat continuity
