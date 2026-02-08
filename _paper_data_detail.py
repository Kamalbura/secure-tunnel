#!/usr/bin/env python3
"""
Deeper analysis: Table 7 should use SPECIFIC suites, not KEM medians that
include heavy SPHINCS sigs. Also compute std devs and other paper values.
"""
import json, pathlib, statistics, math
from collections import defaultdict

ROOT = pathlib.Path("logs/benchmarks/runs/no-ddos")

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

    parts = sid.replace("cs-", "", 1)
    kem_name = sig_name = aead_name = ""
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

    suites.append({
        "suite_id": sid, "kem": kem_name, "sig": sig_name, "aead": aead_name,
        "level": nist_level, "hs_ms": total, "proto_ms": proto,
        "sig_sign_ms": cp.get("signature_sign_time_ms"),
        "sig_verify_ms": cp.get("signature_verify_time_ms"),
        "pk_size": cp.get("pub_key_size_bytes"),
        "sig_size": cp.get("sig_size_bytes"),
        "total_crypto_ms": cp.get("total_crypto_time_ms"),
    })

seen = set()
unique = []
for s in suites:
    if s["suite_id"] not in seen:
        seen.add(s["suite_id"])
        unique.append(s)
suites = unique

# ── All suites sorted by handshake time ──
print("ALL SUITES ranked by handshake time:")
print(f"{'#':>3}  {'hs_ms':>10}  {'KEM':>20}  {'SIG':>15}  {'AEAD':>20}")
for i, s in enumerate(sorted(suites, key=lambda x: x["hs_ms"]), 1):
    print(f"{i:3d}  {s['hs_ms']:10.1f}  {s['kem']:>20}  {s['sig']:>15}  {s['aead']:>20}")

print()

# ── Table 7: Rekey overhead table uses REPRESENTATIVE suites ──
# Paper Table 7 uses specific suites as representative, one per KEM family
# Let's check what the paper originally used and use the Pareto-optimal suite
# The paper uses one representative per KEM: ML-KEM-768, HQC-256, McEliece-348864, McEliece-8192128
# We want the FASTEST variant to represent the KEM's rekey cost

print("=" * 70)
print("TABLE 7 CANDIDATES - fastest suite per KEM family")
print("=" * 70)
by_kem = defaultdict(list)
for s in suites:
    by_kem[s["kem"]].append(s)

for kem in sorted(by_kem.keys()):
    fastest = min(by_kem[kem], key=lambda x: x["hs_ms"])
    vals = [s["hs_ms"] for s in by_kem[kem]]
    print(f"  {kem:25s}  fastest={fastest['hs_ms']:8.1f}ms ({fastest['sig']}+{fastest['aead']})")
    if len(vals) > 1:
        print(f"  {'':25s}  median ={statistics.median(vals):8.1f}ms  stdev={statistics.stdev(vals):8.1f}ms")

print()

# ── McEliece stdev (paper says 6920s, should be ms) ──
print("=" * 70)
print("McEliece-8192128 std dev")
print("=" * 70)
mce_vals = [s["hs_ms"] for s in by_kem.get("McEliece-8192128", [])]
if mce_vals and len(mce_vals) > 1:
    print(f"  n={len(mce_vals)}")
    print(f"  mean={statistics.mean(mce_vals):.1f}ms")
    print(f"  stdev={statistics.stdev(mce_vals):.1f}ms")
    print(f"  median={statistics.median(mce_vals):.1f}ms")

print()

# ── Per-level StdDev for Table 5 ──
print("=" * 70)
print("PER-LEVEL Std Dev for Table 5")
print("=" * 70)
by_level = defaultdict(list)
for s in suites:
    by_level[s["level"]].append(s["hs_ms"])

for lvl in [1, 3, 5]:
    vals = by_level[lvl]
    if len(vals) > 1:
        sd = statistics.stdev(vals)
    else:
        sd = 0
    print(f"  L{lvl}: stdev={sd:.1f}ms")

