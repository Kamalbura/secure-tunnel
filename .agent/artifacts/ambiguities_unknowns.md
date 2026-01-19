# Phase 0: Ambiguities and Unknowns

> Generated: 2026-01-18T23:24
> Status: REQUIRES CLARIFICATION

---

## Verified Facts

These are confirmed from code analysis and user input:

| Fact | Source | Status |
|------|--------|--------|
| liboqs installed on both sides | User input | ✅ VERIFIED |
| INA219 @ 0x40 on I2C-1 | User input + code | ✅ VERIFIED |
| MAVProxy ↔ Pixhawk operational | User input | ✅ VERIFIED |
| Control model is reversed (Drone controls) | Code analysis | ✅ VERIFIED |
| Default suite: cs-mlkem768-aesgcm-mldsa65 | Code analysis | ✅ VERIFIED |
| TCP:46000 for handshake | Code analysis | ✅ VERIFIED |
| UDP:46011/46012 for data plane | Code analysis | ✅ VERIFIED |
| TCP:48080 for control commands | Code analysis | ✅ VERIFIED |

---

## Unverified / Ambiguous

| Item | Concern | Impact | Resolution |
|------|---------|--------|------------|
| Drone Python version | Assumed 3.11.x but not confirmed | Low | Run `python --version` via SSH |
| MAVProxy launch arguments | Varies by sdrone_mav args | Low | Check runtime logs |
| Network latency baseline | Not measured | Medium | Requires ping test |
| Clock sync mechanism | NTP assumed, not verified | Medium | Check clock_sync.py runtime |
| Pixhawk serial baud rate | Default assumed | Low | Check MAVProxy logs |
| INA219 shunt resistor | 0.1Ω assumed per code | Low | Physical verification |

---

## Open Questions

1. **What is the exact Python version on the Drone?**
   - Impact: Package compatibility
   - Resolution: `ssh sshdev@100.101.93.23 "python --version"`

2. **Is NTP synchronized between GCS and Drone?**
   - Impact: Latency measurement accuracy
   - Resolution: Check `clock_offset_ms` in benchmark output

3. **What is the baseline network latency on the LAN?**
   - Impact: Distinguishes crypto overhead from network
   - Resolution: `ping -c 10 100.101.93.23`

---

## Recommendations

1. **Before Phase A**: Run environment validation script
2. **Before Phase B**: Confirm all benchmark JSONL files are immutable
3. **Before Analysis**: Verify clock sync mechanism

---

## Notes

All conclusions in this document are traceable to:
- `[ARTIFACT: codebase_understanding.md]`
- `[ARTIFACT: execution_mental_model.md]`
- User-provided environment input
