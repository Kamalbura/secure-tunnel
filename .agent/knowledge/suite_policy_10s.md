# Deterministic 10-Second Suite Policy

> [!IMPORTANT]
> This policy is DETERMINISTIC. All values are fixed at benchmark time.

## Policy Summary

Each cryptographic suite runs for exactly **10 seconds** of stable operation before metrics are recorded. This ensures:

1. JIT warmup complete
2. TCP connection stabilized
3. Buffer queues filled
4. Thermal equilibrium (drone-side)

## Timing Parameters

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `WARMUP_DURATION` | 3s | JIT + connection stabilization |
| `MEASUREMENT_DURATION` | 10s | Statistical significance |
| `COOLDOWN_DURATION` | 2s | Queue drain |
| `TOTAL_SUITE_TIME` | 15s | Complete cycle |

## Iteration Policy

| Parameter | Value |
|-----------|-------|
| `ITERATIONS_PER_SUITE` | 100 |
| `DISCARD_FIRST_N` | 5 |
| `DISCARD_LAST_N` | 5 |
| `EFFECTIVE_SAMPLES` | 90 |

## Enforcement

Benchmarks that do not meet the 10s stability requirement are marked `INVALID` and excluded from analysis.

## Artifact Reference

- Source: `run_metrics_benchmark.py`
- Configuration: `settings.json:benchmark_duration`
