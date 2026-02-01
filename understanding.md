# Codebase Understanding (High-Level)

## Purpose
Secure-Tunnel is a research-grade, post-quantum secure “bump-in-the-wire” tunnel for MAVLink traffic between a Ground Control Station (GCS) and a drone. It authenticates a TCP handshake using PQC KEM + signatures, derives session keys, and then encrypts MAVLink UDP traffic with AEAD while enforcing replay protection and strict peer checks.

## Core (crypto + proxy engine)
- **Configuration and runtime flags**: Centralized in core/config.py (ports, host IPs, replay window, feature flags, rekey timeouts).
- **Suite registry**: core/suites.py defines the valid {KEM × AEAD × SIG} matrix, alias resolution, NIST-level constraints, and runtime pruning.
- **Handshake protocol**: core/handshake.py builds the server hello, verifies signatures, runs KEM encaps/decaps, derives transport keys, and records metrics.
- **Proxy data plane**: core/async_proxy.py is the selector-based UDP bridge (plaintext ↔ encrypted) with AEAD framing, replay window checks, drop classification, and control-plane handling.
- **CLI entrypoint**: core/run_proxy.py runs the proxy in GCS or drone role, loads keys, starts the handshake, and persists counters/metrics.
- **Rekey control-plane**: core/policy_engine.py implements the in-band two‑phase commit for rekey negotiation.

## sscheduler (drone-driven orchestration)
- **GCS follower**: sscheduler/sgcs.py exposes a TCP control server. The drone instructs the GCS to start/stop the proxy and traffic generation.
- **Drone controller**: sscheduler/sdrone.py selects suites, starts its proxy, triggers GCS actions, and validates data flow with a UDP echo server.
- **Policy logic**: sscheduler/policy.py contains telemetry-aware logic for upgrading/downgrading suites or requesting rekeys based on link/battery/thermal inputs.
- **Control security helpers**: sscheduler/control_security.py provides HMAC-based challenge/response utilities for control-plane hardening.

## Dashboard (forensic benchmark viewer)
- **Backend (FastAPI)**: dashboard/backend provides APIs for runs, suites, comparisons, filters, and schema metadata.
- **Ingestion**: dashboard/backend/ingest.py loads comprehensive JSON metrics, merges GCS JSONL logs, and marks scientific validity.
- **Schema + analysis**: dashboard/backend/models.py and analysis.py define the canonical metric schema and comparison/aggregation utilities.
- **Frontend (React)**: dashboard/frontend implements pages for overview, suite explorer, comparisons, power analysis, and integrity monitoring, backed by a Zustand store.

## End-to-End Flow (Summary)
1. Drone connects to GCS over TCP and verifies the signed server hello.
2. KEM encapsulation/decapsulation establishes shared secrets and session keys.
3. UDP data plane encrypts MAVLink payloads with AEAD and enforces replay protection.
4. Optional control-plane messages coordinate rekeying and suite rotation.
5. Benchmark outputs are ingested and visualized by the dashboard.
