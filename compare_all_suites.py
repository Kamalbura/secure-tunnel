#!/usr/bin/env python3
"""
Comprehensive Suite-by-Suite Comparison across all 3 E2E Benchmark Scenarios.

Reads all JSON files from:
  logs/benchmarks/runs/no-ddos/
  logs/benchmarks/runs/ddos-xgboost/
  logs/benchmarks/runs/ddos-txt/

Produces:
  1. A wide CSV with every metric for every suite × scenario
  2. A condensed markdown comparison table
  3. A per-family summary
  4. A delta / overhead analysis (how much each detector adds)
"""

import json, os, glob, csv, sys
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).parent
RUNS_DIR = ROOT / "logs" / "benchmarks" / "runs"

SCENARIOS = {
    "no-ddos":       "Baseline (No DDoS)",
    "ddos-xgboost":  "XGBoost Detector",
    "ddos-txt":      "TST Detector",
}

# ── helpers ──────────────────────────────────────────────────────────────
def safe(val, fmt=".2f", default="—"):
    if val is None:
        return default
    try:
        return f"{val:{fmt}}"
    except (ValueError, TypeError):
        return str(val)

def deep_merge(base: dict, overlay: dict, protected_keys: set = None) -> dict:
    """Merge overlay into base.
    
    - Never overwrite non-None with None.
    - Keys in protected_keys are NEVER overwritten from overlay
      (drone is the authority for handshake, crypto_primitives, lifecycle).
    """
    if protected_keys is None:
        protected_keys = set()
    merged = dict(base)
    for k, v in overlay.items():
        if k in protected_keys:
            continue  # drone is authoritative for these sections
        if k not in merged:
            merged[k] = v
        elif isinstance(v, dict) and isinstance(merged[k], dict):
            merged[k] = deep_merge(merged[k], v)
        elif v is not None:
            merged[k] = v
    return merged


# Sections where the DRONE file is authoritative.
# GCS reports handshake_total_duration_ms as scheduler-tick time (~2000ms)
# which is NOT the real PQC protocol handshake.
DRONE_AUTHORITATIVE = {
    "handshake", "crypto_primitives", "lifecycle",
    "mavproxy_drone", "system_drone", "power_energy",
    "fc_telemetry", "mavlink_integrity",
}


def load_jsons(scenario_dir: Path):
    """Return dict[suite_id] = merged drone+gcs data.
    
    Drone file is loaded first (has handshake, crypto_primitives, system_drone, etc).
    GCS file is deep-merged on top (adds system_gcs, mavproxy_gcs) but 
    NEVER overwrites drone-authoritative sections (handshake, crypto, etc.).
    
    The GCS handshake_total_duration_ms is actually the scheduler tick
    interval (~2000ms), not the real PQC handshake time, so we must
    always prefer the drone-side measurement.
    """
    suites = {}
    # Sort so that drone files come before gcs files (d < g alphabetically)
    for f in sorted(scenario_dir.glob("*.json")):
        data = json.loads(f.read_text(encoding="utf-8"))
        ctx = data.get("run_context", {})
        suite_id = ctx.get("suite_id", "")
        if not suite_id:
            continue
        if suite_id not in suites:
            suites[suite_id] = data
        else:
            # Second file is GCS — merge but protect drone-authoritative fields
            suites[suite_id] = deep_merge(suites[suite_id], data,
                                          protected_keys=DRONE_AUTHORITATIVE)
    return suites


