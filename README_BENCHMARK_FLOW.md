# Benchmark System Overview (Code-Derived)

This file is derived strictly from implemented code. No documentation or comments are treated as authoritative.

## Scope
- Focus: end-to-end benchmark flow and core proxy interaction.
- Primary entry points:
  - sscheduler/sdrone_bench.py
  - sscheduler/sgcs_bench.py
  - core/run_proxy.py
  - core/async_proxy.py
  - core/handshake.py

## High-Level Flow (VERIFIED)
1) GCS benchmark server starts and listens for TCP JSON commands.
   - It launches MAVProxy for GCS and a MAVLink validation collector.
   - It starts/stops the GCS proxy per-suite.
2) Drone benchmark controller starts and waits for GCS control server.
   - It launches MAVProxy on the drone and starts the drone proxy per-suite.
3) For each suite:
   - Drone commands GCS to start the GCS proxy.
   - Drone starts its local proxy.
   - Drone waits for handshake metrics from the proxy status file.
   - Drone holds the suite for the configured interval.
   - Drone requests GCS to stop the suite and return validation metrics.
   - Drone logs local and GCS metrics to JSONL files.
4) The core proxy encrypts/decrypts UDP between plaintext app ports and encrypted peer ports.
   - MAVProxy is expected to read/write plaintext UDP ports on each side.

## End-to-End Encryption Boundary (VERIFIED)
- The core proxy bridges plaintext UDP sockets to encrypted UDP sockets.
- The handshake performs PQC KEM + signature authentication and derives transport keys.
- AEAD framing is applied to all encrypted packets; plaintext UDP stays local to each side.

## MAVProxy Use (VERIFIED)
- Drone benchmark starts MAVProxy using Python module invocation and forwards to the proxy plaintext TX port.
- GCS benchmark starts MAVProxy with a UDP master bound to the proxy plaintext RX port.

## Clock Synchronization (VERIFIED)
- Drone benchmark sends chronos_sync to GCS control server and computes offset.
- The offset is used to seed the benchmark policy start time and evaluation time.

## Cleanup / Process Lifecycle (VERIFIED)
- Drone benchmark registers an atexit cleanup to stop proxy/MAVProxy and kill stale processes.
- GCS benchmark registers an atexit cleanup to stop the server and MAVProxy.

## UNVERIFIED
- MAVProxy configuration outside these scripts (external launch args, routing) is not validated here.
- Any external scripts or orchestration not present in these entry points are not covered.
