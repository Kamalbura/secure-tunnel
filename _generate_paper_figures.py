#!/usr/bin/env python3
"""
Generate publication-quality figures for the PQC-MAV paper.
Uses corrected benchmark data from the natively-correct run (20260207_172159)
and the isolated primitive benchmarks.

Produces:
  1. kem_keygen_boxplot.pdf  - KEM keygen timing distributions (from bench data)
  2. sig_sign_boxplot.pdf    - SIG signing timing distributions (from bench data)
  3. suite_handshake_comparison.pdf - All 71 suites ranked (from corrected JSONs)
  4. kem_power_comparison.png - Power during KEM ops (from power bench data)
"""

import json
import csv
import pathlib
import statistics
import math
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.patches import Patch
import numpy as np

# ── IEEE-quality style settings ──
plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
    "font.size": 9,
    "axes.titlesize": 10,
    "axes.labelsize": 9,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "legend.fontsize": 8,
    "figure.dpi": 300,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.05,
    "axes.grid": True,
    "grid.alpha": 0.3,
    "grid.linewidth": 0.5,
    "axes.linewidth": 0.6,
    "lines.linewidth": 1.0,
    "patch.linewidth": 0.5,
    "xtick.major.width": 0.6,
    "ytick.major.width": 0.6,
    "text.usetex": False,
})

# ── Color palettes ──
FAMILY_COLORS = {
    "ML-KEM":   "#2563eb",  # Blue
    "HQC":      "#16a34a",  # Green
    "McEliece": "#dc2626",  # Red
}
SIG_COLORS = {
    "Falcon":   "#f59e0b",  # Amber
    "ML-DSA":   "#8b5cf6",  # Purple
    "SPHINCS+": "#06b6d4",  # Cyan
}
LEVEL_COLORS = {
    1: "#22c55e",  # Green
    3: "#f59e0b",  # Amber
    5: "#ef4444",  # Red
}

OUTPUT = pathlib.Path("paper/figures")
OUTPUT.mkdir(parents=True, exist_ok=True)

# ══════════════════════════════════════════════════════════════
# HELPER: Load corrected suite data from dashboard JSONs
# ══════════════════════════════════════════════════════════════
def load_corrected_suites():
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
        if not hs.get("handshake_success") or hs.get("handshake_total_duration_ms") is None:
            continue

        parts = sid.replace("cs-", "", 1)
        kem = sig = aead = ""
        level = 0

        if "mlkem512" in parts:                kem, level = "ML-KEM-512", 1
        elif "mlkem768" in parts:              kem, level = "ML-KEM-768", 3
        elif "mlkem1024" in parts:             kem, level = "ML-KEM-1024", 5
        elif "classicmceliece348864" in parts:  kem, level = "McEliece-348864", 1
        elif "classicmceliece460896" in parts:  kem, level = "McEliece-460896", 3
        elif "classicmceliece8192128" in parts: kem, level = "McEliece-8192128", 5
        elif "hqc128" in parts:                kem, level = "HQC-128", 1
        elif "hqc192" in parts:                kem, level = "HQC-192", 3
        elif "hqc256" in parts:                kem, level = "HQC-256", 5
        else: continue

        if "falcon512" in parts:   sig = "Falcon-512"
        elif "falcon1024" in parts: sig = "Falcon-1024"
        elif "mldsa44" in parts:   sig = "ML-DSA-44"
        elif "mldsa65" in parts:   sig = "ML-DSA-65"
        elif "mldsa87" in parts:   sig = "ML-DSA-87"
        elif "sphincs128s" in parts: sig = "SPHINCS+-128s"
        elif "sphincs192s" in parts: sig = "SPHINCS+-192s"
        elif "sphincs256s" in parts: sig = "SPHINCS+-256s"

        if "aesgcm" in parts:                aead = "AES-GCM"
        elif "chacha20poly1305" in parts:     aead = "ChaCha20"
        elif "ascon128a" in parts:            aead = "Ascon"

        family = kem.split("-")[0] if "-" in kem else kem
        if family == "ML": family = "ML-KEM"
        suites.append({
            "sid": sid, "kem": kem, "sig": sig, "aead": aead,
            "family": family, "level": level,
            "hs_ms": hs["handshake_total_duration_ms"],
        })

    # Deduplicate
    seen = set()
    unique = []
    for s in suites:
        if s["sid"] not in seen:
            seen.add(s["sid"])
            unique.append(s)
    return unique


