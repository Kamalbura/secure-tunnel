# Individual Benchmarks - Post-Quantum Cryptography

## Overview

This folder contains comprehensive benchmark results for post-quantum cryptographic algorithms
tested on Raspberry Pi 4 with INA219 power monitoring at 1kHz sampling rate.

## Folder Structure

```
individual_benchmarks/
├── raw_data/                    # Raw JSON benchmark measurements
│   ├── environment.json         # Test environment details
│   ├── raw/
│   │   ├── kem/                 # 27 KEM benchmark files (100 iterations each)
│   │   ├── sig/                 # 24 Signature benchmark files (100 iterations)
│   │   └── aead/                # 24 AEAD benchmark files (100 iterations)
│   └── 5iter_test/              # Quick validation run (5 iterations)
│
├── reports/                     # Generated PDF reports
│   ├── PQC_BENCHMARK_BOOK.pdf   # Comprehensive 6.2 MB benchmark book
│   └── BENCHMARK_REPORT.pdf     # Quick analysis report
│
├── visualizations/              # All generated plots (57 images)
│   ├── *_timing_dist.png        # Timing distribution histograms
│   ├── *_power_profile.png      # Power consumption profiles
│   ├── *_energy.png             # Energy analysis charts
│   ├── kem_*_comparison.png     # KEM comparison charts
│   ├── sig_*_comparison.png     # Signature comparison charts
│   └── aead_*_comparison.png    # AEAD comparison charts
│
└── analysis/                    # Markdown analysis reports
    └── benchmark_report.md      # Detailed markdown analysis
```

## Algorithms Benchmarked

### Key Encapsulation Mechanisms (KEM) - 9 Algorithms
| Algorithm | NIST Level | Operations |
|-----------|------------|------------|
| ML-KEM-512 | 1 | keygen, encapsulate, decapsulate |
| ML-KEM-768 | 3 | keygen, encapsulate, decapsulate |
| ML-KEM-1024 | 5 | keygen, encapsulate, decapsulate |
| Classic-McEliece-348864 | 1 | keygen, encapsulate, decapsulate |
| Classic-McEliece-460896 | 3 | keygen, encapsulate, decapsulate |
| Classic-McEliece-8192128 | 5 | keygen, encapsulate, decapsulate |
| HQC-128 | 1 | keygen, encapsulate, decapsulate |
| HQC-192 | 3 | keygen, encapsulate, decapsulate |
| HQC-256 | 5 | keygen, encapsulate, decapsulate |

### Digital Signatures (SIG) - 8 Algorithms
| Algorithm | NIST Level | Operations |
|-----------|------------|------------|
| ML-DSA-44 | 1 | keygen, sign, verify |
| ML-DSA-65 | 3 | keygen, sign, verify |
| ML-DSA-87 | 5 | keygen, sign, verify |
| Falcon-512 | 1 | keygen, sign, verify |
| Falcon-1024 | 5 | keygen, sign, verify |
| SPHINCS+-SHA2-128s | 1 | keygen, sign, verify |
| SPHINCS+-SHA2-192s | 3 | keygen, sign, verify |
| SPHINCS+-SHA2-256s | 5 | keygen, sign, verify |

### Authenticated Encryption (AEAD) - 3 Algorithms
| Algorithm | Security | Operations |
|-----------|----------|------------|
| AES-256-GCM | 256-bit | encrypt, decrypt (1KB, 4KB, 64KB, 1MB) |
| ChaCha20-Poly1305 | 256-bit | encrypt, decrypt (1KB, 4KB, 64KB, 1MB) |
| Ascon-128 | 128-bit | encrypt, decrypt (1KB, 4KB, 64KB, 1MB) |

## Measurement Details

- **Platform**: Raspberry Pi 4 Model B (4GB)
- **Power Sensor**: INA219 @ I2C 0x40
- **Sample Rate**: 1000 Hz
- **Iterations**: 100 per operation
- **Total Measurements**: 7,500+
- **Date**: January 2026

## Metrics Captured

Each measurement includes:
- `timing.perf_ns`: High-resolution timing (nanoseconds)
- `power.voltage_mean_v`: Mean voltage per iteration
- `power.current_mean_a`: Mean current per iteration
- `power.power_mean_w`: Mean power consumption (Watts)
- `power.energy_j`: Energy per operation (Joules)
- `power.samples`: Number of power samples captured

## Usage

### Regenerate Analysis
```bash
python bench/analyze_power_benchmark.py -i individual_benchmarks/raw_data -o individual_benchmarks/analysis
```

### Regenerate PDF Book
```bash
python bench/generate_benchmark_book.py -i individual_benchmarks/raw_data -o individual_benchmarks
```

## Key Findings

1. **Fastest KEM**: ML-KEM-512 (~0.3ms keygen)
2. **Slowest KEM**: Classic-McEliece-8192128 (~4 seconds keygen)
3. **Fastest Signature**: ML-DSA-44 (~0.6ms sign)
4. **Most Energy Efficient**: ML-KEM family
5. **Most Conservative Security**: SPHINCS+ (hash-based, quantum-resistant assumptions)

---
*Generated from 100-iteration benchmarks with real-time INA219 power monitoring*