print()

# ── Count total data points (measurements) ──
# Each suite = 1 handshake measurement (in single-run mode)
print("=" * 70)
print("DATA POINT COUNTS")
print("=" * 70)
all_drone = list(ROOT.glob("*_drone.json"))
all_gcs = list(ROOT.glob("*_gcs.json"))
new_drone = list(ROOT.glob("*20260207_172159*_drone.json"))
old_drone = list(ROOT.glob("*20260207_144051*_drone.json"))
print(f"  Total drone JSON files: {len(all_drone)}")
print(f"  Total GCS JSON files: {len(all_gcs)}")
print(f"  New run drone files: {len(new_drone)}")
print(f"  Old run drone files: {len(old_drone)}")
# 72 suites x 2 runs = 144 drone files (some may be failures)
# Per file: 1 handshake + metrics_summary data points

# Count metrics in each file
metric_counts = []
for f in ROOT.glob("*20260207_172159*_drone.json"):
    data = json.loads(f.read_text(encoding="utf-8"))
    # Network metrics have a throughput_samples array
    net = data.get("network", {})
    throughput = net.get("throughput_samples", [])
    metric_counts.append(len(throughput))

total_throughput = sum(metric_counts)
print(f"  Total throughput samples in new run: {total_throughput}")

# ── Figure out if the old inflated data is still in dashboard ──
print()
print("=" * 70)
print("CHECKING OLD RUN FILES FOR PATCHING")
print("=" * 70)
mismatch = 0
for f in ROOT.glob("*_drone.json"):
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
    except:
        continue
    hs = data.get("handshake", {})
    total = hs.get("handshake_total_duration_ms")
    proto = hs.get("protocol_handshake_duration_ms")
    if total is not None and proto is not None:
        if abs(total - proto) > 0.01:
            mismatch += 1
            print(f"  MISMATCH: {f.name}  total={total:.1f}  proto={proto:.1f}")

if mismatch == 0:
    print("  ALL OK - all drone files have total == protocol (patched or natively correct)")
else:
    print(f"  FOUND {mismatch} mismatches!")

# ── SPHINCS impact analysis ──
print()
print("=" * 70)
print("SPHINCS IMPACT (for Discussion section)")
print("=" * 70)
sphincs_suites = [s for s in suites if "SPHINCS" in s["sig"]]
non_sphincs = [s for s in suites if "SPHINCS" not in s["sig"]]

for group, label in [(sphincs_suites, "SPHINCS"), (non_sphincs, "Non-SPHINCS")]:
    vals = [s["hs_ms"] for s in group]
    if vals:
        print(f"  {label}: n={len(vals)} mean={statistics.mean(vals):.1f}ms median={statistics.median(vals):.1f}ms")

# Per-KEM split
for kem in ["ML-KEM-512", "ML-KEM-768", "ML-KEM-1024"]:
    sp = [s["hs_ms"] for s in suites if s["kem"] == kem and "SPHINCS" in s["sig"]]
    ns = [s["hs_ms"] for s in suites if s["kem"] == kem and "SPHINCS" not in s["sig"]]
    if sp and ns:
        print(f"  {kem}: SPHINCS={sp[0]:.1f}ms vs non-SPHINCS max={max(ns):.1f}ms")

print()

# ── Verify what Table 6 Pareto suites look like in detail ──
print("=" * 70)
print("TABLE 6 PARETO DETAIL")
print("=" * 70)
for lvl in [1, 3, 5]:
    level_suites = [s for s in suites if s["level"] == lvl]
    # Sort by handshake time
    level_suites.sort(key=lambda x: x["hs_ms"])
    # Top 3
    for i, s in enumerate(level_suites[:5], 1):
        print(f"  L{lvl} #{i}: {s['kem']} + {s['sig']} ({s['aead']}): "
              f"T_hs={s['hs_ms']:.1f}ms  PK={s['pk_size']}B  SIG={s['sig_size']}B")
    print()
