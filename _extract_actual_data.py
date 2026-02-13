#!/usr/bin/env python3
"""Extract every number needed for the paper from the actual benchmark JSONs."""
import json, os
from pathlib import Path
import numpy as np
from collections import defaultdict

BASE = Path(r"c:\Users\burak\ptojects\secure-tunnel\logs\benchmarks\runs")
BASELINE = BASE / "no-ddos" / "_archived_20260212"
RUN_ID = "20260211_141627"

def parse_suite_id(sid):
    kem_map = {
        "mlkem512": "ML-KEM-512", "mlkem768": "ML-KEM-768", "mlkem1024": "ML-KEM-1024",
        "hqc128": "HQC-128", "hqc192": "HQC-192", "hqc256": "HQC-256",
        "classicmceliece348864": "McEliece-348864",
        "classicmceliece460896": "McEliece-460896",
        "classicmceliece8192128": "McEliece-8192128",
    }
    aead_map = {"aesgcm": "AES-256-GCM", "chacha20poly1305": "ChaCha20-Poly1305", "ascon128a": "Ascon-128a"}
    sig_map = {
        "mldsa44": "ML-DSA-44", "mldsa65": "ML-DSA-65", "mldsa87": "ML-DSA-87",
        "falcon512": "Falcon-512", "falcon1024": "Falcon-1024",
        "sphincs128s": "SPHINCS+-128s", "sphincs192s": "SPHINCS+-192s", "sphincs256s": "SPHINCS+-256s",
    }
    raw = sid.replace("cs-", "")
    kem = aead = sig = None
    for k, v in kem_map.items():
        if raw.startswith(k): kem = v; raw = raw[len(k)+1:]; break
    for k, v in aead_map.items():
        if raw.startswith(k): aead = v; raw = raw[len(k)+1:]; break
    for k, v in sig_map.items():
        if raw == k: sig = v; break
    return kem, aead, sig

def kem_family(k):
    if "ML-KEM" in k: return "ML-KEM"
    if "HQC" in k: return "HQC"
    if "McEliece" in k: return "Classic-McEliece"
    return "?"

# Load all drone JSONs from baseline
data = {}
for f in sorted(BASELINE.glob(f"{RUN_ID}_*_drone.json")):
    with open(f) as fh:
        d = json.load(fh)
    sid = d["run_context"]["suite_id"]
    data[sid] = d
print(f"Loaded {len(data)} suites\n")

# ========= TABLE 3: KEM bench =========
print("=" * 80)
print("TABLE 3: KEM Operation Times (median from live tunnel data)")
print("=" * 80)
kems = ["ML-KEM-512","ML-KEM-768","ML-KEM-1024","HQC-128","HQC-192","HQC-256",
        "McEliece-348864","McEliece-460896","McEliece-8192128"]
for kem in kems:
    kg, enc, dec, pk = [], [], [], []
    for sid, d in data.items():
        k, _, _ = parse_suite_id(sid)
        if k == kem:
            cp = d.get("crypto_primitives", {})
            v = cp.get("kem_keygen_time_ms")
            if v and v > 0: kg.append(v)
            v = cp.get("kem_encapsulation_time_ms")
            if v and v > 0: enc.append(v)
            v = cp.get("kem_decapsulation_time_ms")
            if v and v > 0: dec.append(v)
            v = cp.get("pub_key_size_bytes")
            if v: pk.append(v)
    print(f"  {kem:25s}  keygen={np.median(kg) if kg else 'N/A':>10}  "
          f"encaps={np.median(enc) if enc else 'N/A':>10}  "
          f"decaps={np.median(dec) if dec else 'N/A':>10}  "
          f"pk={pk[0] if pk else 'N/A':>10}  (n={len(kg)})")

# ========= TABLE 4: SIG bench =========
print(f"\n{'='*80}")
print("TABLE 4: SIG Operation Times (median from live tunnel data)")
print("=" * 80)
sigs = ["ML-DSA-44","ML-DSA-65","ML-DSA-87","Falcon-512","Falcon-1024",
        "SPHINCS+-128s","SPHINCS+-192s","SPHINCS+-256s"]
