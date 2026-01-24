# Expectation vs Reality — Final Closure

Date: 2026-01-24

## Objective
Bridge gaps between canonical expectations, code reality, and dashboard visualization. Enforce a single source of truth: only runtime-collected metrics are allowed to appear.

## What is now provably true
- Canonical schema contains only runtime-backed fields.
- Per-suite metrics reset (MAVLink counters) enforced at collector start.
- Dashboard shows only real data; no client-side derived metrics.
- Aggregations are server-side and labeled as derived.
- Verification scripts enforce absence of schema-only fields and per-suite integrity.

## Removed (Not Collectable) Metrics
- Latency/Jitter category (no runtime source)
- Handshake RTT (no direct measurement)
- HKDF extract/expand timing (not instrumented)
- GCS system resource metrics (policy realignment)
- Deprecated GCS MAVProxy fields
- Schema-only fields (tier/order/parameter_set/aead_mode)

## Implemented or Corrected
- MAVLink counters reset per suite
- Power voltage/current averages computed from real samples
- GCS run-context populated via control plane

## Verification
- verify_metrics_output.py: required-field presence
- verify_metrics_integrity.py: forbidden fields + reset checks
- tools/verify_metrics_truth.py: audit classification checks

## Artifacts
- metrics_truth_audit.md
- metrics_gap_ledger.md

Status: CLOSED
