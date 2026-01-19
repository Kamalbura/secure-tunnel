# Phase 0: Codebase Understanding Report

> Generated: 2026-01-18T23:24
> Status: VERIFIED

---

## Executive Summary

The `secure-tunnel` project implements a **Post-Quantum Cryptographic (PQC) overlay network** connecting a Drone (Raspberry Pi 4) to a Ground Control Station (GCS, Windows). It provides:

1. **Authenticated Key Exchange** using liboqs KEM + Digital Signatures
2. **Encrypted Data Plane** using AEAD (AES-GCM, ChaCha20-Poly1305, Ascon)
3. **MAVLink Tunneling** for drone telemetry
4. **Suite Rotation** with configurable rekey intervals

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        DRONE (RPi4)                          │
├─────────────────────────────────────────────────────────────┤
│  sdrone_mav.py                                               │
│  ├── DroneScheduler (Policy: LinearLoop/Random)              │
│  ├── DroneProxyManager → core.run_proxy drone                │
│  ├── MAVProxy (--master=/dev/ttyACM0)                        │
│  ├── TelemetryListener (UDP)                                 │
│  └── GCS Control Client (TCP commands)                       │
│                                                              │
│  Power: INA219 @ I2C 0x40                                    │
└──────────────────────────┬──────────────────────────────────┘
                           │ TCP:46000 (Handshake)
                           │ UDP:46011/46012 (Encrypted)
                           │ TCP:48080 (Control)
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                         GCS (Windows)                        │
├─────────────────────────────────────────────────────────────┤
│  sgcs_mav.py                                                 │
│  ├── ControlServer (TCP listener, follows drone commands)    │
│  ├── GcsProxyManager → core.run_proxy gcs                    │
│  ├── TrafficGenerator (UDP blast @ target Mbps)              │
│  ├── MAVProxy                                                │
│  └── TelemetrySender (UDP fire-and-forget)                   │
└─────────────────────────────────────────────────────────────┘
```

---

## Control Model (REVERSED)

| Property | Value |
|----------|-------|
| Controller | **Drone** (sdrone_mav.py) |
| Follower | GCS (sgcs_mav.py) |
| Rationale | Drone decides suite order, timing, rekey |

### Command Flow

1. Drone → GCS: `start_proxy(suite=X)`
2. GCS starts proxy (TCP listener for handshake)
3. Drone starts proxy (TCP client, initiates handshake)
4. Drone → GCS: `start_traffic(duration=10)`
5. GCS generates UDP traffic
6. Drone echoes traffic (loop-back test)
7. Drone → GCS: `prepare_rekey` before suite rotation

---

## Core Module Classification

### Cryptography (`core/`)

| File | Lines | Purpose |
|------|-------|---------|
| `handshake.py` | 653 | KEM + Signature handshake protocol |
| `suites.py` | 850 | Suite registry (KEM×AEAD×SIG matrix) |
| `aead.py` | 466 | AEAD framing with replay protection |

### Data Plane (`core/`)

| File | Lines | Purpose |
|------|-------|---------|
| `async_proxy.py` | ~1500 | UDP proxy with encrypt/decrypt |
| `run_proxy.py` | 800 | Entry point for proxy subprocess |
| `control_tcp.py` | 300 | TCP handshake channel |

### Metrics (`core/`)

| File | Lines | Purpose |
|------|-------|---------|
| `metrics_schema.py` | 696 | 18 metric categories (A-R) |
| `metrics_collectors.py` | 600 | CPU, memory, latency collectors |
| `metrics_aggregator.py` | 700 | Aggregation and output |
| `power_monitor.py` | 998 | INA219 + RPi5 hwmon backends |

### Scheduling (`sscheduler/`)

| File | Lines | Purpose |
|------|-------|---------|
| `sdrone_mav.py` | 775 | Drone controller entry point |
| `sgcs_mav.py` | 754 | GCS follower entry point |
| `policy.py` | 300 | LinearLoop, Random, ManualOverride |
| `benchmark_policy.py` | 500 | Suite iteration for benchmarks |

---

## Suite Registry

### NIST Levels

| Level | Security Bits | Example Suites |
|-------|---------------|----------------|
| L1 | 128 | MLKEM512-AES-MLDSA44 |
| L3 | 192 | MLKEM768-AES-MLDSA65 |
| L5 | 256 | MLKEM1024-AES-MLDSA87 |

### AEAD Tokens

| Token | Algorithm | Status |
|-------|-----------|--------|
| `aesgcm` | AES-256-GCM | ✅ Active |
| `chacha20poly1305` | ChaCha20-Poly1305 | ✅ Active |
| `ascon128a` | Ascon-128a | ✅ Active (native C) |

### Default Suite

```python
DEFAULT_SUITE_ID = "cs-mlkem768-aesgcm-mldsa65"
```

---

## Handshake Protocol

```
Drone                                    GCS
  │                                       │
  │ ──── TCP connect ──────────────────→ │
  │                                       │
  │ ←── ServerHello (KEM pub, sig) ───── │
  │      metrics: keygen time             │
  │                                       │
  │ ──── ClientReply (KEM ciphertext) ─→ │
  │      metrics: encapsulation time      │
  │                                       │
  │ [Both derive transport keys via HKDF] │
  │                                       │
  │ ←──────── Encrypted UDP ──────────→  │
```

---

## Power Monitoring

### INA219 Configuration

| Parameter | Value |
|-----------|-------|
| I2C Bus | 1 |
| Address | 0x40 |
| Shunt Resistor | 0.1Ω |
| Sample Rate | 10-1100 Hz (profile-dependent) |

### Metrics Captured

- Voltage (V)
- Current (A)
- Power (W)
- Energy (J) cumulative
- CSV logging with timestamps

---

## Environment Verification Status

| Component | GCS | Drone |
|-----------|-----|-------|
| Python | 3.11.13 ✅ | 3.x ✅ |
| liboqs | conda oqs-dev ✅ | ~/cenv ✅ |
| MAVProxy | ✅ | ✅ → Pixhawk |
| INA219 | N/A | smbus2 ✅ |
| Network | LAN ✅ | LAN ✅ |

---

## Entry Point Commands

### GCS (Windows)

```bash
conda activate oqs-dev
python -m sscheduler.sgcs_mav
```

### Drone (via SSH)

```bash
ssh sshdev@100.101.93.23 "cd ~/secure-tunnel && source ~/cenv/bin/activate && python -m sscheduler.sdrone_mav"
```

---

## Ambiguities / Unknowns

| Item | Status | Notes |
|------|--------|-------|
| Exact venv Python version on drone | UNVERIFIED | Assumed 3.11.x |
| MAVProxy exact launch args | UNVERIFIED | Varies by config |
| Pixhawk serial device | VERIFIED | `/dev/ttyACM0` default |
| INA219 calibration values | VERIFIED | Standard 4096 cal |
