#!/usr/bin/env python3
"""
Verify all numbers used in the PPTX presentation against actual benchmark data.
Produces a comprehensive audit report.
"""

import json, os, glob
from pathlib import Path
from collections import defaultdict
import numpy as np

BASE = Path(r"c:\Users\burak\ptojects\secure-tunnel")
RUNS_DIR = BASE / "logs" / "benchmarks" / "runs"

SCENARIOS = {
    "no-ddos":      "20260211_141627",
    "ddos-xgboost": "20260211_150013",
    "ddos-txt":     "20260211_171406",
}

def parse_suite_id(suite_id):
    kem_map = {
        "mlkem512": "ML-KEM-512", "mlkem768": "ML-KEM-768", "mlkem1024": "ML-KEM-1024",
        "hqc128": "HQC-128", "hqc192": "HQC-192", "hqc256": "HQC-256",
        "classicmceliece348864": "Classic-McEliece-348864",
        "classicmceliece460896": "Classic-McEliece-460896",
        "classicmceliece8192128": "Classic-McEliece-8192128",
    }
    aead_map = {
        "aesgcm": "AES-256-GCM", "chacha20poly1305": "ChaCha20-Poly1305", "ascon128a": "Ascon-128a",
    }
    sig_map = {
        "mldsa44": "ML-DSA-44", "mldsa65": "ML-DSA-65", "mldsa87": "ML-DSA-87",
        "falcon512": "Falcon-512", "falcon1024": "Falcon-1024",
        "sphincs128s": "SPHINCS+-128s", "sphincs192s": "SPHINCS+-192s", "sphincs256s": "SPHINCS+-256s",
    }
    raw = suite_id.replace("cs-", "")
    kem = aead = sig = None
    for k, v in kem_map.items():
        if raw.startswith(k):
            kem = v; raw = raw[len(k)+1:]; break
    for k, v in aead_map.items():
        if raw.startswith(k):
            aead = v; raw = raw[len(k)+1:]; break
    for k, v in sig_map.items():
        if raw == k:
            sig = v; break
    return kem, aead, sig

def get_kem_family(kem):
    if not kem: return "Unknown"
    if "ML-KEM" in kem: return "ML-KEM"
    if "HQC" in kem: return "HQC"
    if "McEliece" in kem: return "Classic-McEliece"
    return "Unknown"

def load_scenario(scenario, run_id):
    d = RUNS_DIR / scenario
    suites = {}
    for f in sorted(d.glob(f"{run_id}_*_drone.json")):
        with open(f) as fh:
            data = json.load(fh)
        sid = data["run_context"]["suite_id"]
        suites[sid] = data
    return suites