for sig in sigs:
    sgn, ver, kgen, ss = [], [], [], []
    for sid, d in data.items():
        _, _, s = parse_suite_id(sid)
        if s == sig:
            cp = d.get("crypto_primitives", {})
            v = cp.get("signature_sign_time_ms")
            if v and v > 0: sgn.append(v)
            v = cp.get("signature_verify_time_ms")
            if v and v > 0: ver.append(v)
            v = cp.get("signature_keygen_time_ms")
            if v and v > 0: kgen.append(v)
            v = cp.get("sig_size_bytes")
            if v: ss.append(v)
    print(f"  {sig:25s}  keygen={np.median(kgen) if kgen else 'N/A':>10}  "
          f"sign={np.median(sgn) if sgn else 'N/A':>10}  "
          f"verify={np.median(ver) if ver else 'N/A':>10}  "
          f"sig_size={ss[0] if ss else 'N/A':>10}  (n={len(sgn)})")

# ========= TABLE 5: AEAD bench =========
print(f"\n{'='*80}")
print("TABLE 5: AEAD Performance (median from live tunnel, µs)")
print("=" * 80)
aeads = ["AES-256-GCM","ChaCha20-Poly1305","Ascon-128a"]
aead_enc_vals = {}
for aead in aeads:
    enc_us, dec_us = [], []
    for sid, d in data.items():
        _, a, _ = parse_suite_id(sid)
        if a == aead:
            e = d.get("data_plane", {}).get("aead_encrypt_avg_ns")
            dc = d.get("data_plane", {}).get("aead_decrypt_avg_ns")
            if e and e > 0: enc_us.append(e / 1000)
            if dc and dc > 0: dec_us.append(dc / 1000)
    enc_med = np.median(enc_us) if enc_us else 0
    dec_med = np.median(dec_us) if dec_us else 0
    aead_enc_vals[aead] = enc_med
    print(f"  {aead:25s}  encrypt={enc_med:>8.1f} µs  decrypt={dec_med:>8.1f} µs  (n={len(enc_us)})")

# ========= TABLE 6: End-to-End by NIST Level =========
print(f"\n{'='*80}")
print("TABLE 6: End-to-End Handshake by NIST Level")
print("=" * 80)
levels = {"L1": [], "L3": [], "L5": []}
for sid, d in data.items():
    lvl = d.get("crypto_identity", {}).get("suite_security_level", "?")
    hs = d.get("handshake", {}).get("handshake_total_duration_ms", 0)
    succ = d.get("handshake", {}).get("handshake_success", False)
    if lvl in levels and hs > 0:
        levels[lvl].append(hs)

for lvl in ["L1","L3","L5"]:
    v = levels[lvl]
    if v:
        print(f"  {lvl}: n={len(v):>3}  mean={np.mean(v):>10.1f}  "
              f"median={np.median(v):>10.1f}  P95={np.percentile(v,95):>10.1f}  "
              f"max={max(v):>10.1f}")

# ========= TABLE 7: Pareto suites =========
print(f"\n{'='*80}")
print("TABLE 7: Pareto-Optimal Suites")
print("=" * 80)
pareto = [
    ("cs-mlkem512-aesgcm-falcon512",   "ML-KEM-512 + Falcon-512",   "L1"),
    ("cs-mlkem768-aesgcm-mldsa65",     "ML-KEM-768 + ML-DSA-65",    "L3"),
    ("cs-mlkem1024-aesgcm-falcon1024", "ML-KEM-1024 + Falcon-1024", "L5"),
]
for sid, name, lvl in pareto:
    if sid in data:
        hs = data[sid]["handshake"]["handshake_total_duration_ms"]
        pk = data[sid]["crypto_primitives"]["pub_key_size_bytes"]
        phi60 = (hs/1000)/(60+hs/1000)*100
        print(f"  {name:35s}  {lvl}  T_hs={hs:>10.2f} ms  PK={pk:>10,}  Φ(60s)={phi60:.4f}%")

