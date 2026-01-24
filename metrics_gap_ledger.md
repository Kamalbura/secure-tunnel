# Metrics Gap Ledger (Phase 2)

Date: 2026-01-24

Buckets:
A) REAL & CORRECT → keep
B) REAL BUT CUMULATIVE → fix reset logic
C) DERIVED BUT VALID → label clearly
D) SYNTHETIC → isolate + label
E) SCHEMA-ONLY / NOT COLLECTED → remove
F) COLLECTABLE BUT MISSING → implement

## Actions Completed

### B) REAL BUT CUMULATIVE → Fix Reset Logic
- MAVLink per-suite counters
  - Change: Added `reset()` and invoked on `start_sniffing()`
  - File: core/mavlink_collector.py

### C) DERIVED BUT VALID → Label Clearly
- Throughput, power, energy, CPU average/peak
  - Change: Dashboard now fetches server-side aggregates only; client no longer computes summaries.
  - Files: dashboard/frontend/src/pages/Overview.tsx, dashboard/frontend/src/pages/ComparisonView.tsx, dashboard/frontend/src/pages/BucketComparison.tsx

### E) SCHEMA-ONLY / NOT COLLECTED → Remove
Removed from canonical schema + backend + frontend:
- Latency/Jitter category (no runtime source)
- Handshake RTT (no measurement)
- HKDF extract/expand timing (not recorded)
- GCS system resources (policy realignment)
- GCS MAVProxy deprecated fields
- Rekey blackout/interval fields not present (pruned if not collected)
- Misc. schema-only fields (tier/order/aead_mode/parameter_set)

Files:
- core/metrics_schema.py
- dashboard/backend/models.py
- dashboard/backend/schemas.py
- dashboard/frontend/src/types/metrics.ts

### F) COLLECTABLE BUT MISSING → Implement
- Power sensor voltage/current averages
  - Change: Compute in PowerCollector.get_energy_stats and populate in MetricsAggregator.finalize_suite
  - Files: core/metrics_collectors.py, core/metrics_aggregator.py

### Ingestion & Dashboard Truth Alignment
- Fix comprehensive ingestion field mapping and required defaults
  - File: dashboard/backend/ingest.py
- Remove client-side derived metrics; use server aggregation endpoints
  - File: dashboard/frontend/src/pages/Overview.tsx
- Show missing values as “NOT AVAILABLE”
  - File: dashboard/frontend/src/pages/SuiteDetail.tsx

## Remaining / Not Applicable
- D) SYNTHETIC: No synthetic metrics remain in canonical schema.
- A) REAL & CORRECT: All remaining fields are in metrics_truth_audit.md.
