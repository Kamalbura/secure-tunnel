# Benchmark Metric Schema

> [!NOTE]
> This document defines the canonical schema for benchmark JSONL files.

## Core Fields

| Field | Type | Unit | Description |
|-------|------|------|-------------|
| `timestamp` | ISO8601 | - | Event time |
| `suite` | string | - | Crypto suite identifier |
| `operation` | enum | - | `handshake`, `encrypt`, `decrypt`, `rekey` |
| `latency_ms` | float | ms | Operation latency |
| `throughput_bps` | float | bps | Bytes per second |
| `jitter_ms` | float | ms | Latency variance |

## Drone-Side Fields

| Field | Type | Unit | Description |
|-------|------|------|-------------|
| `power_mw` | float | mW | INA219 power reading |
| `voltage_v` | float | V | INA219 voltage |
| `current_ma` | float | mA | INA219 current |
| `cpu_percent` | float | % | CPU utilization |
| `temp_c` | float | °C | SoC temperature |

## GCS-Side Fields

| Field | Type | Unit | Description |
|-------|------|------|-------------|
| `gcs_latency_ms` | float | ms | GCS-measured latency |
| `packet_loss` | float | % | Packet loss rate |

## Rekey Fields

| Field | Type | Unit | Description |
|-------|------|------|-------------|
| `rekey_start_ts` | ISO8601 | - | Rekey start time |
| `rekey_end_ts` | ISO8601 | - | Rekey end time |
| `rekey_blackout_ms` | float | ms | Data blackout duration |
| `rekey_success` | bool | - | Completion status |

## Suite Identifiers

```
KYBER512_AES128
KYBER768_AES192
KYBER1024_AES256
MLKEM512_AES128
MLKEM768_AES192
MLKEM1024_AES256
CLASSIC_X25519_AES256
```
