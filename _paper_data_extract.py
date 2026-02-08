#!/usr/bin/env python3
"""
Extract corrected benchmark data for research paper tables.
Uses ONLY the corrected run (20260207_172159) with protocol-level handshake times.
"""
import json, pathlib, statistics, math
from collections import defaultdict

ROOT = pathlib.Path("logs/benchmarks/runs/no-ddos")

# ── Collect all suites from latest run ──
suites = []
for f in sorted(ROOT.glob("*20260207_172159*_drone.json")):
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
    except:
        continue
    hs = data.get("handshake", {})
    cp = data.get("crypto_primitives", {})
    rc = data.get("run_context", {})
    sid = rc.get("suite_id", f.stem)

    success = hs.get("handshake_success")
    total = hs.get("handshake_total_duration_ms")
    proto = hs.get("protocol_handshake_duration_ms")

    if not success or total is None or proto is None:
        continue

    # Parse KEM, AEAD, SIG from suite_id
    # Format: cs-{kem}-{aead}-{sig}
    parts = sid.replace("cs-", "", 1)

    # Determine KEM family and level
    kem_name = ""
    sig_name = ""
    aead_name = ""
    nist_level = 0

    if "mlkem512" in parts: kem_name, nist_level = "ML-KEM-512", 1
    elif "mlkem768" in parts: kem_name, nist_level = "ML-KEM-768", 3
    elif "mlkem1024" in parts: kem_name, nist_level = "ML-KEM-1024", 5
    elif "classicmceliece348864" in parts: kem_name, nist_level = "McEliece-348864", 1
    elif "classicmceliece460896" in parts: kem_name, nist_level = "McEliece-460896", 3
    elif "classicmceliece8192128" in parts: kem_name, nist_level = "McEliece-8192128", 5
    elif "hqc128" in parts: kem_name, nist_level = "HQC-128", 1
    elif "hqc192" in parts: kem_name, nist_level = "HQC-192", 3
    elif "hqc256" in parts: kem_name, nist_level = "HQC-256", 5
    else: continue

    if "falcon512" in parts: sig_name = "Falcon-512"
    elif "falcon1024" in parts: sig_name = "Falcon-1024"
    elif "mldsa44" in parts: sig_name = "ML-DSA-44"
    elif "mldsa65" in parts: sig_name = "ML-DSA-65"
    elif "mldsa87" in parts: sig_name = "ML-DSA-87"
    elif "sphincs128s" in parts: sig_name = "SPHINCS+-128s"
    elif "sphincs192s" in parts: sig_name = "SPHINCS+-192s"
    elif "sphincs256s" in parts: sig_name = "SPHINCS+-256s"

    if "aesgcm" in parts: aead_name = "AES-256-GCM"
    elif "chacha20poly1305" in parts: aead_name = "ChaCha20-Poly1305"
    elif "ascon128a" in parts: aead_name = "Ascon-128a"

    kem_family = kem_name.split("-")[0] if "-" in kem_name else kem_name

    suites.append({
        "suite_id": sid,
        "kem": kem_name,
        "kem_family": kem_family,
        "sig": sig_name,
        "aead": aead_name,
        "level": nist_level,
        "handshake_ms": total,
        "proto_ms": proto,
        "kem_keygen_ms": cp.get("kem_keygen_time_ms"),
        "kem_encaps_ms": cp.get("kem_encapsulation_time_ms"),
        "kem_decaps_ms": cp.get("kem_decapsulation_time_ms"),
        "sig_sign_ms": cp.get("signature_sign_time_ms"),
        "sig_verify_ms": cp.get("signature_verify_time_ms"),
        "total_crypto_ms": cp.get("total_crypto_time_ms"),
        "pk_size": cp.get("pub_key_size_bytes"),
        "sig_size": cp.get("sig_size_bytes"),
    })

# Deduplicate (some files have two naming patterns)
seen = set()
unique_suites = []
for s in suites:
    key = s["suite_id"]
    if key not in seen:
        seen.add(key)
        unique_suites.append(s)
suites = unique_suites

print(f"Total unique successful suites: {len(suites)}")
print()

# ══════════════════════════════════════════════════════════════
# TABLE 5: End-to-end suite handshake times by NIST level
# ══════════════════════════════════════════════════════════════
print("=" * 70)
print("TABLE 5: End-to-end suite handshake times by NIST level")
print("=" * 70)
by_level = defaultdict(list)
for s in suites:
    by_level[s["level"]].append(s["handshake_ms"])

for lvl in [1, 3, 5]:
    vals = by_level[lvl]
    if not vals:
        continue
    n = len(vals)
    mean = statistics.mean(vals)
    med = statistics.median(vals)
    p95 = sorted(vals)[int(n * 0.95)] if n > 1 else vals[0]
    mx = max(vals)
    print(f"  L{lvl}: n={n}  mean={mean:.1f}ms  median={med:.1f}ms  P95={p95:.1f}ms  max={mx:.1f}ms")