# ══════════════════════════════════════════════════════════════
# FIGURE 1: Suite handshake comparison (CORRECTED)
# ══════════════════════════════════════════════════════════════
def fig_suite_handshake():
    suites = load_corrected_suites()
    suites.sort(key=lambda s: s["hs_ms"])

    fig, ax = plt.subplots(figsize=(3.5, 6.5))  # IEEE single-column

    y = np.arange(len(suites))
    times = [s["hs_ms"] for s in suites]

    # Color by KEM family
    colors = []
    for s in suites:
        colors.append(FAMILY_COLORS.get(s["family"], "#999999"))

    bars = ax.barh(y, times, color=colors, alpha=0.85, height=0.75,
                   edgecolor="white", linewidth=0.3)

    # Labels — abbreviated
    labels = []
    for s in suites:
        kem_short = s["kem"].replace("ML-KEM-", "K").replace("HQC-", "H").replace("McEliece-", "M")
        sig_short = s["sig"].replace("ML-DSA-", "D").replace("Falcon-", "F").replace("SPHINCS+-", "S")
        aead_short = s["aead"][0]  # A, C, or A
        if s["aead"] == "ChaCha20": aead_short = "C"
        elif s["aead"] == "Ascon": aead_short = "N"
        labels.append(f"{kem_short}·{sig_short}·{aead_short}")

    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=5, fontfamily="monospace")
    ax.set_xscale("log")
    ax.set_xlabel("Handshake time (ms, log scale)")
    ax.set_title("End-to-end handshake: 71 cipher suites", fontsize=9, fontweight="bold")

    # Add vertical reference lines
    ax.axvline(x=22, color="#2563eb", linestyle="--", alpha=0.4, linewidth=0.7)
    ax.text(22, len(suites)-1, " 22 ms", fontsize=6, color="#2563eb", va="top")
    ax.axvline(x=5000, color="#dc2626", linestyle="--", alpha=0.4, linewidth=0.7)
    ax.text(4000, 2, "5 s MAVLink\ntimeout  ", fontsize=6, color="#dc2626", ha="right", va="bottom")

    # Legend
    legend_elements = [
        Patch(facecolor=FAMILY_COLORS["ML-KEM"], label="ML-KEM", alpha=0.85),
        Patch(facecolor=FAMILY_COLORS["HQC"],    label="HQC", alpha=0.85),
        Patch(facecolor=FAMILY_COLORS["McEliece"], label="McEliece", alpha=0.85),
    ]
    ax.legend(handles=legend_elements, loc="lower right", framealpha=0.9,
              edgecolor="#cccccc", fontsize=7)

    ax.set_xlim(left=5)
    ax.invert_yaxis()
    plt.tight_layout()

    for ext in ["pdf", "png"]:
        fig.savefig(OUTPUT / f"suite_handshake_comparison.{ext}", format=ext)
    plt.close()
    print(f"[FIG] suite_handshake_comparison — {len(suites)} suites plotted")


# ══════════════════════════════════════════════════════════════
# FIGURE 2: KEM keygen boxplot (from bench CSV if available,
#           otherwise from dashboard crypto_primitives)
# ══════════════════════════════════════════════════════════════
def fig_kem_keygen_boxplot():
    csv_path = pathlib.Path("bench_analysis/csv/raw_kem.csv")
    
    # Try loading from bench CSV
    raw = defaultdict(list)
    if csv_path.exists():
        with open(csv_path) as f:
            for row in csv.DictReader(f):
                if row.get("operation") == "keygen":
                    algo = row["algorithm"]
                    try:
                        ms = float(row["wall_time_ns"]) / 1_000_000
                        raw[algo].append(ms)
                    except:
                        pass
    
    if not raw:
        print("[WARN] No bench CSV found, skipping kem_keygen_boxplot")
        return

    # Order by median time
    order = sorted(raw.keys(), key=lambda a: statistics.median(raw[a]))

    fig, ax = plt.subplots(figsize=(3.5, 3.0))  # IEEE single-column

    bp = ax.boxplot(
        [raw[a] for a in order],
        positions=range(len(order)),
        patch_artist=True,
        showfliers=True,
        widths=0.6,
        flierprops=dict(marker=".", markersize=2, alpha=0.4),
        medianprops=dict(color="black", linewidth=1),
        whiskerprops=dict(linewidth=0.7),
        capprops=dict(linewidth=0.7),
    )

    for patch, algo in zip(bp["boxes"], order):
        if "ML-KEM" in algo:   c = FAMILY_COLORS["ML-KEM"]
        elif "HQC" in algo:    c = FAMILY_COLORS["HQC"]
        elif "McEliece" in algo: c = FAMILY_COLORS["McEliece"]
        else: c = "#999"
        patch.set_facecolor(c)
        patch.set_alpha(0.7)

    short_labels = [a.replace("Classic-McEliece-", "McE-").replace("ML-KEM-", "K-") for a in order]
    ax.set_xticks(range(len(order)))
    ax.set_xticklabels(short_labels, rotation=40, ha="right", fontsize=7)
    ax.set_yscale("log")
    ax.set_ylabel("Keygen time (ms, log scale)")
    ax.set_title("KEM keygen distribution (n = 200)", fontsize=9, fontweight="bold")

    legend_elements = [
        Patch(facecolor=FAMILY_COLORS["ML-KEM"], label="ML-KEM", alpha=0.7),
        Patch(facecolor=FAMILY_COLORS["HQC"],    label="HQC", alpha=0.7),
        Patch(facecolor=FAMILY_COLORS["McEliece"], label="McEliece", alpha=0.7),
    ]
    ax.legend(handles=legend_elements, loc="upper left", framealpha=0.9,
              edgecolor="#cccccc", fontsize=7)

    plt.tight_layout()
    for ext in ["pdf", "png"]:
        fig.savefig(OUTPUT / f"kem_keygen_boxplot.{ext}", format=ext)
    plt.close()
    print(f"[FIG] kem_keygen_boxplot — {len(order)} algorithms")