def extract_metrics(d: dict) -> dict:
    """Pull flat metrics from a merged suite dict."""
    crypto   = d.get("crypto_identity", {})
    hs       = d.get("handshake", {})
    cp       = d.get("crypto_primitives", {})
    dp       = d.get("data_plane", {})
    lj       = d.get("latency_jitter", {})
    sd       = d.get("system_drone", {})
    sg       = d.get("system_gcs", {})
    pe       = d.get("power_energy", {})
    mp_d     = d.get("mavproxy_drone", {})
    mp_g     = d.get("mavproxy_gcs", {})
    mi       = d.get("mavlink_integrity", {})
    fc       = d.get("fc_telemetry", {})
    lc       = d.get("lifecycle", {})
    val      = d.get("validation", {})

    return {
        # Identity
        "KEM":            crypto.get("kem_algorithm", ""),
        "KEM Family":     crypto.get("kem_family", ""),
        "KEM NIST":       crypto.get("kem_nist_level", ""),
        "SIG":            crypto.get("sig_algorithm", ""),
        "SIG Family":     crypto.get("sig_family", ""),
        "SIG NIST":       crypto.get("sig_nist_level", ""),
        "AEAD":           crypto.get("aead_algorithm", ""),
        "Security Level": crypto.get("suite_security_level", ""),

        # Handshake
        "Handshake ms":       hs.get("handshake_total_duration_ms"),
        "Handshake OK":       hs.get("handshake_success"),

        # Crypto primitives
        "KEM Keygen ms":      cp.get("kem_keygen_time_ms"),
        "KEM Encaps ms":      cp.get("kem_encapsulation_time_ms"),
        "KEM Decaps ms":      cp.get("kem_decapsulation_time_ms"),
        "SIG Sign ms":        cp.get("signature_sign_time_ms"),
        "SIG Verify ms":      cp.get("signature_verify_time_ms"),
        "Total Crypto ms":    cp.get("total_crypto_time_ms"),
        "PubKey Bytes":       cp.get("pub_key_size_bytes"),
        "Ciphertext Bytes":   cp.get("ciphertext_size_bytes"),
        "SIG Bytes":          cp.get("sig_size_bytes"),

        # Data plane
        "Throughput Mbps":    dp.get("achieved_throughput_mbps"),
        "Goodput Mbps":       dp.get("goodput_mbps"),
        "Wire Rate Mbps":     dp.get("wire_rate_mbps"),
        "Pkts Sent":          dp.get("packets_sent"),
        "Pkts Received":      dp.get("packets_received"),
        "Pkt Loss %":         (dp.get("packet_loss_ratio") or 0) * 100,
        "Bytes Sent":         dp.get("bytes_sent"),
        "Bytes Received":     dp.get("bytes_received"),
        "AEAD Enc Avg ns":    dp.get("aead_encrypt_avg_ns"),
        "AEAD Dec Avg ns":    dp.get("aead_decrypt_avg_ns"),
        "AEAD Enc Count":     dp.get("aead_encrypt_count"),
        "AEAD Dec Count":     dp.get("aead_decrypt_count"),

        # Lifecycle
        "Suite Total ms":     lc.get("suite_total_duration_ms"),
        "Suite Active ms":    lc.get("suite_active_duration_ms"),

        # System – Drone
        "Drone CPU Avg %":    sd.get("cpu_usage_avg_percent"),
        "Drone CPU Peak %":   sd.get("cpu_usage_peak_percent"),
        "Drone CPU MHz":      sd.get("cpu_freq_mhz"),
        "Drone Mem RSS MB":   sd.get("memory_rss_mb"),
        "Drone Temp °C":      sd.get("temperature_c"),
        "Drone Load 1m":      sd.get("load_avg_1m"),

        # System – GCS
        "GCS CPU Avg %":      sg.get("cpu_usage_avg_percent"),
        "GCS CPU Peak %":     sg.get("cpu_usage_peak_percent"),
        "GCS CPU MHz":        sg.get("cpu_freq_mhz"),
        "GCS Mem RSS MB":     sg.get("memory_rss_mb"),
        "GCS Temp °C":        sg.get("temperature_c"),

        # Power
        "Power Avg W":        pe.get("power_avg_w"),
        "Power Peak W":       pe.get("power_peak_w"),
        "Energy Total J":     pe.get("energy_total_j"),
        "Energy/HS J":        pe.get("energy_per_handshake_j"),

        # MAVProxy drone
        "MAV Drone Msgs RX":  mp_d.get("mavproxy_drone_total_msgs_received"),
        "MAV Drone RX pps":   mp_d.get("mavproxy_drone_rx_pps"),
        "MAV Drone HB ms":    mp_d.get("mavproxy_drone_heartbeat_interval_ms"),
        "MAV Drone SeqGap":   mp_d.get("mavproxy_drone_seq_gap_count"),
        "MAV Drone StreamHz": mp_d.get("mavproxy_drone_stream_rate_hz"),

        # MAVProxy GCS
        "MAV GCS Msgs RX":    mp_g.get("mavproxy_gcs_total_msgs_received"),
        "MAV GCS SeqGap":     mp_g.get("mavproxy_gcs_seq_gap_count"),

        # MAVLink integrity
        "MAVLink CRC Err":    mi.get("mavlink_packet_crc_error_count"),
        "MAVLink Decode Err": mi.get("mavlink_decode_error_count"),
        "MAVLink Drop":       mi.get("mavlink_msg_drop_count"),
        "MAVLink OOO":        mi.get("mavlink_out_of_order_count"),
        "MAVLink Dup":        mi.get("mavlink_duplicate_count"),

        # FC telemetry
        "FC Mode":            fc.get("fc_mode"),
        "FC Armed":           fc.get("fc_armed_state"),
        "FC Bat V":           fc.get("fc_battery_voltage_v"),
        "FC Bat A":           fc.get("fc_battery_current_a"),
        "FC CPU %":           fc.get("fc_cpu_load_percent"),

        # Validation
        "Pass/Fail":          val.get("benchmark_pass_fail", ""),
    }


