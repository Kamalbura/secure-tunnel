# PQC Benchmark Analysis Pipeline - Summary Report

## Execution Summary

**Pipeline Executed:** 2026-01-11
**Target System:** Raspberry Pi 4 Model B Rev 1.5 (dev@100.101.93.23)
**Python Environment:** ~/cenv (Python 3.11.2)

---

## Data Provenance

All computed values derive exclusively from:
```
bench_results/raw/kem/*.json    → 27 files (5,400 iterations)
bench_results/raw/sig/*.json    → 24 files (4,800 iterations)
bench_results/raw/aead/*.json   → 24 files (4,800 iterations)
bench_results/raw/suites/*.json → 23 files (4,600 iterations)
```

**Total:** 98 benchmark files, 19,600 timing iterations

---

## Output Artifacts

### CSV Exports (`bench_analysis/csv/`)

| File | Records | Size | Description |
|------|---------|------|-------------|
| raw_all.csv | 19,600 | 2.3 MB | Complete dataset with all algorithms and timings |
| raw_kem.csv | 5,400 | 544 KB | KEM benchmarks (keygen, encapsulate, decapsulate) |
| raw_sig.csv | 4,800 | 449 KB | Signature benchmarks (keygen, sign, verify) |
| raw_aead.csv | 4,800 | 481 KB | AEAD benchmarks (encrypt, decrypt) |
| raw_suite.csv | 4,600 | 857 KB | Suite handshake benchmarks |

### Statistical Summaries (`bench_analysis/stats/`)

| File | Description | Grouping |
|------|-------------|----------|
| stats_by_nist_level.csv | Aggregate statistics | NIST security level (L1/L3/L5) |
| stats_by_family.csv | Aggregate statistics | Algorithm family |
| stats_kem_by_level.csv | KEM comparison | Same NIST level, different algorithms |
| stats_family_by_level.csv | Family progression | Same family, different NIST levels |
| stats_kem_operations.csv | Per-algorithm stats | KEM: keygen/encapsulate/decapsulate |
| stats_sig_operations.csv | Per-algorithm stats | SIG: keygen/sign/verify |
| stats_aead_operations.csv | Per-algorithm stats | AEAD: encrypt/decrypt |
| stats_suite_comparison.csv | Full handshake stats | All cipher suites |

**Statistics computed:**
- count (n)
- mean_ns, mean_ms
- median_ns, median_ms
- stdev_ns
- min_ns, max_ns
- p95_ns, p95_ms

### Visualizations (`bench_analysis/plots/`)

| Plot Type | Files | Description |
|-----------|-------|-------------|
| Box plots (KEM) | kem_keygen_boxplot.{pdf,png}, kem_encapsulate_boxplot.{pdf,png}, kem_decapsulate_boxplot.{pdf,png} | Timing distribution per algorithm |
| Box plots (SIG) | sig_keygen_boxplot.{pdf,png}, sig_sign_boxplot.{pdf,png}, sig_verify_boxplot.{pdf,png} | Timing distribution per algorithm |
| NIST comparison | kem_nist_level_comparison.{pdf,png}, sig_nist_level_comparison.{pdf,png} | Mean times grouped by L1/L3/L5 |
| Family comparison | family_comparison.{pdf,png} | Mean keygen times by algorithm family |
| AEAD comparison | aead_encrypt_comparison.{pdf,png}, aead_decrypt_comparison.{pdf,png} | AEAD timing by payload size |
| Suite comparison | suite_handshake_comparison.{pdf,png} | Full handshake times by cipher suite |
| Size metrics | kem_sizes.{pdf,png}, sig_sizes.{pdf,png} | Key/ciphertext/signature sizes |

---

## LaTeX Report

A compilable LaTeX report template is provided at:
```
bench/analysis/benchmark_report.tex
```

The report includes:
- Experimental setup from environment.json
- Benchmark methodology from benchmark_pqc.py documentation
- Tables of raw statistics
- Figures with captions citing source files
- Sectioned comparisons (NIST level, same-family, primitive vs suite)

**To compile:**
```bash
cd bench/analysis
pdflatex benchmark_report.tex
pdflatex benchmark_report.tex  # Run twice for TOC
```

---

## Verification Criteria Met

| Criterion | Status |
|-----------|--------|
| All values derived from existing JSON files | ✓ |
| No metrics invented | ✓ |
| No power/energy/efficiency inferred | ✓ |
| Source files cited in all outputs | ✓ |
| No conclusions or recommendations | ✓ |
| Statistics computed from raw timing arrays | ✓ |
| 100% iteration success verified | ✓ |

---

## Scripts Created

| Script | Purpose | Location |
|--------|---------|----------|
| benchmark_analysis.py | Data ingestion & statistics | bench/analysis/ |
| benchmark_plots.py | Visualization generation | bench/analysis/ |
| run_analysis.py | Pipeline orchestration | bench/analysis/ |
| benchmark_report.tex | LaTeX report template | bench/analysis/ |

---

## Algorithms Covered

### Key Encapsulation Mechanisms (KEM)
- **ML-KEM** (NIST FIPS 203): 512, 768, 1024
- **Classic McEliece**: 348864 (L1), 460896 (L3), 8192128 (L5)
- **HQC**: 128 (L1), 192 (L3), 256 (L5)

### Digital Signatures
- **ML-DSA** (NIST FIPS 204): 44 (L1), 65 (L3), 87 (L5)
- **Falcon**: 512 (L1), 1024 (L5)
- **SPHINCS+**: SHA2-128s (L1), SHA2-192s (L3), SHA2-256s (L5)

### AEAD Ciphers
- **AES-256-GCM** (64B, 256B, 1024B, 4096B)
- **ChaCha20-Poly1305** (64B, 256B, 1024B, 4096B)
- **Ascon-128a** (64B, 256B, 1024B, 4096B)

### Cipher Suites
- 23 combinations: Classic-McEliece × {AES-GCM, ChaCha20, Ascon} × {ML-DSA, Falcon, SPHINCS+}

---

## Data Integrity Statement

> All timing values in this analysis were extracted directly from the `perf_time_ns` field 
> of JSON benchmark files generated by `bench/benchmark_pqc.py`. Statistical computations 
> (mean, median, standard deviation, min, max, 95th percentile) were performed on the raw 
> timing arrays using NumPy functions. No values were invented, inferred, or estimated.
> Source file citations are provided throughout.

---

*Generated by PQC Benchmark Analysis Pipeline v1.0.0*
