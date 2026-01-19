# Expectation vs Reality

> Phase 0.95 • Generated: 2026-01-19
> Status: ANALYSIS COMPLETE

---

## Pre-Run Expectations

| Component | Expectation | Verified |
|-----------|-------------|----------|
| Clock sync | <1s drift | ✅ |
| Drone headless | No MAVProxy GUI | ✅ |
| GCS GUI | `--map --console` | ✅ |
| Power @ 1000 Hz | iter_samples() | ✅ (code) |
| 10s per suite | time.monotonic() | ✅ (code) |
| JSONL output | Per-suite append | ✅ (code) |

---

## Potential Mismatches (Theoretical)

| Expectation | Risk | Mitigation |
|-------------|------|------------|
| 1000 Hz actual | Python GIL | Expect ~800-900 Hz |
| Latency <50ms | Network jitter | Average multiple samples |
| Zero packet loss | Suite switch | Accept <5% loss |
| Crypto timing | Proxy status file | May be zeros |

---

## Known Gaps

| Gap | Impact | Acceptable |
|-----|--------|------------|
| Rekey metrics | Not collected | ✅ Single-suite mode |
| GCS CPU | Not collected | ✅ Policy removed |
| Crypto primitives | Often zero | ⚠️ Post-hoc analysis |

---

## Post-Run Validation Required

1. Verify JSONL contains all 5 suites
2. Verify power samples > 10,000
3. Verify latency values are realistic (1-50ms)
4. Verify no handshake failures
5. Verify seq_gap_count is low

---

## Verdict

**Pre-flight checks PASSED.** Live execution will validate remaining items.
