# Secure-Tunnel forensic wiring (evidence-linked)

This document is a **code-only wiring map** of the benchmark → metrics → dashboard pipeline. Every statement below is backed by a concrete code reference.

## 1) True execution entrypoints ("what can actually be run")

### Scheduler / benchmark controllers
- Drone benchmark scheduler CLI: [sscheduler/sdrone_bench.py](sscheduler/sdrone_bench.py#L713-L756)
- GCS benchmark server CLI: [sscheduler/sgcs_bench.py](sscheduler/sgcs_bench.py#L857-L915)

### Other runnable benchmark entrypoints (non-sscheduler)
- Standalone metrics benchmark: [run_metrics_benchmark.py](run_metrics_benchmark.py#L51-L51) and [run_metrics_benchmark.py](run_metrics_benchmark.py#L151-L151)
- Full benchmark runner (bench/): MetricsAggregator wiring at [bench/run_full_benchmark.py](bench/run_full_benchmark.py#L377) and [bench/run_full_benchmark.py](bench/run_full_benchmark.py#L549)

## 2) Producer-side pipeline (scheduler → proxy/handshake → metrics aggregator → JSON output)

### 2.1 Proxies are launched as modules
- Drone launches proxy via `python -m core.run_proxy drone ... --status-file logs/drone_status.json`: [sscheduler/sdrone_bench.py](sscheduler/sdrone_bench.py#L150-L154)
- GCS launches proxy via `python -m core.run_proxy gcs ... --status-file logs/gcs_status.json`: [sscheduler/sgcs_bench.py](sscheduler/sgcs_bench.py#L511-L515)

### 2.2 Handshake metrics are produced in the proxy and exported via status payload
- Proxy imports and calls the handshake implementations:
  - `server_gcs_handshake(...)`: call site [core/async_proxy.py](core/async_proxy.py#L508) and definition [core/handshake.py](core/handshake.py#L428)
  - `client_drone_handshake(...)`: call site [core/async_proxy.py](core/async_proxy.py#L560) and definition [core/handshake.py](core/handshake.py#L538)
- Proxy supports `--status-file` and writes a status payload: [core/async_proxy.py](core/async_proxy.py#L794-L820)
- If `handshake_metrics` exists, it is placed in the status payload: [core/async_proxy.py](core/async_proxy.py#L908-L909)
- Proxy also stores `handshake_metrics` in counters: [core/async_proxy.py](core/async_proxy.py#L919)

### 2.3 Drone scheduler consumes the proxy status file to record handshake + primitives
- Drone scheduler reads `logs/drone_status.json` and extracts `handshake_metrics` (including nested `counters.handshake_metrics` fallback): [sscheduler/sdrone_bench.py](sscheduler/sdrone_bench.py#L201-L219)
- Drone scheduler records handshake timeline and cryptographic primitive breakdown into the aggregator:
  - `record_handshake_start()`: [sscheduler/sdrone_bench.py](sscheduler/sdrone_bench.py#L464)
  - `record_handshake_end(success=True)` and `record_crypto_primitives(metrics)`: [sscheduler/sdrone_bench.py](sscheduler/sdrone_bench.py#L512-L513)
  - `record_handshake_end(success=False, failure_reason="handshake_timeout")`: [sscheduler/sdrone_bench.py](sscheduler/sdrone_bench.py#L527)

### 2.4 Drone scheduler consumes proxy counters to record data-plane metrics
- Drone scheduler reads counters from `logs/drone_status.json` and passes them to the aggregator: [sscheduler/sdrone_bench.py](sscheduler/sdrone_bench.py#L540-L556)

### 2.5 MetricsAggregator is the consolidation point
- Key API surface:
  - `_mark_metric_status(...)`: [core/metrics_aggregator.py](core/metrics_aggregator.py#L133)
  - `start_suite(...)`: [core/metrics_aggregator.py](core/metrics_aggregator.py#L173)
  - `record_data_plane_metrics(...)`: [core/metrics_aggregator.py](core/metrics_aggregator.py#L417)
  - `finalize_suite(...)`: [core/metrics_aggregator.py](core/metrics_aggregator.py#L569)
- The aggregator saves suite JSON via `_save_metrics(...)`: [core/metrics_aggregator.py](core/metrics_aggregator.py#L1112-L1122)

### 2.6 Output directory wiring (important for dashboard ingest)
- Scheduler-run comprehensive metrics are written to `logs/benchmarks/comprehensive`:
  - Drone side: [sscheduler/sdrone_bench.py](sscheduler/sdrone_bench.py#L308-L310)
  - GCS side: [sscheduler/sgcs_bench.py](sscheduler/sgcs_bench.py#L581-L583)
- If `MetricsAggregator` is constructed with no explicit output_dir, it defaults to `logs/comprehensive_metrics`: [core/metrics_aggregator.py](core/metrics_aggregator.py#L75-L90)

## 3) Dashboard ingest (JSON files → in-memory store)

### 3.1 Ingest expects `logs/benchmarks/comprehensive/*.json`
- Base directories: [dashboard/backend/ingest.py](dashboard/backend/ingest.py#L15-L16)
- Load comprehensive suites from JSON: [dashboard/backend/ingest.py](dashboard/backend/ingest.py#L226-L235) and glob loop [dashboard/backend/ingest.py](dashboard/backend/ingest.py#L228)

### 3.2 Fallback ingest: JSONL minimal suites
- JSONL scan: [dashboard/backend/ingest.py](dashboard/backend/ingest.py#L250-L251)
- Minimal suite builder + "missing_comprehensive_metrics" reason: [dashboard/backend/ingest.py](dashboard/backend/ingest.py#L127-L159)

### 3.3 Store singleton is accessed via `get_store()`
- Store acquisition in API code paths is via `get_store()`: [dashboard/backend/main.py](dashboard/backend/main.py#L36-L46) and [dashboard/backend/routes/suites.py](dashboard/backend/routes/suites.py#L35-L49)

## 4) Dashboard backend API (two competing implementations)

### 4.1 `dashboard/backend/main.py` exposes only runs endpoints
- `GET /api/runs`: [dashboard/backend/main.py](dashboard/backend/main.py#L36-L40)
- `GET /api/runs/{run_id}/suites`: [dashboard/backend/main.py](dashboard/backend/main.py#L42-L48)

### 4.2 `dashboard/backend/routes/suites.py` defines the endpoints the frontend actually calls
- Router creation: [dashboard/backend/routes/suites.py](dashboard/backend/routes/suites.py#L34)
- Health + suites + suite detail + compare + aggregation + buckets + schema:
  - `/api/health`: [dashboard/backend/routes/suites.py](dashboard/backend/routes/suites.py#L41-L57)
  - `/api/suites`: [dashboard/backend/routes/suites.py](dashboard/backend/routes/suites.py#L75-L102)
  - `/api/suite/{suite_key}`: [dashboard/backend/routes/suites.py](dashboard/backend/routes/suites.py#L129-L157)
  - `/api/aggregate/kem-family`: [dashboard/backend/routes/suites.py](dashboard/backend/routes/suites.py#L216-L266)
  - `/api/metrics/schema`: [dashboard/backend/routes/suites.py](dashboard/backend/routes/suites.py#L287-L290)
  - `/api/buckets`: [dashboard/backend/routes/suites.py](dashboard/backend/routes/suites.py#L323-L460)

### 4.3 README claims the full endpoint set, but the documented uvicorn command points at `main:app`
- Quick start backend command: [dashboard/README.md](dashboard/README.md#L45-L55)
- Endpoint list includes `/api/suites`, `/api/health`, `/api/aggregate/...`, etc: [dashboard/README.md](dashboard/README.md#L75-L85)

## 5) Frontend consumers (what is actually visualized)

### 5.1 Frontend types claim to mirror the canonical schema
- Comment: [dashboard/frontend/src/types/metrics.ts](dashboard/frontend/src/types/metrics.ts#L4)
- `ComprehensiveSuiteMetrics` TS interface: [dashboard/frontend/src/types/metrics.ts](dashboard/frontend/src/types/metrics.ts#L321)

### 5.2 Store wiring (API base)
- Store uses `API_BASE = '/api'` and calls `/api/suites`, `/api/runs`, `/api/suite/...`: [dashboard/frontend/src/state/store.ts](dashboard/frontend/src/state/store.ts#L12-L15) and [dashboard/frontend/src/state/store.ts](dashboard/frontend/src/state/store.ts#L66-L112)

### 5.3 Overview page
- Calls `/api/health` and `/api/aggregate/kem-family`: [dashboard/frontend/src/pages/Overview.tsx](dashboard/frontend/src/pages/Overview.tsx#L25-L33)
- Renders bars keyed by flattened aggregation keys:
  - `handshake_handshake_total_duration_ms_mean`: [dashboard/frontend/src/pages/Overview.tsx](dashboard/frontend/src/pages/Overview.tsx#L97)
  - `power_energy_power_avg_w_mean`: [dashboard/frontend/src/pages/Overview.tsx](dashboard/frontend/src/pages/Overview.tsx#L120)

### 5.4 Suite Explorer (summary fields only)
- Shows `handshake_total_duration_ms`, `power_avg_w`, `energy_total_j`: [dashboard/frontend/src/pages/SuiteExplorer.tsx](dashboard/frontend/src/pages/SuiteExplorer.tsx#L157-L168)

### 5.5 Suite Detail (renders these schema categories)
- Uses `validation.metric_status` map: [dashboard/frontend/src/pages/SuiteDetail.tsx](dashboard/frontend/src/pages/SuiteDetail.tsx#L84)
- Renders cards for:
  - A: [dashboard/frontend/src/pages/SuiteDetail.tsx](dashboard/frontend/src/pages/SuiteDetail.tsx#L102-L110)
  - B: [dashboard/frontend/src/pages/SuiteDetail.tsx](dashboard/frontend/src/pages/SuiteDetail.tsx#L114-L122)
  - D: [dashboard/frontend/src/pages/SuiteDetail.tsx](dashboard/frontend/src/pages/SuiteDetail.tsx#L126-L139)
  - M: [dashboard/frontend/src/pages/SuiteDetail.tsx](dashboard/frontend/src/pages/SuiteDetail.tsx#L144-L165)
  - G: [dashboard/frontend/src/pages/SuiteDetail.tsx](dashboard/frontend/src/pages/SuiteDetail.tsx#L170-L190)
  - H: [dashboard/frontend/src/pages/SuiteDetail.tsx](dashboard/frontend/src/pages/SuiteDetail.tsx#L196-L221)
  - K: [dashboard/frontend/src/pages/SuiteDetail.tsx](dashboard/frontend/src/pages/SuiteDetail.tsx#L226-L252)
  - N: [dashboard/frontend/src/pages/SuiteDetail.tsx](dashboard/frontend/src/pages/SuiteDetail.tsx#L257-L274)
  - O: [dashboard/frontend/src/pages/SuiteDetail.tsx](dashboard/frontend/src/pages/SuiteDetail.tsx#L279-L296)
  - P: [dashboard/frontend/src/pages/SuiteDetail.tsx](dashboard/frontend/src/pages/SuiteDetail.tsx#L301-L334)
  - R: [dashboard/frontend/src/pages/SuiteDetail.tsx](dashboard/frontend/src/pages/SuiteDetail.tsx#L339-L340)

### 5.6 Comparison View
- Compares handshake duration + power + energy + drone CPU avg: [dashboard/frontend/src/pages/ComparisonView.tsx](dashboard/frontend/src/pages/ComparisonView.tsx#L23-L44)

### 5.7 Power Analysis
- Uses summary fields `power_avg_w`, `energy_total_j`, `handshake_total_duration_ms`: [dashboard/frontend/src/pages/PowerAnalysis.tsx](dashboard/frontend/src/pages/PowerAnalysis.tsx#L38-L41)

### 5.8 Bucket Comparison
- Fetches buckets from a hard-coded origin URL (not `API_BASE`): [dashboard/frontend/src/pages/BucketComparison.tsx](dashboard/frontend/src/pages/BucketComparison.tsx#L51)

### 5.9 Integrity Monitor
- Operates on suite summary metadata (not detailed MAVLink integrity fields): [dashboard/frontend/src/pages/IntegrityMonitor.tsx](dashboard/frontend/src/pages/IntegrityMonitor.tsx#L34-L60)

## 6) KPI trace examples (root → leaf)

### KPI: Handshake total duration (ms)
- Proxy measures handshake and emits metrics into status payload: [core/async_proxy.py](core/async_proxy.py#L908-L909)
- Drone scheduler reads status JSON and passes handshake metrics into aggregator: [sscheduler/sdrone_bench.py](sscheduler/sdrone_bench.py#L201-L219) and [sscheduler/sdrone_bench.py](sscheduler/sdrone_bench.py#L512-L513)
- Dashboard aggregation endpoint groups by KEM family and produces flattened key `handshake_handshake_total_duration_ms_mean`: [dashboard/backend/routes/suites.py](dashboard/backend/routes/suites.py#L216-L266)
- Overview uses that flattened key in the chart: [dashboard/frontend/src/pages/Overview.tsx](dashboard/frontend/src/pages/Overview.tsx#L97)

### KPI: Power average (W)
- Comprehensive suite JSON is loaded from `logs/benchmarks/comprehensive/*.json`: [dashboard/backend/ingest.py](dashboard/backend/ingest.py#L226-L235)
- Suite Explorer displays `power_avg_w` (summary): [dashboard/frontend/src/pages/SuiteExplorer.tsx](dashboard/frontend/src/pages/SuiteExplorer.tsx#L162-L163)
- Suite Detail displays `power_energy.power_avg_w` (full): [dashboard/frontend/src/pages/SuiteDetail.tsx](dashboard/frontend/src/pages/SuiteDetail.tsx#L310)
- Overview uses aggregated key `power_energy_power_avg_w_mean`: [dashboard/frontend/src/pages/Overview.tsx](dashboard/frontend/src/pages/Overview.tsx#L120)

---

If you want, I can extend this file with:
- per-field schema population mapping (A–R) from [core/metrics_aggregator.py](core/metrics_aggregator.py) into UI presence.
- a "dead code" list (backend endpoints defined vs actually mounted) and the minimal patch to make the dashboard backend serve what the frontend calls.