def main():
    print("=" * 80)
    print("PRESENTATION DATA VERIFICATION AUDIT")
    print("=" * 80)

    # Load all data
    all_data = {}
    for sc, rid in SCENARIOS.items():
        all_data[sc] = load_scenario(sc, rid)
        print(f"  [{sc}] {len(all_data[sc])} suites loaded")

    baseline = all_data["no-ddos"]

    # ================================================================
    # 1. SUITE COUNT VERIFICATION
    # ================================================================
    print("\n" + "=" * 80)
    print("1. SUITE COUNT VERIFICATION")
    print("=" * 80)
    for sc, suites in all_data.items():
        print(f"  {sc}: {len(suites)} suites")
        levels = defaultdict(int)
        for sid, d in suites.items():
            lvl = d["crypto_identity"]["suite_security_level"]
            levels[lvl] += 1
        for l in sorted(levels): print(f"    {l}: {levels[l]}")
    print(f"  PPTX claims: 72 suites (L1:27, L3:18, L5:27)")

    # ================================================================
    # 2. KEM PRIMITIVE TIMES (Paper Table 3 / PPTX slide)
    # ================================================================
    print("\n" + "=" * 80)
    print("2. KEM PRIMITIVE TIMES (from benchmark data)")
    print("=" * 80)
    kems = ["ML-KEM-512", "ML-KEM-768", "ML-KEM-1024",
            "HQC-128", "HQC-192", "HQC-256",
            "Classic-McEliece-348864", "Classic-McEliece-460896", "Classic-McEliece-8192128"]
    
    print(f"  {'Algorithm':<30} {'Keygen(ms)':<12} {'Encaps(ms)':<12} {'Decaps(ms)':<12} {'PK(B)':<10}")
    print("  " + "-" * 76)
    for kem in kems:
        kg_times, enc_times, dec_times, pk_sizes = [], [], [], []
        for sid, d in baseline.items():
            k, _, _ = parse_suite_id(sid)
            if k == kem:
                cp = d.get("crypto_primitives", {})
                if cp.get("kem_keygen_time_ms"): kg_times.append(cp["kem_keygen_time_ms"])
                if cp.get("kem_encapsulation_time_ms"): enc_times.append(cp["kem_encapsulation_time_ms"])
                if cp.get("kem_decapsulation_time_ms"): dec_times.append(cp["kem_decapsulation_time_ms"])
                if cp.get("pub_key_size_bytes"): pk_sizes.append(cp["pub_key_size_bytes"])
        kg = np.median(kg_times) if kg_times else 0
        enc = np.median(enc_times) if enc_times else 0
        dec = np.median(dec_times) if dec_times else 0
        pk = pk_sizes[0] if pk_sizes else 0
        print(f"  {kem:<30} {kg:<12.4f} {enc:<12.4f} {dec:<12.4f} {pk:<10}")

    print("\n  Paper claims (Table 3):")
    print("  ML-KEM-512:  keygen=0.08, encaps=0.06, decaps=0.07, PK=800")
    print("  ML-KEM-768:  keygen=0.11, encaps=0.09, decaps=0.10, PK=1184")
    print("  ML-KEM-1024: keygen=0.14, encaps=0.12, decaps=0.14, PK=1568")
    print("  HQC-128:     keygen=22.1, encaps=44.7, decaps=73.0, PK=2249")
    print("  HQC-192:     keygen=67.4, encaps=135.4, decaps=211.2, PK=4522")
    print("  HQC-256:     keygen=123.6, encaps=248.8, decaps=392.3, PK=7245")
    print("  McE-348864:  keygen=333,  encaps=0.27, decaps=55.4, PK=261120")
    print("  McE-460896:  keygen=1115, encaps=0.64, decaps=89.4, PK=524160")
    print("  McE-8192128: keygen=8835, encaps=1.99, decaps=209, PK=1357824")

    # ================================================================
    # 3. SIGNATURE TIMES
    # ================================================================
    print("\n" + "=" * 80)
    print("3. SIGNATURE TIMES (from benchmark data)")
    print("=" * 80)
    sigs = ["ML-DSA-44", "ML-DSA-65", "ML-DSA-87",
            "Falcon-512", "Falcon-1024",
            "SPHINCS+-128s", "SPHINCS+-192s", "SPHINCS+-256s"]
    print(f"  {'Algorithm':<25} {'Sign(ms)':<12} {'Verify(ms)':<12} {'SigSize(B)':<12}")
    print("  " + "-" * 61)
    for sig in sigs:
        sign_times, ver_times, sig_sizes = [], [], []
        for sid, d in baseline.items():
            _, _, s = parse_suite_id(sid)
            if s == sig:
                cp = d.get("crypto_primitives", {})
                if cp.get("signature_sign_time_ms"): sign_times.append(cp["signature_sign_time_ms"])
                if cp.get("signature_verify_time_ms"): ver_times.append(cp["signature_verify_time_ms"])
                if cp.get("sig_size_bytes"): sig_sizes.append(cp["sig_size_bytes"])
        sgn = np.median(sign_times) if sign_times else 0
        ver = np.median(ver_times) if ver_times else 0
        ss = sig_sizes[0] if sig_sizes else 0
        print(f"  {sig:<25} {sgn:<12.4f} {ver:<12.4f} {ss:<12}")

    print("\n  Paper claims (Table 4):")
    print("  Falcon-512:    sign=0.65, verify=0.11, sig=655")
    print("  Falcon-1024:   sign=1.31, verify=0.20, sig=1273")
    print("  ML-DSA-44:     sign=1.03, verify=0.25, sig=2420")
    print("  ML-DSA-65:     sign=1.59, verify=0.38, sig=3293")
    print("  ML-DSA-87:     sign=1.77, verify=0.61, sig=4595")
    print("  SPHINCS+-128s: sign=1461, verify=1.49, sig=7856")
    print("  SPHINCS+-192s: sign=2611, verify=2.20, sig=16224")
    print("  SPHINCS+-256s: sign=2308, verify=3.12, sig=29792")

    # ================================================================
    # 4. AEAD TIMES
    # ================================================================
    print("\n" + "=" * 80)
    print("4. AEAD ENCRYPT/DECRYPT TIMES (from benchmark data)")
    print("=" * 80)
    aeads = ["AES-256-GCM", "ChaCha20-Poly1305", "Ascon-128a"]
    for aead in aeads:
        enc_ns, dec_ns = [], []
        for sid, d in baseline.items():
            _, a, _ = parse_suite_id(sid)
            if a == aead:
                dp = d.get("data_plane", {})
                if dp.get("aead_encrypt_avg_ns"): enc_ns.append(dp["aead_encrypt_avg_ns"])
                if dp.get("aead_decrypt_avg_ns"): dec_ns.append(dp["aead_decrypt_avg_ns"])
        enc_us = np.median(enc_ns)/1000 if enc_ns else 0
        dec_us = np.median(dec_ns)/1000 if dec_ns else 0
        print(f"  {aead:<25} Encrypt: {enc_us:.1f} µs    Decrypt: {dec_us:.1f} µs")

    print("\n  Paper claims: AES=7.3/7.7µs, ChaCha20=6.7/7.1µs, Ascon=4.1/4.2µs")

    # ================================================================
    # 5. END-TO-END HANDSHAKE TIMES
    # ================================================================
    print("\n" + "=" * 80)
    print("5. END-TO-END HANDSHAKE TIMES (baseline)")
    print("=" * 80)
    
    # By level
    level_times = defaultdict(list)
    for sid, d in baseline.items():
        lvl = d["crypto_identity"]["suite_security_level"]
        t = d.get("handshake", {}).get("handshake_total_duration_ms", 0)
        if t: level_times[lvl].append(t)
    
    print(f"  {'Level':<8} {'n':<5} {'Mean(ms)':<12} {'Median(ms)':<12} {'P95(ms)':<12} {'Max(ms)':<12}")
    print("  " + "-" * 61)
    for lvl in ["L1", "L3", "L5"]:
        vals = level_times[lvl]
        print(f"  {lvl:<8} {len(vals):<5} {np.mean(vals):<12.1f} {np.median(vals):<12.1f} "
              f"{np.percentile(vals,95):<12.1f} {np.max(vals):<12.1f}")
    
    print("\n  Paper claims (Table 5):")
    print("  L1: n=27, mean=290, median=123, P95=835, max=891")
    print("  L3: n=17, mean=749, median=416, P95=1583, max=1583")
    print("  L5: n=27, mean=855, median=870, P95=2364, max=3273")

    # By KEM family
    print(f"\n  Handshake by KEM Family (median):")
    for fam in ["ML-KEM", "HQC", "Classic-McEliece"]:
        times = []
        for sid, d in baseline.items():
            k, _, _ = parse_suite_id(sid)
            if get_kem_family(k) == fam:
                t = d.get("handshake", {}).get("handshake_total_duration_ms", 0)
                if t: times.append(t)
        print(f"    {fam:<20} median={np.median(times):.1f} ms, mean={np.mean(times):.1f} ms, n={len(times)}")

    # Specific Pareto suites
    print(f"\n  Pareto-optimal suite handshake times:")
    pareto_sids = [
        ("cs-mlkem512-aesgcm-falcon512",   "ML-KEM-512 + Falcon-512 (L1)",  9.1),
        ("cs-mlkem768-aesgcm-mldsa65",     "ML-KEM-768 + ML-DSA-65 (L3)",  17.7),
        ("cs-mlkem1024-aesgcm-falcon1024", "ML-KEM-1024 + Falcon-1024 (L5)", 10.1),
    ]
    for sid, label, paper_val in pareto_sids:
        if sid in baseline:
            actual = baseline[sid]["handshake"]["handshake_total_duration_ms"]
            match = "✓" if abs(actual - paper_val) < paper_val * 0.5 else "✗ MISMATCH"
            print(f"    {label:<40} actual={actual:.2f} ms, paper={paper_val} ms  {match}")

    # ================================================================
    # 6. SYSTEM METRICS ACROSS SCENARIOS
    # ================================================================
    print("\n" + "=" * 80)
    print("6. SYSTEM METRICS ACROSS SCENARIOS")
    print("=" * 80)
    for sc, suites in all_data.items():
        cpus = [d["system_drone"]["cpu_usage_avg_percent"] for d in suites.values()
                if d.get("system_drone", {}).get("cpu_usage_avg_percent") is not None]
        temps = [d["system_drone"]["temperature_c"] for d in suites.values()
                 if d.get("system_drone", {}).get("temperature_c") is not None]
        pkts = [d["data_plane"]["packets_sent"] for d in suites.values()
                if d.get("data_plane", {}).get("packets_sent")]
        loss = [d["data_plane"]["packet_loss_ratio"] for d in suites.values()
                if d.get("data_plane", {}).get("packet_loss_ratio") is not None]
        hs = [d["handshake"]["handshake_total_duration_ms"] for d in suites.values()
              if d.get("handshake", {}).get("handshake_total_duration_ms")]
        
        print(f"  [{sc}]")
        print(f"    CPU avg:  {np.mean(cpus):.1f}%    Temp avg: {np.mean(temps):.1f}°C")
        print(f"    Packets sent (median): {int(np.median(pkts))}   Loss: {np.mean(loss)*100:.2f}%")
        print(f"    Handshake: median={np.median(hs):.1f}, mean={np.mean(hs):.1f}, P95={np.percentile(hs,95):.1f}")

    # ================================================================
    # 7. OVERHEAD DELTA BETWEEN SCENARIOS
    # ================================================================
    print("\n" + "=" * 80)
    print("7. OVERHEAD DELTA (handshake time vs baseline)")
    print("=" * 80)
    for compare_sc in ["ddos-xgboost", "ddos-txt"]:
        print(f"\n  [{compare_sc} vs no-ddos]:")
        for fam in ["ML-KEM", "HQC", "Classic-McEliece"]:
            base_times, comp_times = [], []
            for sid in baseline:
                k, _, _ = parse_suite_id(sid)
                if get_kem_family(k) == fam and sid in all_data[compare_sc]:
                    bt = baseline[sid]["handshake"]["handshake_total_duration_ms"]
                    ct = all_data[compare_sc][sid]["handshake"]["handshake_total_duration_ms"]
                    if bt and ct:
                        base_times.append(bt)
                        comp_times.append(ct)
            if base_times:
                bm = np.median(base_times)
                cm = np.median(comp_times)
                delta = cm - bm
                pct = (delta / bm) * 100
                print(f"    {fam:<20} base_med={bm:.1f}, comp_med={cm:.1f}, Δ={delta:+.1f} ms ({pct:+.1f}%)")

    # ================================================================
    # 8. REKEY OVERHEAD VERIFICATION
    # ================================================================
    print("\n" + "=" * 80)
    print("8. REKEY OVERHEAD Φ(R) VERIFICATION")
    print("=" * 80)
    rekey_suites = {
        "cs-mlkem768-aesgcm-mldsa65": ("ML-KEM-768", 17.7),
        "cs-hqc256-aesgcm-falcon1024": ("HQC-256", 272),
        "cs-classicmceliece348864-aesgcm-falcon512": ("McE-348864", 120),
        "cs-classicmceliece8192128-aesgcm-mldsa87": ("McE-8192128", 517),
    }
    R_vals = [60, 300, 3600]
    for sid, (name, paper_ths) in rekey_suites.items():
        if sid in baseline:
            actual_ths = baseline[sid]["handshake"]["handshake_total_duration_ms"]
            print(f"  {name}: actual T_hs = {actual_ths:.2f} ms (paper: {paper_ths} ms)")
            for R in R_vals:
                phi = (actual_ths / 1000) / (R + actual_ths / 1000) * 100
                print(f"    R={R}s: Φ = {phi:.4f}%")

    # ================================================================
    # 9. HANDSHAKE SUCCESS CHECK
    # ================================================================
    print("\n" + "=" * 80)
    print("9. HANDSHAKE SUCCESS/FAILURE COUNT")
    print("=" * 80)
    for sc, suites in all_data.items():
        success = sum(1 for d in suites.values() if d["handshake"].get("handshake_success"))
        total = len(suites)
        print(f"  [{sc}] {success}/{total} succeeded")

    # ================================================================
    # 10. SPECIFIC DATA POINTS CROSS-CHECK
    # ================================================================
    print("\n" + "=" * 80)
    print("10. SPECIFIC NUMBERS CROSS-CHECK")
    print("=" * 80)
    
    # ML-KEM suite without SPHINCS+
    mlkem_no_sphincs = []
    for sid, d in baseline.items():
        k, _, s = parse_suite_id(sid)
        if get_kem_family(k) == "ML-KEM" and "SPHINCS" not in (s or ""):
            t = d["handshake"]["handshake_total_duration_ms"]
            mlkem_no_sphincs.append(t)
    print(f"  ML-KEM suites (excl SPHINCS+): max handshake = {max(mlkem_no_sphincs):.1f} ms")
    print(f"    PPTX claims: < 22 ms")
    
    # Packet counts
    all_pkts = [d["data_plane"]["packets_sent"] for d in baseline.values()]
    print(f"  Packets sent range: {min(all_pkts)} - {max(all_pkts)}, median={int(np.median(all_pkts))}")
    
    # PK size ratio
    mlkem512_pk = 800
    mce_pk = 1357824
    print(f"  PK size ratio McE-8192128/ML-KEM-512 = {mce_pk/mlkem512_pk:.0f}×  (paper: 867×)")
    print(f"    Corrected: {mce_pk}/{mlkem512_pk} = {mce_pk/mlkem512_pk:.0f}")

    # 29x rekey difference check
    if "cs-mlkem768-aesgcm-mldsa65" in baseline and "cs-classicmceliece8192128-aesgcm-mldsa87" in baseline:
        mlkem_ths = baseline["cs-mlkem768-aesgcm-mldsa65"]["handshake"]["handshake_total_duration_ms"]
        mce_ths = baseline["cs-classicmceliece8192128-aesgcm-mldsa87"]["handshake"]["handshake_total_duration_ms"]
        phi_ml = (mlkem_ths/1000)/(60+mlkem_ths/1000)*100
        phi_mc = (mce_ths/1000)/(60+mce_ths/1000)*100
        ratio = phi_mc / phi_ml if phi_ml else 0
        print(f"  Rekey ratio: ML-KEM Φ={phi_ml:.4f}%, McE Φ={phi_mc:.4f}%, ratio={ratio:.1f}×  (paper: 29×)")

    print("\n" + "=" * 80)
    print("AUDIT COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