# ========= TABLE 8: Rekey overhead =========
print(f"\n{'='*80}")
print("TABLE 8: Rekey Overhead (select suites)")
print("=" * 80)
rekey_suites = {
    "ML-KEM-768": "cs-mlkem768-aesgcm-mldsa65",
    "HQC-256": "cs-hqc256-aesgcm-falcon1024",
    "McE-348864": "cs-classicmceliece348864-aesgcm-falcon512",
    "McE-8192128": "cs-classicmceliece8192128-aesgcm-mldsa87",
}
for label, sid in rekey_suites.items():
    if sid in data:
        hs = data[sid]["handshake"]["handshake_total_duration_ms"]
        phi60 = (hs/1000)/(60+hs/1000)*100
        phi300 = (hs/1000)/(300+hs/1000)*100
        phi3600 = (hs/1000)/(3600+hs/1000)*100
        print(f"  {label:20s}  T_hs={hs:>10.2f} ms  Φ(60s)={phi60:.4f}%  "
              f"Φ(300s)={phi300:.4f}%  Φ(3600s)={phi3600:.5f}%")

# ========= System Metrics =========
print(f"\n{'='*80}")
print("TABLE 9: System Metrics during tunnel operation")
print("=" * 80)
# Select one ML-KEM and one McEliece suite
mlkem_sid = "cs-mlkem768-aesgcm-mldsa65"
mce_sid = "cs-classicmceliece8192128-aesgcm-mldsa87"
for label, sid in [("ML-KEM-768+ML-DSA-65", mlkem_sid), ("McE-8192128+ML-DSA-87", mce_sid)]:
    if sid in data:
        d = data[sid]
        sd = d.get("system_drone", {})
        dp = d.get("data_plane", {})
        print(f"  {label}:")
        print(f"    CPU avg:  {sd.get('cpu_usage_avg_percent', '?')}")
        print(f"    CPU peak: {sd.get('cpu_usage_peak_percent', '?')}")
        print(f"    Temp:     {sd.get('temperature_c', '?')} °C")
        print(f"    Pkts sent:{dp.get('packets_sent', '?')}")
        print(f"    Pkt loss: {dp.get('packet_loss_ratio', '?')}")

# ========= ML-KEM max handshake (excluding SPHINCS+) =========
print(f"\n{'='*80}")
print("ML-KEM suites excluding SPHINCS+ — max handshake")
print("=" * 80)
mlkem_no_sphincs = []
for sid, d in data.items():
    k, _, s = parse_suite_id(sid)
    if "ML-KEM" in (k or "") and "SPHINCS" not in (s or ""):
        hs = d.get("handshake", {}).get("handshake_total_duration_ms", 0)
        if hs > 0:
            mlkem_no_sphincs.append((sid, hs))
mlkem_no_sphincs.sort(key=lambda x: x[1], reverse=True)
for sid, hs in mlkem_no_sphincs[:5]:
    print(f"  {sid}: {hs:.2f} ms")
if mlkem_no_sphincs:
    print(f"  MAX = {mlkem_no_sphincs[0][1]:.2f} ms")

# ========= Family medians =========
print(f"\n{'='*80}")
print("KEM Family Medians (handshake)")
print("=" * 80)
fam_vals = defaultdict(list)
for sid, d in data.items():
    k, _, _ = parse_suite_id(sid)
    fam = kem_family(k)
    hs = d.get("handshake", {}).get("handshake_total_duration_ms", 0)
    if hs > 0: fam_vals[fam].append(hs)
for fam in ["ML-KEM","HQC","Classic-McEliece"]:
    v = fam_vals[fam]
    print(f"  {fam:20s}  median={np.median(v):.1f}  mean={np.mean(v):.1f}  max={max(v):.1f}  (n={len(v)})")

# ========= Cross-family degradation example =========
print(f"\n{'='*80}")
print("Cross-family degradation: McE-8192128(L5) vs ML-KEM-1024(L5)")
print("=" * 80)
mce_l5 = []
mlkem_l5 = []
for sid, d in data.items():
    k, _, _ = parse_suite_id(sid)
    if k == "McEliece-8192128":
        hs = d.get("handshake", {}).get("handshake_total_duration_ms", 0)
        if hs > 0: mce_l5.append(hs)
    if k == "ML-KEM-1024":
        hs = d.get("handshake", {}).get("handshake_total_duration_ms", 0)
        if hs > 0: mlkem_l5.append(hs)