# ══════════════════════════════════════════════════════════════
# FIGURE 3: SIG signing boxplot
# ══════════════════════════════════════════════════════════════
def fig_sig_sign_boxplot():
    csv_path = pathlib.Path("bench_analysis/csv/raw_sig.csv")

    raw = defaultdict(list)
    if csv_path.exists():
        with open(csv_path) as f:
            for row in csv.DictReader(f):
                if row.get("operation") == "sign":
                    algo = row["algorithm"]
                    try:
                        ms = float(row["wall_time_ns"]) / 1_000_000
                        raw[algo].append(ms)
                    except:
                        pass

    if not raw:
        print("[WARN] No bench CSV found, skipping sig_sign_boxplot")
        return

    order = sorted(raw.keys(), key=lambda a: statistics.median(raw[a]))

    fig, ax = plt.subplots(figsize=(3.5, 3.0))

    bp = ax.boxplot(
        [raw[a] for a in order],
        positions=range(len(order)),
        patch_artist=True,
        showfliers=True,
        widths=0.6,
        flierprops=dict(marker=".", markersize=2, alpha=0.4),
        medianprops=dict(color="black", linewidth=1),
        whiskerprops=dict(linewidth=0.7),
        capprops=dict(linewidth=0.7),
    )

    for patch, algo in zip(bp["boxes"], order):
        if "Falcon" in algo:     c = SIG_COLORS["Falcon"]
        elif "ML-DSA" in algo:   c = SIG_COLORS["ML-DSA"]
        elif "SPHINCS" in algo:  c = SIG_COLORS["SPHINCS+"]
        else: c = "#999"
        patch.set_facecolor(c)
        patch.set_alpha(0.7)

    short_labels = [a.replace("SPHINCS+-", "S+").replace("ML-DSA-", "D-").replace("Falcon-", "F-") for a in order]
    ax.set_xticks(range(len(order)))
    ax.set_xticklabels(short_labels, rotation=40, ha="right", fontsize=7)
    ax.set_yscale("log")
    ax.set_ylabel("Sign time (ms, log scale)")
    ax.set_title("Signature signing distribution (n = 200)", fontsize=9, fontweight="bold")

    legend_elements = [
        Patch(facecolor=SIG_COLORS["Falcon"],  label="Falcon", alpha=0.7),
        Patch(facecolor=SIG_COLORS["ML-DSA"],  label="ML-DSA", alpha=0.7),
        Patch(facecolor=SIG_COLORS["SPHINCS+"], label="SPHINCS⁺", alpha=0.7),
    ]
    ax.legend(handles=legend_elements, loc="upper left", framealpha=0.9,
              edgecolor="#cccccc", fontsize=7)

    plt.tight_layout()
    for ext in ["pdf", "png"]:
        fig.savefig(OUTPUT / f"sig_sign_boxplot.{ext}", format=ext)
    plt.close()
    print(f"[FIG] sig_sign_boxplot — {len(order)} algorithms")