print()

# ══════════════════════════════════════════════════════════════
# TABLE 5 ALTERNATIVE: By KEM family
# ══════════════════════════════════════════════════════════════
print("=" * 70)
print("By KEM family (for context)")
print("=" * 70)
by_kem = defaultdict(list)
for s in suites:
    by_kem[s["kem"]].append(s["handshake_ms"])

for k in sorted(by_kem.keys()):
    vals = by_kem[k]
    med = statistics.median(vals)
    mn = min(vals)
    mx = max(vals)
    print(f"  {k:25s}  n={len(vals):2d}  median={med:8.1f}ms  min={mn:8.1f}ms  max={mx:8.1f}ms")

print()

# ══════════════════════════════════════════════════════════════
# TABLE 6: Pareto-optimal suites (best handshake per NIST level)
# ══════════════════════════════════════════════════════════════
print("=" * 70)
print("TABLE 6: Pareto-optimal suites (fastest per NIST level)")
print("=" * 70)
for lvl in [1, 3, 5]:
    level_suites = [s for s in suites if s["level"] == lvl]
    if not level_suites:
        continue
    best = min(level_suites, key=lambda x: x["handshake_ms"])
    print(f"  L{lvl}: {best['kem']} + {best['sig']} ({best['aead']})")
    print(f"       T_hs = {best['handshake_ms']:.1f}ms  PK = {best['pk_size']} B")

print()

# ══════════════════════════════════════════════════════════════
# TABLE 7: Rekey overhead
# ══════════════════════════════════════════════════════════════
print("=" * 70)
print("TABLE 7: Rekey overhead per KEM family (median T_hs)")
print("=" * 70)
# Group by KEM, compute median T_hs
kem_medians = {}
for k, vals in by_kem.items():
    kem_medians[k] = statistics.median(vals)

for kem in ["ML-KEM-768", "HQC-256", "McEliece-348864", "McEliece-8192128"]:
    if kem not in kem_medians:
        continue
    ths = kem_medians[kem]
    for R in [60, 300, 3600]:
        phi = (ths / 1000) / (R + ths / 1000) * 100
        print(f"  {kem:22s}  T_hs={ths:8.1f}ms  R={R:5d}s  Phi={phi:.4f}%")
    print()

# ══════════════════════════════════════════════════════════════
# REGRESSION MODEL: log10(T_hs) vs log10(pk_size), log10(sig_size)
# ══════════════════════════════════════════════════════════════
print("=" * 70)
print("REGRESSION: log10(T_hs) = a + b*log10(pk_size) + c*log10(sig_size)")
print("=" * 70)

# Collect valid data points
X, Y = [], []
for s in suites:
    if s["pk_size"] and s["sig_size"] and s["handshake_ms"] > 0:
        X.append((math.log10(s["pk_size"]), math.log10(s["sig_size"])))
        Y.append(math.log10(s["handshake_ms"]))

n = len(X)
print(f"  Data points: {n}")

# Simple OLS: Y = a + b*x1 + c*x2
# Using normal equations
if n > 3:
    sum_y = sum(Y)
    sum_x1 = sum(x[0] for x in X)
    sum_x2 = sum(x[1] for x in X)
    sum_x1y = sum(x[0] * y for x, y in zip(X, Y))
    sum_x2y = sum(x[1] * y for x, y in zip(X, Y))
    sum_x1x1 = sum(x[0] ** 2 for x in X)
    sum_x2x2 = sum(x[1] ** 2 for x in X)
    sum_x1x2 = sum(x[0] * x[1] for x in X)

    # Normal equations: [n, sum_x1, sum_x2; sum_x1, sum_x1x1, sum_x1x2; sum_x2, sum_x1x2, sum_x2x2] * [a,b,c] = [sum_y, sum_x1y, sum_x2y]
    # Solve with numpy-free approach (Cramer's rule for 3x3)
    A = [
        [n, sum_x1, sum_x2],
        [sum_x1, sum_x1x1, sum_x1x2],
        [sum_x2, sum_x1x2, sum_x2x2],
    ]
    B = [sum_y, sum_x1y, sum_x2y]

    def det3(m):
        return (m[0][0]*(m[1][1]*m[2][2]-m[1][2]*m[2][1])
               -m[0][1]*(m[1][0]*m[2][2]-m[1][2]*m[2][0])
               +m[0][2]*(m[1][0]*m[2][1]-m[1][1]*m[2][0]))

    D = det3(A)
    Da = det3([
        [B[0], A[0][1], A[0][2]],
        [B[1], A[1][1], A[1][2]],
        [B[2], A[2][1], A[2][2]],
    ])
    Db = det3([
        [A[0][0], B[0], A[0][2]],
        [A[1][0], B[1], A[1][2]],
        [A[2][0], B[2], A[2][2]],
    ])
    Dc = det3([
        [A[0][0], A[0][1], B[0]],
        [A[1][0], A[1][1], B[1]],
        [A[2][0], A[2][1], B[2]],
    ])

    a = Da / D
    b = Db / D
    c = Dc / D

    # R-squared
    y_mean = sum_y / n
    ss_tot = sum((y - y_mean) ** 2 for y in Y)
    ss_res = sum((y - (a + b * x[0] + c * x[1])) ** 2 for x, y in zip(X, Y))
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0

    print(f"  log10(T_hs) = {a:.2f} + {b:.2f}*log10(pk_size) + {c:.2f}*log10(sig_size)")
    print(f"  R^2 = {r2:.4f}")

