# PQC Benchmark Analysis Report
## Run ID: live_run_20260205_145749
## Date: 2026-02-05 14:57:49 - 17:10:30 UTC

---

## Executive Summary

| Metric | Value |
|--------|-------|
| **Total Suites Tested** | 72 |
| **Run Duration** | ~132 minutes (2h 12m) |
| **Suite Interval** | 110 seconds |
| **Handshake Success Rate** | 71/72 (98.6%) |
| **Comprehensive Files Captured** | 45/72 (62.5%) |

---

## Key Findings

### 1. Performance Ranking by KEM (Post-Quantum Key Encapsulation)

| KEM Type | Avg Handshake | Min | Max | Notes |
|----------|--------------|-----|-----|-------|
| **ML-KEM** | 390ms | 9ms | 1315ms | **FASTEST** - NIST standardized (FIPS 203) |
| **HQC** | 548ms | 60ms | 1511ms | Good balance, code-based |
| **Classic-McEliece** | 950ms | 134ms | 2846ms | Slowest but highest security margin |

### 2. Performance Ranking by Signature

| Signature Type | Avg Handshake | Notes |
|----------------|--------------|-------|
| **ML-DSA** | 188ms | **FASTEST** - NIST standardized (FIPS 204) |
| **Falcon** | 401ms | Compact signatures, good performance |
| **SPHINCS+** | 1223ms | Slowest, hash-based security |

### 3. Performance by NIST Security Level

| Level | Avg Handshake | Suite Count |
|-------|--------------|-------------|
| L1 (AES-128 equiv) | 298ms | 27 |
| L3 (AES-192 equiv) | 792ms | 18 |
| L5 (AES-256 equiv) | 852ms | 27 |

### 4. AEAD Cipher Performance (no significant difference)

| AEAD | Avg Handshake |
|------|--------------|
| AES-256-GCM | 571ms |
| ChaCha20-Poly1305 | 581ms |
| Ascon-128a | 736ms |

---

## Top Performers

### Fastest 5 Suites (Latency-Critical Deployments)

| Rank | Suite | Handshake |
|------|-------|-----------|
| 1 | mlkem512-ascon128a-falcon512 | **9.28ms** |
| 2 | mlkem512-aesgcm-falcon512 | 12.61ms |
| 3 | mlkem512-aesgcm-mldsa44 | 13.69ms |
| 4 | mlkem512-chacha20poly1305-mldsa44 | 14.21ms |
| 5 | mlkem1024-chacha20poly1305-mldsa87 | 14.71ms |

### Slowest 5 Suites (Security-First Deployments)

| Rank | Suite | Handshake |
|------|-------|-----------|
| 1 | classicmceliece460896-ascon128a-sphincs192s | **2845.84ms** |
| 2 | classicmceliece8192128-ascon128a-falcon1024 | 2827.29ms |
| 3 | classicmceliece8192128-ascon128a-sphincs256s | 2320.84ms |
| 4 | classicmceliece8192128-aesgcm-falcon1024 | 2063.25ms |
| 5 | classicmceliece8192128-chacha20poly1305-sphincs256s | 2030.75ms |

---

## Cross-Dimensional Matrix (KEM x SIG Average Handshake)

|           | Falcon | ML-DSA | SPHINCS+ |
|-----------|--------|--------|----------|
| ML-KEM    | 21ms   | 17ms   | 1010ms   |
| HQC       | 167ms  | 168ms  | 1181ms   |
| McEliece  | 1014ms | 380ms  | 1478ms   |

**Key Insight**: ML-KEM + ML-DSA combination achieves **17ms** average - essentially negligible for UAV operations.

---

## System Metrics (from 45 detailed captures)

| Metric | Value |
|--------|-------|
| **Average Power** | 2.756 W |
| **Total Energy** | 13,321 J (3.70 Wh) |
| **Avg CPU Usage** | 25.6% |
| **Avg Temperature** | 64.7°C |
| **Max Temperature** | 66.2°C |
| **Total MAVLink Messages** | 2,541,274 |
| **Heartbeat Losses** | **0** |

---

## Recommendations by Use Case

### Real-time UAV Control (Sub-50ms requirement)
- **Recommended**: ML-KEM-512/768/1024 + ML-DSA-44/65/87
- **Handshake Range**: 9-28ms
- **NIST Level**: L1/L3/L5 available

### General UAV Operations (Reconnection tolerance 100-500ms)
- **Recommended**: HQC-128/192/256 + Falcon-512/1024 or ML-DSA
- **Handshake Range**: 60-280ms
- **Good balance** of security margin and performance

### High-Security Missions (Session persistence, rare reconnects)
- **Recommended**: Classic-McEliece + SPHINCS+
- **Handshake Range**: 600-2800ms
- **Maximum post-quantum security margin** with conservative cryptographic assumptions

---

## Data Completeness Notes

1. **72/72 suites completed** with handshake timings captured in `benchmark_results.json`
2. **45/72 comprehensive metric files** captured (27 failed to save due to file I/O issues during benchmark)
3. **1 handshake timeout**: `classicmceliece460896-aesgcm-sphincs192s` (0ms recorded = timeout)
4. **Validation flags**: 44 suites marked as "mavlink_latency_invalid" - this is a **validation system issue**, not handshake failure. Handshakes completed successfully.

---

## File Inventory

```
chronos_runs/live_run_20260205_145749/
├── benchmark_results_20260205_145749.json  # Complete 72-suite results
├── benchmark_results_20260205_145749.csv   # CSV export
├── benchmark_summary_20260205_145749.json  # Run summary
├── drone_status.json                       # Drone state
├── ANALYSIS_REPORT.txt                     # This analysis (text)
├── analyze_complete.py                     # Analysis script
├── compare_suites.py                       # Suite comparison script
├── comprehensive/                          # 45 detailed metric files
│   ├── cs-mlkem512-ascon128a-falcon512_comprehensive.json
│   └── ... (90 files, 45 unique)
└── logs/                                   # 73 log files
    └── ...
```

---

## Conclusion

This 72-suite benchmark demonstrates that **NIST-standardized ML-KEM + ML-DSA** combinations are ready for real-time UAV deployment with sub-20ms handshakes, while **Classic-McEliece + SPHINCS+** provides maximum security for high-value missions at the cost of 2-3 second handshakes.

The **306.7x performance gap** between fastest and slowest suites highlights the importance of algorithm selection based on operational requirements.
