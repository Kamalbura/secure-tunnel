# GCS Metric Pruning Decisions

> [!NOTE]
> This document records which GCS-side metrics were pruned and the rationale.

## Pruning Summary

GCS-side metrics serve **integrity validation only**. They do NOT drive policy decisions.

## Retained Metrics

| Metric | Purpose |
|--------|---------|
| `gcs_latency_ms` | Cross-validate drone latency |
| `packet_loss` | Verify data integrity |
| `connection_state` | Session continuity check |

## Pruned Metrics

| Metric | Reason |
|--------|--------|
| `gcs_cpu_percent` | Not relevant to drone-constrained policy |
| `gcs_memory_mb` | Not relevant to drone-constrained policy |
| `gcs_disk_io` | Not relevant to benchmark analysis |
| `gcs_network_queue` | Redundant with throughput |

## Rationale

Per **Rule #1** (Drone-side metrics drive policy):
- GCS hardware is not constrained
- GCS power is unlimited
- GCS thermal is not relevant
- Only drone-side constraints affect operational decisions

## Enforcement

GCS metrics should only appear in:
- Integrity validation reports
- Cross-correlation checks
- Debug logs

They MUST NOT appear in:
- Policy decisions
- Suite selection logic
- Rekey scheduling