print()

# ══════════════════════════════════════════════════════════════
# KEY INLINE NUMBERS
# ══════════════════════════════════════════════════════════════
print("=" * 70)
print("KEY INLINE NUMBERS FOR PAPER")
print("=" * 70)

# McEliece cross-family degradation
mce8192_vals = by_kem.get("McEliece-8192128", [])
mlkem1024_vals = by_kem.get("ML-KEM-1024", [])
if mce8192_vals and mlkem1024_vals:
    mce_med = statistics.median(mce8192_vals)
    mlk_med = statistics.median(mlkem1024_vals)
    ratio = mce_med / mlk_med
    reduction = (1 - mlk_med / mce_med) * 100
    print(f"  McEliece-8192128 median: {mce_med:.1f}ms")
    print(f"  ML-KEM-1024 median:      {mlk_med:.1f}ms")
    print(f"  Ratio: {ratio:.0f}x")
    print(f"  Reduction: {reduction:.1f}%")

# ML-KEM range
all_mlkem = []
for k in ["ML-KEM-512", "ML-KEM-768", "ML-KEM-1024"]:
    all_mlkem.extend(by_kem.get(k, []))
if all_mlkem:
    print(f"  ML-KEM range: {min(all_mlkem):.1f}ms - {max(all_mlkem):.1f}ms")
    print(f"  ML-KEM median: {statistics.median(all_mlkem):.1f}ms")
    # Excluding SPHINCS
    mlkem_no_sphincs = [s["handshake_ms"] for s in suites
                        if s["kem_family"] == "ML" and "SPHINCS" not in s["sig"]]
    if mlkem_no_sphincs:
        print(f"  ML-KEM (no SPHINCS) max: {max(mlkem_no_sphincs):.1f}ms")

# Mean increase L1 to L5
l1_mean = statistics.mean(by_level[1]) if by_level[1] else 0
l5_mean = statistics.mean(by_level[5]) if by_level[5] else 0
if l1_mean > 0:
    print(f"  L1 mean: {l1_mean:.1f}ms, L5 mean: {l5_mean:.1f}ms, ratio: {l5_mean/l1_mean:.1f}x")

# McEliece-348864 (L1) vs ML-KEM-1024 (L5) for the "family matters" argument
mce348_vals = by_kem.get("McEliece-348864", [])
if mce348_vals and mlkem1024_vals:
    mce348_med = statistics.median(mce348_vals)
    mlk1024_med = statistics.median(mlkem1024_vals)
    print(f"  McEliece-348864 (L1) median: {mce348_med:.1f}ms")
    print(f"  ML-KEM-1024 (L5) median:     {mlk1024_med:.1f}ms")
    print(f"  McEliece L1 is {mce348_med/mlk1024_med:.0f}x slower than ML-KEM L5")

print()

# ══════════════════════════════════════════════════════════════
# ENERGY BUDGET IMPACT (recalculate)
# ══════════════════════════════════════════════════════════════
print("=" * 70)
print("ENERGY BUDGET (30-min flight)")
print("=" * 70)
flight_s = 1800
avg_power_w = 3.99
total_energy_j = avg_power_w * flight_s
rekey_interval = 60
n_rekeys = flight_s // rekey_interval

for kem, label in [("ML-KEM-768", "ML-KEM"), ("McEliece-8192128", "McEliece-8192128")]:
    vals = by_kem.get(kem, [])
    if not vals:
        continue
    ths_s = statistics.median(vals) / 1000.0
    energy_per_rekey = avg_power_w * ths_s
    total_rekey_energy = energy_per_rekey * n_rekeys
    pct = total_rekey_energy / total_energy_j * 100
    print(f"  {label}: T_hs={ths_s*1000:.1f}ms, {n_rekeys} rekeys")
    print(f"    Energy/rekey: {energy_per_rekey:.4f}J")
    print(f"    Total rekey energy: {total_rekey_energy:.3f}J ({pct:.4f}% of flight)")

print()
print("DONE - Use these values to update paper tables")