# ── main ─────────────────────────────────────────────────────────────────
def main():
    # Load all scenarios
    all_data = {}  # scenario -> {suite_id -> metrics}
    for scen in SCENARIOS:
        sdir = RUNS_DIR / scen
        if not sdir.exists():
            print(f"⚠  Missing scenario dir: {sdir}")
            continue
        raw = load_jsons(sdir)
        all_data[scen] = {sid: extract_metrics(d) for sid, d in raw.items()}
        print(f"✔  {scen}: {len(all_data[scen])} suites loaded")

    # Get all unique suite IDs sorted
    all_suites = sorted(set().union(*(d.keys() for d in all_data.values())))
    print(f"\nTotal unique suites: {len(all_suites)}")

    # Get all metric keys (from first available entry)
    sample = next(iter(next(iter(all_data.values())).values()))
    metric_keys = list(sample.keys())

    # ─── 1. Full CSV ────────────────────────────────────────────────────
    csv_path = ROOT / "suite_comparison_full.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        # Header
        header = ["Suite ID"]
        for scen, label in SCENARIOS.items():
            for mk in metric_keys:
                header.append(f"{label} | {mk}")
        w.writerow(header)

        for sid in all_suites:
            row = [sid]
            for scen in SCENARIOS:
                m = all_data.get(scen, {}).get(sid, {})
                for mk in metric_keys:
                    row.append(m.get(mk, ""))
            w.writerow(row)

    print(f"✔  Full CSV: {csv_path}")

    # ─── 2. Condensed Markdown ──────────────────────────────────────────
    md_path = ROOT / "suite_comparison.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# E2E Benchmark — Full Suite-by-Suite Comparison\n\n")
        f.write(f"**Date**: 2026-02-11  |  **Suites**: {len(all_suites)}  |  ")
        f.write(f"**Scenarios**: {', '.join(SCENARIOS.values())}\n\n")

        # ─── 2a. Handshake + Crypto Table ───────────────────────────────
        f.write("## 1. Handshake & Crypto Primitives\n\n")
        cols = [
            "Suite", 
            "KEM", "SIG", "AEAD", "Level",
            "HS (Base) ms", "HS (XGB) ms", "HS (TST) ms",
            "Δ XGB %", "Δ TST %",
            "KEM Keygen ms", "KEM Encaps ms", "KEM Decaps ms",
            "SIG Sign ms", "SIG Verify ms", "Total Crypto ms",
            "PubKey B", "CT B", "SIG B",
        ]
        f.write("| " + " | ".join(cols) + " |\n")
        f.write("| " + " | ".join(["---"] * len(cols)) + " |\n")

        for sid in all_suites:
            base = all_data.get("no-ddos", {}).get(sid, {})
            xgb  = all_data.get("ddos-xgboost", {}).get(sid, {})
            tst  = all_data.get("ddos-txt", {}).get(sid, {})

            hs_b = base.get("Handshake ms")
            hs_x = xgb.get("Handshake ms")
            hs_t = tst.get("Handshake ms")

            delta_x = ((hs_x - hs_b) / hs_b * 100) if hs_b and hs_x and hs_b > 0 else None
            delta_t = ((hs_t - hs_b) / hs_b * 100) if hs_b and hs_t and hs_b > 0 else None

            short_id = sid.replace("cs-", "").replace("classicmceliece", "mce")
            row = [
                short_id,
                base.get("KEM", ""),
                base.get("SIG", ""),
                base.get("AEAD", ""),
                base.get("Security Level", ""),
                safe(hs_b),
                safe(hs_x),
                safe(hs_t),
                safe(delta_x, "+.1f") if delta_x is not None else "—",
                safe(delta_t, "+.1f") if delta_t is not None else "—",
                safe(base.get("KEM Keygen ms")),
                safe(base.get("KEM Encaps ms")),
                safe(base.get("KEM Decaps ms")),
                safe(base.get("SIG Sign ms")),
                safe(base.get("SIG Verify ms")),
                safe(base.get("Total Crypto ms")),
                safe(base.get("PubKey Bytes"), "d"),
                safe(base.get("Ciphertext Bytes"), "d"),
                safe(base.get("SIG Bytes"), "d"),
            ]
            f.write("| " + " | ".join(str(x) for x in row) + " |\n")

        # ─── 2b. Data Plane Table ───────────────────────────────────────
        f.write("\n## 2. Data Plane & Throughput\n\n")
        cols = [
            "Suite",
            "Tput (Base) Mbps", "Tput (XGB) Mbps", "Tput (TST) Mbps",
            "Goodput (Base)", "Goodput (XGB)", "Goodput (TST)",
            "Pkts Sent (B)", "Pkts Sent (X)", "Pkts Sent (T)",
            "Pkts Recv (B)", "Pkts Recv (X)", "Pkts Recv (T)",
            "Loss (B) %", "Loss (X) %", "Loss (T) %",
            "AEAD Enc ns (B)", "AEAD Enc ns (X)", "AEAD Enc ns (T)",
        ]
        f.write("| " + " | ".join(cols) + " |\n")
        f.write("| " + " | ".join(["---"] * len(cols)) + " |\n")

        for sid in all_suites:
            base = all_data.get("no-ddos", {}).get(sid, {})
            xgb  = all_data.get("ddos-xgboost", {}).get(sid, {})
            tst  = all_data.get("ddos-txt", {}).get(sid, {})
            short_id = sid.replace("cs-", "").replace("classicmceliece", "mce")
            row = [
                short_id,
                safe(base.get("Throughput Mbps"), ".4f"),
                safe(xgb.get("Throughput Mbps"), ".4f"),
                safe(tst.get("Throughput Mbps"), ".4f"),
                safe(base.get("Goodput Mbps"), ".4f"),
                safe(xgb.get("Goodput Mbps"), ".4f"),
                safe(tst.get("Goodput Mbps"), ".4f"),
                safe(base.get("Pkts Sent"), "d"),
                safe(xgb.get("Pkts Sent"), "d"),
                safe(tst.get("Pkts Sent"), "d"),
                safe(base.get("Pkts Received"), "d"),
                safe(xgb.get("Pkts Received"), "d"),
                safe(tst.get("Pkts Received"), "d"),
                safe(base.get("Pkt Loss %")),
                safe(xgb.get("Pkt Loss %")),
                safe(tst.get("Pkt Loss %")),
                safe(base.get("AEAD Enc Avg ns"), "d"),
                safe(xgb.get("AEAD Enc Avg ns"), "d"),
                safe(tst.get("AEAD Enc Avg ns"), "d"),
            ]
            f.write("| " + " | ".join(str(x) for x in row) + " |\n")

        # ─── 2c. System Resources Table ─────────────────────────────────
        f.write("\n## 3. System Resources (Drone Pi + GCS)\n\n")
        cols = [
            "Suite",
            "D CPU% (B)", "D CPU% (X)", "D CPU% (T)",
            "D Peak% (B)", "D Peak% (X)", "D Peak% (T)",
            "D Temp°C (B)", "D Temp°C (X)", "D Temp°C (T)",
            "D Mem MB (B)", "D Mem MB (X)", "D Mem MB (T)",
            "G CPU% (B)", "G CPU% (X)", "G CPU% (T)",
            "G Peak% (B)", "G Peak% (X)", "G Peak% (T)",
            "G Mem MB (B)", "G Mem MB (X)", "G Mem MB (T)",
        ]
        f.write("| " + " | ".join(cols) + " |\n")
        f.write("| " + " | ".join(["---"] * len(cols)) + " |\n")

        for sid in all_suites:
            base = all_data.get("no-ddos", {}).get(sid, {})
            xgb  = all_data.get("ddos-xgboost", {}).get(sid, {})
            tst  = all_data.get("ddos-txt", {}).get(sid, {})
            short_id = sid.replace("cs-", "").replace("classicmceliece", "mce")
            row = [
                short_id,
                safe(base.get("Drone CPU Avg %")),
                safe(xgb.get("Drone CPU Avg %")),
                safe(tst.get("Drone CPU Avg %")),
                safe(base.get("Drone CPU Peak %")),
                safe(xgb.get("Drone CPU Peak %")),
                safe(tst.get("Drone CPU Peak %")),
                safe(base.get("Drone Temp °C")),
                safe(xgb.get("Drone Temp °C")),
                safe(tst.get("Drone Temp °C")),
                safe(base.get("Drone Mem RSS MB")),
                safe(xgb.get("Drone Mem RSS MB")),
                safe(tst.get("Drone Mem RSS MB")),
                safe(base.get("GCS CPU Avg %")),
                safe(xgb.get("GCS CPU Avg %")),
                safe(tst.get("GCS CPU Avg %")),
                safe(base.get("GCS CPU Peak %")),
                safe(xgb.get("GCS CPU Peak %")),
                safe(tst.get("GCS CPU Peak %")),
                safe(base.get("GCS Mem RSS MB")),
                safe(xgb.get("GCS Mem RSS MB")),
                safe(tst.get("GCS Mem RSS MB")),
            ]
            f.write("| " + " | ".join(str(x) for x in row) + " |\n")

        # ─── 2d. MAVProxy & MAVLink Integrity ───────────────────────────
        f.write("\n## 4. MAVProxy & MAVLink Integrity\n\n")
        cols = [
            "Suite",
            "D Msgs (B)", "D Msgs (X)", "D Msgs (T)",
            "D RX pps (B)", "D RX pps (X)", "D RX pps (T)",
            "D HB ms (B)", "D HB ms (X)", "D HB ms (T)",
            "D SeqGap (B)", "D SeqGap (X)", "D SeqGap (T)",
            "D StreamHz (B)", "D StreamHz (X)", "D StreamHz (T)",
            "G Msgs (B)", "G Msgs (X)", "G Msgs (T)",
            "CRC Err (B)", "CRC Err (X)", "CRC Err (T)",
            "Drop (B)", "Drop (X)", "Drop (T)",
        ]
        f.write("| " + " | ".join(cols) + " |\n")
        f.write("| " + " | ".join(["---"] * len(cols)) + " |\n")

        for sid in all_suites:
            base = all_data.get("no-ddos", {}).get(sid, {})
            xgb  = all_data.get("ddos-xgboost", {}).get(sid, {})
            tst  = all_data.get("ddos-txt", {}).get(sid, {})
            short_id = sid.replace("cs-", "").replace("classicmceliece", "mce")
            row = [
                short_id,
                safe(base.get("MAV Drone Msgs RX"), "d"),
                safe(xgb.get("MAV Drone Msgs RX"), "d"),
                safe(tst.get("MAV Drone Msgs RX"), "d"),
                safe(base.get("MAV Drone RX pps")),
                safe(xgb.get("MAV Drone RX pps")),
                safe(tst.get("MAV Drone RX pps")),
                safe(base.get("MAV Drone HB ms")),
                safe(xgb.get("MAV Drone HB ms")),
                safe(tst.get("MAV Drone HB ms")),
                safe(base.get("MAV Drone SeqGap"), "d"),
                safe(xgb.get("MAV Drone SeqGap"), "d"),
                safe(tst.get("MAV Drone SeqGap"), "d"),
                safe(base.get("MAV Drone StreamHz")),
                safe(xgb.get("MAV Drone StreamHz")),
                safe(tst.get("MAV Drone StreamHz")),
                safe(base.get("MAV GCS Msgs RX"), "d"),
                safe(xgb.get("MAV GCS Msgs RX"), "d"),
                safe(tst.get("MAV GCS Msgs RX"), "d"),
                safe(base.get("MAVLink CRC Err"), "d"),
                safe(xgb.get("MAVLink CRC Err"), "d"),
                safe(tst.get("MAVLink CRC Err"), "d"),
                safe(base.get("MAVLink Drop"), "d"),
                safe(xgb.get("MAVLink Drop"), "d"),
                safe(tst.get("MAVLink Drop"), "d"),
            ]
            f.write("| " + " | ".join(str(x) for x in row) + " |\n")

        # ─── 2e. Power & Energy ─────────────────────────────────────────
        f.write("\n## 5. Power & Energy\n\n")
        cols = [
            "Suite",
            "Pwr W (B)", "Pwr W (X)", "Pwr W (T)",
            "Peak W (B)", "Peak W (X)", "Peak W (T)",
            "Energy J (B)", "Energy J (X)", "Energy J (T)",
            "E/HS J (B)", "E/HS J (X)", "E/HS J (T)",
        ]
        f.write("| " + " | ".join(cols) + " |\n")
        f.write("| " + " | ".join(["---"] * len(cols)) + " |\n")

        for sid in all_suites:
            base = all_data.get("no-ddos", {}).get(sid, {})
            xgb  = all_data.get("ddos-xgboost", {}).get(sid, {})
            tst  = all_data.get("ddos-txt", {}).get(sid, {})
            short_id = sid.replace("cs-", "").replace("classicmceliece", "mce")
            row = [
                short_id,
                safe(base.get("Power Avg W"), ".3f"),
                safe(xgb.get("Power Avg W"), ".3f"),
                safe(tst.get("Power Avg W"), ".3f"),
                safe(base.get("Power Peak W"), ".3f"),
                safe(xgb.get("Power Peak W"), ".3f"),
                safe(tst.get("Power Peak W"), ".3f"),
                safe(base.get("Energy Total J"), ".3f"),
                safe(xgb.get("Energy Total J"), ".3f"),
                safe(tst.get("Energy Total J"), ".3f"),
                safe(base.get("Energy/HS J"), ".3f"),
                safe(xgb.get("Energy/HS J"), ".3f"),
                safe(tst.get("Energy/HS J"), ".3f"),
            ]
            f.write("| " + " | ".join(str(x) for x in row) + " |\n")

        # ─── 2f. Lifecycle & Validation ─────────────────────────────────
        f.write("\n## 6. Lifecycle & Validation\n\n")
        cols = [
            "Suite",
            "Total ms (B)", "Total ms (X)", "Total ms (T)",
            "Active ms (B)", "Active ms (X)", "Active ms (T)",
            "Result (B)", "Result (X)", "Result (T)",
        ]
        f.write("| " + " | ".join(cols) + " |\n")
        f.write("| " + " | ".join(["---"] * len(cols)) + " |\n")

        for sid in all_suites:
            base = all_data.get("no-ddos", {}).get(sid, {})
            xgb  = all_data.get("ddos-xgboost", {}).get(sid, {})
            tst  = all_data.get("ddos-txt", {}).get(sid, {})
            short_id = sid.replace("cs-", "").replace("classicmceliece", "mce")
            row = [
                short_id,
                safe(base.get("Suite Total ms")),
                safe(xgb.get("Suite Total ms")),
                safe(tst.get("Suite Total ms")),
                safe(base.get("Suite Active ms")),
                safe(xgb.get("Suite Active ms")),
                safe(tst.get("Suite Active ms")),
                base.get("Pass/Fail", "—"),
                xgb.get("Pass/Fail", "—"),
                tst.get("Pass/Fail", "—"),
            ]
            f.write("| " + " | ".join(str(x) for x in row) + " |\n")

        # ─── 3. Summary by KEM Family ──────────────────────────────────
        f.write("\n## 7. Summary by KEM Family\n\n")
        family_stats = defaultdict(lambda: defaultdict(list))
        for scen in SCENARIOS:
            for sid, m in all_data.get(scen, {}).items():
                fam = m.get("KEM Family", "unknown")
                hs = m.get("Handshake ms")
                if hs is not None:
                    family_stats[(fam, scen)]["hs"].append(hs)
                cpu = m.get("Drone CPU Avg %")
                if cpu is not None:
                    family_stats[(fam, scen)]["cpu"].append(cpu)
                temp = m.get("Drone Temp °C")
                if temp is not None:
                    family_stats[(fam, scen)]["temp"].append(temp)

        families = sorted(set(k[0] for k in family_stats))
        cols = ["KEM Family",
                "Avg HS (B) ms", "Avg HS (X) ms", "Avg HS (T) ms",
                "Avg CPU (B) %", "Avg CPU (X) %", "Avg CPU (T) %",
                "Avg Temp (B)°C", "Avg Temp (X)°C", "Avg Temp (T)°C"]
        f.write("| " + " | ".join(cols) + " |\n")
        f.write("| " + " | ".join(["---"] * len(cols)) + " |\n")

        for fam in families:
            vals = {}
            for scen in SCENARIOS:
                s = family_stats.get((fam, scen), {})
                hs_list = s.get("hs", [])
                cpu_list = s.get("cpu", [])
                temp_list = s.get("temp", [])
                vals[(scen, "hs")] = sum(hs_list)/len(hs_list) if hs_list else None
                vals[(scen, "cpu")] = sum(cpu_list)/len(cpu_list) if cpu_list else None
                vals[(scen, "temp")] = sum(temp_list)/len(temp_list) if temp_list else None

            scens = list(SCENARIOS.keys())
            row = [
                fam,
                safe(vals[(scens[0], "hs")]),
                safe(vals[(scens[1], "hs")]),
                safe(vals[(scens[2], "hs")]),
                safe(vals[(scens[0], "cpu")]),
                safe(vals[(scens[1], "cpu")]),
                safe(vals[(scens[2], "cpu")]),
                safe(vals[(scens[0], "temp")]),
                safe(vals[(scens[1], "temp")]),
                safe(vals[(scens[2], "temp")]),
            ]
            f.write("| " + " | ".join(str(x) for x in row) + " |\n")

        # ─── 4. Overhead Summary ────────────────────────────────────────
        f.write("\n## 8. DDoS Detector Overhead Summary\n\n")
        f.write("| Metric | XGBoost Δ (avg) | TST Δ (avg) |\n")
        f.write("| --- | --- | --- |\n")

        # Compute averages across all suites
        for metric_name, key in [
            ("Handshake Time", "Handshake ms"),
            ("Drone CPU Avg", "Drone CPU Avg %"),
            ("Drone CPU Peak", "Drone CPU Peak %"),
            ("Drone Temp", "Drone Temp °C"),
            ("GCS CPU Avg", "GCS CPU Avg %"),
            ("Throughput", "Throughput Mbps"),
            ("Drone Mem RSS", "Drone Mem RSS MB"),
        ]:
            base_vals = [m[key] for m in all_data.get("no-ddos", {}).values() if m.get(key) is not None]
            xgb_vals  = [m[key] for m in all_data.get("ddos-xgboost", {}).values() if m.get(key) is not None]
            tst_vals  = [m[key] for m in all_data.get("ddos-txt", {}).values() if m.get(key) is not None]

            avg_b = sum(base_vals)/len(base_vals) if base_vals else 0
            avg_x = sum(xgb_vals)/len(xgb_vals) if xgb_vals else 0
            avg_t = sum(tst_vals)/len(tst_vals) if tst_vals else 0

            if avg_b != 0:
                delta_x = (avg_x - avg_b) / avg_b * 100
                delta_t = (avg_t - avg_b) / avg_b * 100
                f.write(f"| {metric_name} | {avg_x:.2f} ({delta_x:+.1f}%) | {avg_t:.2f} ({delta_t:+.1f}%) |\n")
            else:
                f.write(f"| {metric_name} | {avg_x:.2f} | {avg_t:.2f} |\n")

        f.write("\n---\n*Generated by compare_all_suites.py*\n")

    print(f"✔  Markdown: {md_path}")

    # ─── 3. Per-suite Delta CSV ─────────────────────────────────────────
    delta_path = ROOT / "suite_comparison_delta.csv"
    key_metrics = [
        "Handshake ms", "Total Crypto ms",
        "Throughput Mbps", "Pkt Loss %",
        "Drone CPU Avg %", "Drone CPU Peak %", "Drone Temp °C",
        "GCS CPU Avg %", "GCS CPU Peak %",
        "MAV Drone Msgs RX", "MAV Drone StreamHz",
        "Power Avg W", "Energy Total J",
        "Suite Active ms",
    ]
    with open(delta_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        header = ["Suite", "KEM", "SIG", "AEAD", "Level"]
        for mk in key_metrics:
            header += [f"Base {mk}", f"XGB {mk}", f"TST {mk}", f"Δ XGB %", f"Δ TST %"]
        w.writerow(header)

        for sid in all_suites:
            base = all_data.get("no-ddos", {}).get(sid, {})
            xgb  = all_data.get("ddos-xgboost", {}).get(sid, {})
            tst  = all_data.get("ddos-txt", {}).get(sid, {})

            row = [sid, base.get("KEM",""), base.get("SIG",""), base.get("AEAD",""), base.get("Security Level","")]
            for mk in key_metrics:
                vb = base.get(mk)
                vx = xgb.get(mk)
                vt = tst.get(mk)
                row.append(vb if vb is not None else "")
                row.append(vx if vx is not None else "")
                row.append(vt if vt is not None else "")
                # Delta %
                if vb and vx and isinstance(vb, (int, float)) and vb != 0:
                    row.append(f"{(vx-vb)/vb*100:+.2f}")
                else:
                    row.append("")
                if vb and vt and isinstance(vb, (int, float)) and vb != 0:
                    row.append(f"{(vt-vb)/vb*100:+.2f}")
                else:
                    row.append("")
            w.writerow(row)

    print(f"✔  Delta CSV: {delta_path}")
    print("\nDone! Files generated:")
    print(f"  1. {csv_path.name}       — every metric, every suite, every scenario")
    print(f"  2. {md_path.name}     — readable markdown with 8 comparison tables")
    print(f"  3. {delta_path.name} — key metrics with Δ% overhead columns")


if __name__ == "__main__":
    main()