mce_med = np.median(mce_l5) if mce_l5 else 0
mlkem_med = np.median(mlkem_l5) if mlkem_l5 else 0
print(f"  McE-8192128 median:  {mce_med:.1f} ms")
print(f"  ML-KEM-1024 median:  {mlkem_med:.1f} ms")
print(f"  Ratio: {mce_med/mlkem_med:.0f}×") if mlkem_med else None

# ========= McE-348864 vs ML-KEM-1024 (discussion example) =========
print(f"\n{'='*80}")
print("Discussion: McE-348864(L1) vs ML-KEM-1024(L5)")
print("=" * 80)
mce_l1 = []
for sid, d in data.items():
    k, _, _ = parse_suite_id(sid)
    if k == "McEliece-348864":
        hs = d.get("handshake", {}).get("handshake_total_duration_ms", 0)
        if hs > 0: mce_l1.append(hs)
mce_l1_med = np.median(mce_l1) if mce_l1 else 0
print(f"  McE-348864 median:  {mce_l1_med:.1f} ms")
print(f"  ML-KEM-1024 median: {mlkem_med:.1f} ms")
if mlkem_med: print(f"  Ratio: {mce_l1_med/mlkem_med:.0f}×")

# ========= Handshake success count =========
print(f"\n{'='*80}")
print("Handshake Success")
print("=" * 80)
passed = sum(1 for d in data.values() if d.get("handshake", {}).get("handshake_success"))
print(f"  Passed: {passed}/72")

# ========= Rekey ratio McE-8192128 vs ML-KEM-768 =========
print(f"\n{'='*80}")
print("Rekey Overhead Ratio")
print("=" * 80)
mlkem768_hs = data.get("cs-mlkem768-aesgcm-mldsa65", {}).get("handshake", {}).get("handshake_total_duration_ms", 0)
mce8192_hs = data.get("cs-classicmceliece8192128-aesgcm-mldsa87", {}).get("handshake", {}).get("handshake_total_duration_ms", 0)
phi_ml = (mlkem768_hs/1000)/(60+mlkem768_hs/1000)*100
phi_mc = (mce8192_hs/1000)/(60+mce8192_hs/1000)*100
print(f"  ML-KEM-768 T_hs = {mlkem768_hs:.2f} ms → Φ(60s) = {phi_ml:.4f}%")
print(f"  McE-8192128 T_hs = {mce8192_hs:.2f} ms → Φ(60s) = {phi_mc:.4f}%")
print(f"  Ratio: {phi_mc/phi_ml:.0f}× (McE/MLK)")

# ========= Energy: rekey 30x at 60s for 30min flight =========
print(f"\n{'='*80}")
print("Energy Budget (30 rekeys in 30-min flight at 3.99 W)")
print("=" * 80)
total_flight_J = 3.99 * 1800  # 7182 J
mlkem_per_rekey_J = 3.99 * (mlkem768_hs / 1000)  # watts * seconds
mce_per_rekey_J = 3.99 * (mce8192_hs / 1000)
mlkem_total_J = 30 * mlkem_per_rekey_J
mce_total_J = 30 * mce_per_rekey_J
print(f"  Total flight energy: {total_flight_J:.0f} J")
print(f"  ML-KEM-768:  {mlkem_per_rekey_J:.4f} J/rekey × 30 = {mlkem_total_J:.2f} J = {mlkem_total_J/total_flight_J*100:.3f}%")
print(f"  McE-8192128: {mce_per_rekey_J:.4f} J/rekey × 30 = {mce_total_J:.2f} J = {mce_total_J/total_flight_J*100:.3f}%")
print(f"  Ratio: {mce_total_J/mlkem_total_J:.0f}×")

print(f"\n{'='*80}")
print("DONE")
print("=" * 80)