# ══════════════════════════════════════════════════════════════
# FIGURE 4: KEM power comparison (from power bench data)
# ══════════════════════════════════════════════════════════════
def fig_kem_power():
    power_dir = pathlib.Path("bench_results_power/raw/kem")
    if not power_dir.exists():
        print("[WARN] No power bench data found, skipping kem_power_comparison")
        return

    # Gather power data per algorithm
    algo_power = defaultdict(lambda: {"mean_w": [], "energy_uj": [], "time_ms": []})
    for f in sorted(power_dir.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except:
            continue
        algo = data.get("algorithm", f.stem)
        pw = data.get("power", {})
        timing = data.get("timing", {})
        
        def _scalar(v):
            """Extract scalar from value that might be a list."""
            if isinstance(v, list):
                return statistics.mean(v) if v else None
            return v
        
        pmw = _scalar(pw.get("power_mean_w"))
        if pmw is not None:
            algo_power[algo]["mean_w"].append(pmw)
        ej = _scalar(pw.get("energy_j"))
        if ej is not None:
            algo_power[algo]["energy_uj"].append(ej * 1_000_000)
        if timing.get("wall_ns"):
            wns = timing["wall_ns"]
            if isinstance(wns, list):
                algo_power[algo]["time_ms"].extend([w / 1_000_000 for w in wns])
            else:
                algo_power[algo]["time_ms"].append(wns / 1_000_000)

    if not algo_power:
        print("[WARN] No KEM power data found")
        return

    # Sort by mean power
    algos = sorted(algo_power.keys(),
                   key=lambda a: statistics.mean(algo_power[a]["mean_w"]) if algo_power[a]["mean_w"] else 0)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.0, 3.0))  # IEEE double-column

    x = np.arange(len(algos))
    width = 0.6

    # Left: Mean power (W)
    powers = [statistics.mean(algo_power[a]["mean_w"]) if algo_power[a]["mean_w"] else 0 for a in algos]
    colors = []
    for a in algos:
        if "ML-KEM" in a or "mlkem" in a.lower(): colors.append(FAMILY_COLORS["ML-KEM"])
        elif "HQC" in a or "hqc" in a.lower(): colors.append(FAMILY_COLORS["HQC"])
        elif "McEliece" in a or "mceliece" in a.lower(): colors.append(FAMILY_COLORS["McEliece"])
        else: colors.append("#999")

    ax1.bar(x, powers, width, color=colors, alpha=0.8, edgecolor="white", linewidth=0.3)
    short = [a.replace("Classic-McEliece-", "McE-").replace("ML-KEM-", "K-").replace("p256_", "") for a in algos]
    ax1.set_xticks(x)
    ax1.set_xticklabels(short, rotation=40, ha="right", fontsize=7)
    ax1.set_ylabel("Mean power (W)")
    ax1.set_title("Power during KEM ops", fontsize=9, fontweight="bold")

    # Right: Energy per operation (µJ)
    energies = [statistics.mean(algo_power[a]["energy_uj"]) if algo_power[a]["energy_uj"] else 0 for a in algos]
    ax2.bar(x, energies, width, color=colors, alpha=0.8, edgecolor="white", linewidth=0.3)
    ax2.set_xticks(x)
    ax2.set_xticklabels(short, rotation=40, ha="right", fontsize=7)
    ax2.set_ylabel("Energy per op (µJ)")
    ax2.set_title("Energy per KEM operation", fontsize=9, fontweight="bold")
    if energies and max(energies) / max(min(e for e in energies if e > 0), 0.001) > 50:
        ax2.set_yscale("log")
        ax2.set_ylabel("Energy per op (µJ, log scale)")

    legend_elements = [
        Patch(facecolor=FAMILY_COLORS["ML-KEM"], label="ML-KEM", alpha=0.8),
        Patch(facecolor=FAMILY_COLORS["HQC"],    label="HQC", alpha=0.8),
        Patch(facecolor=FAMILY_COLORS["McEliece"], label="McEliece", alpha=0.8),
    ]
    ax2.legend(handles=legend_elements, loc="upper left", framealpha=0.9,
               edgecolor="#cccccc", fontsize=7)

    plt.tight_layout()
    for ext in ["png", "pdf"]:
        fig.savefig(OUTPUT / f"kem_power_comparison.{ext}", format=ext)
    plt.close()
    print(f"[FIG] kem_power_comparison — {len(algos)} algorithms")


# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 60)
    print("Generating paper figures with corrected data")
    print("=" * 60)

    # Always regenerate suite handshake (uses corrected dashboard data)
    fig_suite_handshake()

    # Regenerate primitive plots if bench CSVs exist
    fig_kem_keygen_boxplot()
    fig_sig_sign_boxplot()

    # Regenerate power comparison if power data exists
    fig_kem_power()

    print("\nDone. Figures saved to paper/figures/")
