# Observability Boundary Report

**Phase:** X - Forensic Reality Check
**Date:** 2026-01-19
**Evidence Type:** Classification of Observable vs Non-Observable

## 1. Observability Classification

| Finding | Classification | Evidence Type |
|:---|:---:|:---|
| MAVProxy Console Output (GCS) | **HUMAN-ONLY** | GUI window visible to operator. |
| MAVProxy Map (GCS) | **HUMAN-ONLY** | GUI window visible to operator. |
| MAVLink Packet Flow | **AGENT-VERIFIED** | `pymavlink` counters in JSONL. |
| INA219 Power Readings | **AGENT-VERIFIED** | `power_energy` block in JSONL. |
| Pixhawk FC Telemetry | **AGENT-VERIFIED** | `fc_telemetry` block in JSONL. |
| Drone CPU/Temp | **AGENT-VERIFIED** | `system_drone` block in JSONL. |
| GCS CPU/Mem | **UNOBSERVABLE** | Explicitly disabled (Policy). |
| Crypto Primitive Timings | **UNOBSERVABLE** | C-proxy instrumentation gap. |
| Handshake Success/Fail | **AGENT-VERIFIED** | `handshake.handshake_success` in JSONL. |
| Proxy Subprocess Alive | **AGENT-VERIFIED** | `ManagedProcess.is_running()` in code. |
| JSONL File Existence | **AGENT-VERIFIED** | `ls` / `find` commands. |
| Log File Timestamps | **AGENT-VERIFIED** | `stat` / `ls -l` commands. |

## 2. Visibility Separation

### AGENT-VERIFIED (Programmatically Observable)
*   JSONL field values
*   Process exit codes
*   File existence and modification times
*   Port binding (`netstat`, `ss`)
*   Thread state (via `ps`, `lsof`)

### HUMAN-ONLY (Requires Physical Observation)
*   MAVProxy GUI map rendering
*   MAVProxy console text output
*   Physical LED indicators on Pixhawk/INA219
*   Screen refresh and visual confirmation

### UNOBSERVABLE (No Signal Exists)
*   Crypto primitive sub-millisecond timings (Gap)
*   GCS system resource consumption (Disabled)
*   Rekey blackout duration (Not triggered in 10s runs)

## 3. Boundary Enforcement

| Action | Allowed? | Justification |
|:---|:---:|:---|
| Claim "MAVProxy GUI shows X" | ❌ NO | Agent cannot see GUI. |
| Claim "JSONL contains X" | ✅ YES | Agent can read file. |
| Claim "Power reading is X" | ✅ YES | JSONL has hardware value. |
| Claim "Crypto took X ms" | ❌ NO | Value is `-1` (Gap). |
