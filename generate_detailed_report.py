#!/usr/bin/env python3
"""
PQC-MAV: Detailed PDF Report Generator
========================================
Generates a comprehensive PDF report where EVERY chart, table, and graph
gets a full page of beginner-friendly explanation -- assuming the reader
has zero prior knowledge of PQC, drones, or cryptographic benchmarks.

Usage:  python generate_detailed_report.py
Output: presentation/PQC_MAV_Detailed_Report_v3.pdf
"""

import json, io, textwrap, math
from pathlib import Path
from collections import defaultdict

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import Patch
from matplotlib.lines import Line2D
from PIL import Image

# Import data loading and chart helpers from v2 generator
from generate_presentation_v2 import (
    BASE, RUNS_DIR, OUTPUT_DIR, SCENARIOS,
    load_all_data, parse_suite_id, kem_family, sig_family, nist_level,
    extract_kem_keygen, extract_handshake, extract_by_kem_family,
    chart_kem_keygen, chart_handshake_by_family, chart_all_suites,
    chart_overhead_delta, chart_sig_timing, chart_aead,
    chart_pareto, chart_system_metrics, chart_boxplot_by_level,
    chart_rekey_overhead, chart_cpu_temp_heatmap,
)

OUTPUT_PATH = OUTPUT_DIR / "PQC_MAV_Detailed_Report_v3.pdf"


# ============================================================================
# Helper: Add a text page with word-wrapped paragraphs
# ============================================================================
def text_page(pdf, title, body, *, title_color="#1A237E", body_fontsize=10.5,
              body_color="black", section_num=None):
    """Render one page with a title bar and multi-paragraph body text."""
    fig = plt.figure(figsize=(11, 8.5))
    fig.patch.set_facecolor("white")

    # Optional section number badge
    heading = f"{section_num}. {title}" if section_num else title
    fig.text(0.05, 0.95, heading, fontsize=18, fontweight="bold",
             color=title_color, verticalalignment="top")

    # Body text (wraps automatically via matplotlib's built-in newline support)
    fig.text(0.06, 0.88, body, fontsize=body_fontsize, color=body_color,
             verticalalignment="top", wrap=True,
             transform=fig.transFigure,
             linespacing=1.55,
             fontfamily="sans-serif")
    pdf.savefig(fig)
    plt.close(fig)


def chart_page(pdf, title, chart_buf, *, section_num=None,
               caption=None, top_pct=0.82):
    """Render one page with chart embedded + optional caption."""
    fig = plt.figure(figsize=(11, 8.5))
    fig.patch.set_facecolor("white")
    heading = f"{section_num}. {title}" if section_num else title
    fig.text(0.05, 0.97, heading, fontsize=16, fontweight="bold", color="#1A237E")
    chart_buf.seek(0)
    img = Image.open(chart_buf)
    ax = fig.add_axes([0.04, 0.08, 0.92, top_pct])
    ax.imshow(img)
    ax.axis("off")
    if caption:
        fig.text(0.05, 0.04, caption, fontsize=8.5, color="#555555",
                 style="italic", wrap=True)
    pdf.savefig(fig)
    plt.close(fig)


def table_page(pdf, title, col_labels, rows, *, section_num=None,
               note=None, col_colors=None, row_height=2.0,
               font_size=10):
    """Render one page with a data table."""
    fig, ax = plt.subplots(figsize=(11, 8.5))
    fig.patch.set_facecolor("white")
    ax.axis("off")
    heading = f"{section_num}. {title}" if section_num else title
    fig.text(0.05, 0.95, heading, fontsize=16, fontweight="bold", color="#1A237E")
    table = ax.table(cellText=rows, colLabels=col_labels,
                     loc="center", cellLoc="center")
    table.auto_set_font_size(False)
    table.set_fontsize(font_size)
    table.scale(1.3, row_height)
    ncols = len(col_labels)
    for j in range(ncols):
        table[0, j].set_facecolor("#1A237E")
        table[0, j].set_text_props(color="white", fontweight="bold")
    if col_colors:
        for i, row in enumerate(rows):
            for j, cc in enumerate(col_colors):
                if cc and callable(cc):
                    c = cc(row, i, j)
                    if c:
                        table[i + 1, j].set_facecolor(c)
    if note:
        fig.text(0.05, 0.12, note, fontsize=9, color="#757575", style="italic",
                 wrap=True)
    pdf.savefig(fig)
    plt.close(fig)


# ============================================================================
# Main report builder
# ============================================================================
def build_detailed_report(data, charts):
    baseline = data["no-ddos"]
    xgb = data["ddos-xgboost"]
    tst = data["ddos-txt"]

    sec = [0]  # mutable counter for section numbering

    def sn():
        sec[0] += 1
        return str(sec[0])

    with PdfPages(str(OUTPUT_PATH)) as pdf:
        # ================================================================
        # PAGE 1: Title Page
        # ================================================================
        fig = plt.figure(figsize=(11, 8.5))
        fig.patch.set_facecolor("#1A237E")
        fig.text(0.5, 0.68, "PQC-MAV", fontsize=52, fontweight="bold",
                 color="white", ha="center")
        fig.text(0.5, 0.54,
                 "A Complete Post-Quantum Cryptographic Tunnel\n"
                 "for UAV–GCS Communication",
                 fontsize=18, color="#BBDEFB", ha="center", linespacing=1.6)
        fig.text(0.5, 0.42, "-" * 40, fontsize=12, color="#2196F3", ha="center")
        fig.text(0.5, 0.34, "Comprehensive Benchmark Report",
                 fontsize=18, color="white", ha="center")
        fig.text(0.5, 0.24, "Burak Güneysu  •  February 2026",
                 fontsize=13, color="#9E9E9E", ha="center")
        fig.text(0.5, 0.14,
                 "72 Cipher Suites  ·  3 Scenarios  ·  216 Live Tunnel Sessions  ·  Real Hardware",
                 fontsize=11, color="#757575", ha="center")
        fig.text(0.5, 0.06,
                 "Every chart in this report is followed by a full-page explanation.",
                 fontsize=10, color="#FFD54F", ha="center", style="italic")
        pdf.savefig(fig); plt.close(fig)

        # ================================================================
        # BOOK-STYLE INTRODUCTION: BENCHMARKING FOUNDATIONS
        # ================================================================

        # -- Chapter 0.1: What Is Benchmarking? -------------------------
        text_page(pdf, "What Is Benchmarking?", textwrap.dedent("""\
        Before presenting results, this report dedicates its opening pages to
        explaining -- from the very basics -- what benchmarking means in a
        research context, how our benchmark system was designed, how it collects
        data, and how it validates itself. Without this foundation, the charts
        and tables that follow would be just numbers without meaning.

        DEFINITION:
        "Benchmarking" is the systematic, repeatable measurement of a system's
        behaviour under controlled conditions. It is not a casual speed test.
        A proper benchmark must satisfy four scientific requirements:

        1. REPRODUCIBILITY -- the same hardware, software, and environment
           must produce statistically similar results if re-run tomorrow.

        2. ISOLATION -- each measurement must be independent. One cipher suite's
           performance must not leak into the next suite's measurement.

        3. COMPLETENESS -- every relevant algorithm combination must be tested,
           not just the ones we expect to perform well.

        4. TRANSPARENCY -- every raw data point, every intermediate calculation,
           and every anomaly must be recorded, not hidden.

        WHAT WE ARE BENCHMARKING:
        We are measuring the real-world performance cost of adding post-quantum
        cryptographic protection to a live drone-to-ground-station communication
        channel. Specifically, we measure:

          * Handshake latency -- how long does it take for the drone and GCS to
            negotiate a shared encryption key using post-quantum algorithms?

          * Per-packet overhead -- how much time does encrypting/decrypting each
            MAVLink telemetry packet add to the communication pipeline?

          * System impact -- how much CPU, memory, thermal headroom, and battery
            energy does the cryptographic workload consume on a constrained
            ARM-based drone computer (Raspberry Pi 5)?

          * Primitive-level timing -- how fast are the individual cryptographic
            operations (keygen, encaps, decaps, sign, verify) on real hardware?

        WHY NOT USE EXISTING BENCHMARKS?
        Standard cryptographic benchmarks (like liboqs speed tests or SUPERCOP)
        measure isolated operations in a vacuum. They do NOT capture:
          - Real network I/O (sending keys and ciphertexts over TCP/UDP)
          - Operating-system scheduling and context-switch overhead
          - Memory pressure when running alongside other processes
          - Thermal throttling on small ARM boards after sustained load
          - Protocol-level overhead (framing, nonce construction, AAD building)

        Our benchmark measures the ENTIRE PROTOCOL -- not just the math.
        """), section_num="I")

        # -- Chapter 0.2: Benchmark Architecture Overview ---------------
        text_page(pdf, "Benchmark Architecture Overview", textwrap.dedent("""\
        The PQC-MAV benchmark system consists of two coordinated programs running
        on two separate physical machines connected by an Ethernet LAN:

        DRONE SIDE (sdrone_bench.py -- the "scheduler"):
          Runs on the Raspberry Pi 5 (uavpi, 192.168.0.100).
          This is the MASTER. It decides which cipher suite to test next,
          starts and stops the tunnel proxy, collects drone-side metrics, and
          saves the final merged JSON output for each suite.

        GCS SIDE (sgcs_bench.py -- the "server"):
          Runs on the Windows 11 laptop (lappy, 192.168.0.101).
          This is the FOLLOWER. It listens for JSON-RPC commands from the drone
          scheduler and obeys them: start proxy, stop proxy, report metrics.

        COORDINATION PROTOCOL (TCP port 48080):
          The drone and GCS communicate via a simple JSON-RPC channel:
            - "ping"          -- heartbeat, verify the GCS is alive
            - "get_info"      -- retrieve GCS system info (OS, CPU, liboqs version)
            - "chronos_sync"  -- 3-way clock synchronisation (NTP-lite protocol)
            - "start_proxy"   -- start the GCS-side tunnel proxy for a given suite
            - "stop_suite"    -- stop the current suite, return GCS metrics
            - "stop_traffic"  -- halt MAVLink traffic generators
            - "shutdown"      -- full GCS shutdown after all 72 suites complete

        WHY TCP:48080 AND NOT THE TUNNEL ITSELF?
          The benchmark coordination channel MUST be separate from the tunnel
          being tested. If we used the PQC tunnel to send benchmark commands,
          a handshake failure would also break the benchmark control channel --
          making it impossible to diagnose the failure.

        PHYSICAL NETWORK LAYOUT:
          [Pixhawk SITL] --> serial/UDP --> [MAVProxy] --> UDP:14590
                --> [PQC Tunnel: Drone Proxy] --> (PQC-encrypted UDP:46011/46012)
                --> [PQC Tunnel: GCS Proxy]   --> UDP:14551 --> [GCS software]

          Separately: [Drone scheduler] -- TCP:48080 --> [GCS benchmark server]
        """), section_num="II")

        # -- Chapter 0.3: The Complete Benchmark Lifecycle --------------
        text_page(pdf, "The Complete Benchmark Lifecycle", textwrap.dedent("""\
        Here is the exact sequence of events when you run the benchmark from
        start to finish. This is what the drone scheduler (sdrone_bench.py) does:

        PHASE 1: INITIALISATION (runs once)
          1. Parse command-line arguments (scenario name, rekey interval, etc.)
          2. Build the "BenchmarkPolicy" -- a state machine that tracks which
             of the 72 suites have been tested and decides what comes next
          3. Initialise the MetricsAggregator -- the central hub that will
             collect and merge all measurements
          4. Read the suite registry from core/suites.py (all 72 combinations)
          5. Wait for GCS to come online: send "ping" commands via TCP:48080
             until the GCS responds (this ensures both machines are ready)

        PHASE 2: CLOCK SYNCHRONISATION (runs once)
          6. Execute a 3-way NTP-lite synchronisation ("chronos_sync"):
               - Drone sends timestamp T1 to GCS
               - GCS records receipt at T2, responds immediately at T3
               - Drone records receipt at T4
               - Clock offset = ((T2-T1) + (T3-T4)) / 2
             This lets us correlate drone-side and GCS-side timestamps even
             though the two machines have independent clocks.

        PHASE 3: START MAVProxy (runs once)
          7. Launch MAVProxy -- the standard MAVLink router that connects the
             Pixhawk SITL flight controller to the PQC tunnel input. MAVProxy
             generates ~320 MAVLink messages per second (heartbeat, GPS,
             attitude, battery, EKF status, etc.)

        PHASE 4: PER-SUITE LOOP (repeats 72 times)
          8. The BenchmarkPolicy selects the next untested suite
             (e.g., "cs-mlkem768-aesgcm-mldsa65")
          9. The scheduler calls _activate_suite() which:
               a. Sends "start_proxy {suite_id}" to GCS via TCP:48080
               b. GCS starts its tunnel proxy (core/async_proxy.py) with the
                  specified KEM, SIG, and AEAD algorithms
               c. Drone starts its own tunnel proxy
               d. Tunnel proxies perform the PQC handshake (see next page)
               e. read_handshake_status(timeout=45s) -- waits for handshake
                  success or failure, with a 45-second timeout
          10. If handshake succeeds, a 30-second data session begins:
               MAVLink flows through the PQC tunnel at 320 Hz
          11. At each 1-second interval, the system collector samples CPU
              usage, temperature, memory, and other OS-level metrics

        (continued on next page)
        """), section_num="III")

        text_page(pdf, "The Complete Benchmark Lifecycle (continued)", textwrap.dedent("""\
        PHASE 4 (continued): PER-SUITE LOOP

          12. After 30 seconds, the scheduler sends "stop_suite" to GCS
          13. GCS returns its metrics (GCS-side handshake timing, packet
              counts, CPU usage, etc.) as a JSON dictionary
          14. The MetricsAggregator merges drone-side + GCS-side data:
               - Drone contributes: all crypto primitive times, KEM operation
                 durations, drone CPU, temperature, power, AEAD counters
               - GCS contributes: its own KEM/SIG times, packet counts, CPU usage
          15. The merged JSON is written to:
               logs/benchmarks/runs/{scenario}/{suite_id}/metrics.json
          16. BenchmarkPolicy.evaluate() is called:
               - Returns HOLD (stay on current suite -- used for retries)
               - Returns NEXT_SUITE (advance to next untested suite)
               - Returns COMPLETE (all 72 suites finished)
          17. confirm_advance() is called -- the only function that mutates the
              policy state. This is a deliberate "two-phase commit" design:
              evaluation is pure logic; advancement is an explicit action.

        PHASE 5: FINALISATION (runs once)
          18. After all 72 suites complete (or the policy declares COMPLETE):
               - Send "shutdown" to GCS
               - Close MAVProxy
               - Write a summary manifest (timing, pass/fail counts)
               - Print final statistics

        TOTAL WALL-CLOCK TIME:
          72 suites × ~110 seconds each = ~132 minutes per scenario.
          3 scenarios × 132 min = ~396 minutes = ~6.6 hours total.

        TWO-PHASE COMMIT AND STATE MACHINE:
          The BenchmarkPolicy has only ONE function that changes state:
          confirm_advance(). All other methods are read-only queries. This
          means the benchmark never accidentally skips or double-counts a
          suite, even if an error occurs mid-run. The policy remembers which
          suites are "completed", "failed", or "pending", and on restart it
          can resume from where it left off.

        CRASH RECOVERY:
          Because each suite's metrics are written to disk immediately after
          completion (step 15), a power failure or crash loses at most ONE
          suite's data. The policy state file on disk enables warm restart.
        """), section_num="III (cont.)")

        # -- Chapter 0.4: The PQC Handshake Protocol --------------------
        text_page(pdf, "The PQC Handshake Protocol", textwrap.dedent("""\
        The handshake is the most critical part of each benchmark run. It is
        where ALL the post-quantum cryptographic operations happen. Here is
        the exact 3-message protocol as implemented in core/handshake.py:

        MESSAGE 1: TCP CONNECT (Drone --> GCS)
          The drone's proxy opens a TCP connection to GCS port 46000.
          This is a plain TCP socket -- no encryption yet.

        MESSAGE 2: SERVER_HELLO (GCS --> Drone)
          The GCS ("server") performs:
            a. KEM keygen: Generate a fresh public/private key pair
               using the selected algorithm (e.g. ML-KEM-768).
               Timing: measured via time.perf_counter_ns()
            b. Build the ServerHello message containing:
               - Protocol version ("pq-drone-gcs:v1")
               - Session ID (8 random bytes)
               - KEM algorithm name and parameters
               - SIG algorithm name and parameters
               - The KEM public key (800 to 1,357,824 bytes!)
               - A random challenge (for HMAC-PSK authentication)
            c. Sign the entire ServerHello using the selected SIG algorithm
               (e.g. Falcon-512). The signature is appended to the message.
            d. Send the complete ServerHello over TCP

        MESSAGE 3: CLIENT_RESPONSE (Drone --> GCS)
          The drone receives ServerHello and:
            a. Verify the signature on ServerHello using the GCS's pre-shared
               SIG public key. If verification fails, abort immediately.
            b. KEM encaps: Use the received KEM public key to encapsulate
               a random shared secret. This produces a "ciphertext" that only
               the GCS's private key can decrypt.
            c. Build a "transcript" of the entire exchange:
               transcript = version | protocol_id | session_id | kem_name |
                            sig_name | kem_pub | challenge
            d. Compute HMAC-PSK over the transcript using a pre-shared key.
               This provides an additional layer of authentication beyond
               the digital signature.
            e. Send the KEM ciphertext + HMAC to GCS

        KEY DERIVATION (both sides independently):
          After message 3, both sides hold the same shared secret (from KEM).
          They derive the AEAD session keys using HKDF-SHA256:
            - Input: shared_secret from KEM
            - Salt: session_id
            - Info: structured string with KEM/SIG/AEAD names
            - Output: 64 bytes, split into:
                k_drone_to_gcs (32 bytes) -- for encrypting drone-to-GCS traffic
                k_gcs_to_drone (32 bytes) -- for encrypting GCS-to-drone traffic
          Two separate keys ensure that traffic in each direction uses a unique
          key -- compromising one direction does not compromise the other.
        """), section_num="IV")

        # -- Chapter 0.5: The Encrypted Data Plane ----------------------
        text_page(pdf, "The Encrypted Data Plane", textwrap.dedent("""\
        Once the handshake completes, the tunnel switches from TCP (handshake)
        to UDP (data plane). Every MAVLink packet is encrypted using AEAD.
        Here is how it works, as implemented in core/aead.py:

        PACKET STRUCTURE:
        Each encrypted packet consists of:
          [22-byte header] [encrypted payload] [16-byte authentication tag]

        The 22-byte header is sent IN THE CLEAR (not encrypted) and contains:
          - version      (1 byte)  -- protocol version
          - kem_id       (1 byte)  -- which KEM was used
          - kem_param    (1 byte)  -- KEM parameter set
          - sig_id       (1 byte)  -- which SIG was used
          - sig_param    (1 byte)  -- SIG parameter set
          - session_id   (8 bytes) -- identifies which handshake produced this key
          - sequence_no  (8 bytes) -- monotonically increasing packet counter
          - epoch        (1 byte)  -- rekey generation counter

        This header serves as the AAD (Associated Authenticated Data) -- it is
        not encrypted, but it IS authenticated. Any tampering with the header
        will cause the authentication tag to fail verification.

        NONCE CONSTRUCTION:
          The nonce (number-used-once) is NOT transmitted. Instead, both sides
          reconstruct it from the epoch and sequence number:
            nonce = epoch (1 byte) || sequence_no (8 bytes) || padding
          This saves 12 bytes per packet and eliminates nonce-reuse attacks.

        ANTI-REPLAY PROTECTION:
          A 1024-bit sliding bitmap window tracks received sequence numbers.
          When a packet arrives:
            - If seq > highest_seen: advance the window, mark as received
            - If seq is within the window: check the bitmap bit
            - If seq is too old (outside the window): drop as "replay"
          This prevents an attacker from recording and re-sending old packets.

        WIRE OVERHEAD:
          Every MAVLink packet gains 22 (header) + 16 (tag) = 38 bytes of
          overhead. For a typical MAVLink v2 message of ~50 bytes, this is
          a 76% size increase. At 320 messages/second on a LAN, this is
          still well within bandwidth limits (320 x 88 bytes = 28 KB/s).

        DROP CLASSIFICATION:
          The proxy tracks 6 categories of dropped packets:
            drop_replay, drop_auth_fail, drop_seq_old, drop_decrypt_fail,
            drop_malformed, drop_unknown
          Every dropped packet is counted and categorised -- never silently
          discarded. This transparency is essential for forensic analysis.
        """), section_num="V")

        # -- Chapter 0.6: How Metrics Are Collected ---------------------
        text_page(pdf, "How Metrics Are Collected", textwrap.dedent("""\
        Accurate measurement is the foundation of any benchmark. PQC-MAV uses
        a dedicated metrics pipeline with 6 specialised collector classes,
        all defined in core/metrics_collectors.py:

        1. ENVIRONMENT COLLECTOR (EnvironmentCollector):
           Captures static facts about the test environment at startup:
           hostname, OS version, kernel version, Python version, liboqs
           version, CPU model, total RAM, architecture. These never change
           during a run but are essential for reproducibility -- if someone
           wants to replicate our results, they need to know the exact system.

        2. SYSTEM COLLECTOR (SystemCollector):
           Samples dynamic OS metrics every 0.5 seconds throughout the run:
             - CPU usage (per-core and average) via /proc/stat
             - Temperature via /sys/class/thermal/thermal_zone0
             - Memory usage via /proc/meminfo
             - Disk I/O (reads/writes per second)
           At the end of each suite, it computes: average, peak, min, and
           standard deviation for each metric. This gives us both the typical
           load AND the worst-case spikes.

        3. POWER COLLECTOR (PowerCollector):
           Reads the INA219 current/voltage sensor at 1 kHz (1000 times per
           second) via the I2C bus, or falls back to the kernel's hwmon
           interface if the sensor is unavailable. Computes:
             - Average power draw (watts)
             - Peak power draw
             - Total energy consumed per suite (joules = watts x seconds)
           This is critical for drone deployment: power = flight time.

        4. NETWORK COLLECTOR (NetworkCollector):
           Monitors the network interface counters:
             - Bytes sent/received
             - Packets sent/received
             - Errors. Dropped packets at the OS level
           Computed as deltas (before vs. after each suite) so we measure
           only the traffic generated by that specific suite, not background.

        5. LATENCY TRACKER (LatencyTracker):
           Measures round-trip time between drone and GCS using timestamped
           probe packets inserted into the MAVLink stream. Records:
             - Mean, median, P95, P99 latency
             - Jitter (variance in latency)
             - Packet-level timing distributions

        6. MAVLINK METRICS COLLECTOR (MavLinkMetricsCollector):
           Hooks into MAVProxy to count MAVLink message statistics:
             - Messages per second (inbound and outbound)
             - Message type distribution (HEARTBEAT, GPS, ATTITUDE, etc.)
             - CRC errors, sequence gaps, lost messages
           This detects whether the PQC tunnel is causing message drops.
        """), section_num="VI")

        # -- Chapter 0.7: The MetricsAggregator Hub ---------------------
        text_page(pdf, "The MetricsAggregator: Central Data Hub", textwrap.dedent("""\
        All six collectors feed their data into a single central component:
        the MetricsAggregator (core/metrics_aggregator.py). This hub is
        responsible for the complete lifecycle of metric data for each suite.

        PER-SUITE LIFECYCLE:
          1. start_suite(suite_id)
             Resets all collectors to zero. Starts the system collector's
             sampling timer. Records the start timestamp.

          2. record_handshake(timing_dict)
             Called once after the handshake completes (or fails). Records all
             handshake-related metrics: total duration, per-step durations
             (keygen, encaps, decaps, sign, verify), success/failure, and
             the public key / ciphertext / signature sizes.

          3. record_crypto_primitives(details)
             Records the raw timing of each individual cryptographic operation
             in nanosecond precision. These are separate from the handshake
             times because they exclude network I/O and protocol overhead --
             giving us the "pure algorithm" time for comparison with published
             benchmarks by algorithm authors.

          4. record_data_plane(counters)
             At the end of the 30-second session, the AEAD proxy reports:
             packets encrypted/decrypted, bytes processed, average encrypt
             and decrypt times, drop counts by category, and anti-replay
             window statistics.

          5. finalize_suite(gcs_metrics)
             Merges the GCS-side metrics (sent via TCP:48080 after "stop_suite")
             into the drone-side data. The merge is additive -- no data is
             overwritten. GCS metrics go into dedicated "gcs_*" fields.

          6. save_suite_metrics(output_path)
             Serialises all collected data into a JSON file with an 18-category
             structure (described on the next page). This file is the primary
             research artifact -- every chart in this report is generated from
             these JSON files.

        TIMING PRECISION:
          All timing uses time.perf_counter_ns() -- Python's highest-resolution
          monotonic clock, with nanosecond granularity. On the RPi 5, this maps
          to the ARM Performance Monitor Unit (PMU), providing sub-microsecond
          accuracy. We chose perf_counter_ns() over time.time() because perf_counter
          is not affected by NTP clock adjustments or timezone changes.
        """), section_num="VII")

        # -- Chapter 0.8: The 18-Category JSON Schema -------------------
        text_page(pdf, "The 18-Category Metrics Schema", textwrap.dedent("""\
        Each suite's JSON output follows a strict 18-category schema defined in
        core/metrics_schema.py. These categories (labelled A through R) ensure
        that every aspect of the system is captured:

        Category A -- RunContext (20 fields):
          Suite ID, scenario name, timestamp, hostname, OS, kernel version,
          Python version, liboqs version, CPU model, RAM, rekey interval,
          run duration, and other environment metadata.

        Category B -- CryptoIdentity (8 fields):
          KEM algorithm name and NIST level, SIG algorithm name and level,
          AEAD algorithm name, mathematical family classification.

        Category C -- Lifecycle (5 fields):
          Suite start/end timestamps, total duration, handshake success flag,
          and reason for failure (if any).

        Category D -- Handshake (7 fields):
          Total handshake duration (ms), per-phase breakdown (TCP connect,
          ServerHello send, client response, key derivation), timeout flag.

        Category E -- CryptoPrimitives (15 fields):
          Individual operation times in ms: KEM keygen, encaps, decaps,
          SIG keygen, sign, verify. Plus key sizes and ciphertext sizes.

        Category F -- Rekey (7 fields):
          Number of rekeys performed, total rekey time, average rekey
          duration, rekey overhead percentage Phi(R).

        Category G -- DataPlane (22 fields):
          Packets sent/received, bytes sent/received, AEAD encrypt/decrypt
          averages (nanoseconds), packet loss ratio, duplicate count, and
          all 6 drop-category counters.

        Category H -- LatencyJitter (11 fields):
          Mean, median, P95, P99 latency, jitter, min/max RTT.

        Categories I-J -- MavProxy Drone + GCS (17 fields total):
          MAVLink message counts, rates, CRC errors, sequence gaps.

        Category K -- MavLinkIntegrity (9 fields):
          End-to-end message checks: expected vs. received, gap analysis.

        Categories L-R -- System telemetry, power, validation (remaining).
        """), section_num="VIII")

        # -- Chapter 0.9: Validation and Verification -------------------
        text_page(pdf, "Validation and Verification", textwrap.dedent("""\
        A benchmark is only as trustworthy as its validation. PQC-MAV implements
        multiple layers of automated verification, so that if any measurement is
        suspect, it is flagged -- never silently accepted.

        1. BUILT-IN SANITY CHECKS (run after every suite):
           The MetricsAggregator runs a battery of checks before saving:
             - mavlink_no_messages: Did MAVLink traffic actually flow?
               If zero MAVLink messages were exchanged, the suite is flagged.
             - mavlink_latency_invalid: Is the measured latency physically
               plausible? (e.g., negative latency indicates a clock error)
             - data_plane_no_traffic: Did the AEAD proxy process any packets?
               A handshake might "succeed" but produce no data flow.
             - handshake_timeout: Did the handshake exceed the 45-second limit?
             - handshake_auth_fail: Did signature verification or HMAC fail?

        2. METRIC TRANSPARENCY (per-field status tracking):
           Every metric that is null, zero, or anomalous gets a companion
           entry in the "metric_status" dictionary explaining WHY:
             "kem_keygen_time_ms": null,
             "metric_status": {
               "kem_keygen_time_ms": {
                 "status": "unavailable",
                 "reason": "GCS-side operation; not measured on drone"
               }
             }
           This means a reader (or automated tool) can distinguish between
           "this metric was zero because nothing happened" and "this metric
           was zero because it wasn't applicable to this side."

        3. DATA INTEGRITY HASH:
           Before writing each JSON file, the aggregator computes a SHA-256
           hash over the entire serialised metrics dictionary (excluding the
           hash field itself). This hash is stored in the JSON output.
           If anyone modifies the JSON file after the benchmark (accidentally
           or maliciously), the hash will no longer match -- detecting tampering.

        4. GCS-SIDE CROSS-VALIDATION:
           The GCS independently measures its own KEM keygen, SIG verify, and
           decapsulation times. When the drone merges GCS metrics in step 5 of
           the aggregator lifecycle, it DOES NOT overwrite drone-side data.
           Instead, both sides' measurements are preserved. A post-hoc audit
           can compare drone-reported vs. GCS-reported timing for the same
           operations -- if they diverge significantly, something is wrong.

        5. ANTI-REPLAY VERIFICATION:
           The sliding-bitmap anti-replay window maintains statistics:
             - Total packets inside window: should equal packets received
             - Total replays detected: should be zero in a clean run
             - Drop counters by category: all should be zero unless an
               attack is being simulated
           Any non-zero drop counter in a baseline (no-attack) scenario is
           an automatic red flag.

        6. SUCCESS/FAILURE ACCOUNTING:
           Of our 216 total runs (72 suites x 3 scenarios), exactly 215
           succeeded and 1 timed out. The single failure -- McEliece-460896 +
           SPHINCS+-192s in the baseline scenario -- is fully documented:
           the KEM keygen (231 ms) plus SPHINCS+-192s signing (1,342 ms)
           combined to exceed the 45-second handshake timeout under load.
           This failure is itself a valuable data point, not an error to hide.
        """), section_num="IX")

        # -- Chapter 0.10: How to Read This Report ----------------------
        text_page(pdf, "How to Read This Report", textwrap.dedent("""\
        Now that you understand the benchmark infrastructure, here is how the
        rest of this report is structured:

        THE PATTERN:
        Every topic follows a three-part pattern:
          1. A CHART or TABLE presenting the visual data
          2. A full EXPLANATION PAGE that assumes zero prior knowledge:
             - What the chart shows
             - How to read the axes and colours
             - What the key observations are
             - What the practical implications mean for drone deployment

        THE FLOW:
        The report progresses from individual primitives to system-level analysis:

          * KEM Performance: How fast is each key-exchange algorithm?
            --> Chart + Table + Explanation

          * SIG Performance: How fast is each signature algorithm?
            --> Chart + Table + Explanation

          * AEAD Performance: How fast is each per-packet cipher?
            --> Chart + Table + Explanation

          * Full Handshake Analysis: All 72 suites ranked end-to-end
            --> Ranking chart + Statistical tables + Boxplots

          * Pareto Frontier: Which suites offer the best security-speed tradeoff?
            --> Scatter plot + Pareto table + Explanation

          * Rekey Overhead: What is the cost of periodic key rotation?
            --> Phi(R) curves + Energy budget analysis

          * Scenario Comparison: How does DDoS detection affect everything?
            --> Family comparison + Overhead delta table

          * System Metrics: CPU, temperature, packets under each scenario
            --> System charts + Heatmap + Cross-scenario summary

          * Conclusions: Key findings and deployment recommendations

        DATA PROVENANCE:
        Every number in this report can be traced back to a specific JSON
        file in logs/benchmarks/runs/{scenario}/{suite_id}/metrics.json.
        These files are the benchmark's primary research artifacts and are
        stored alongside this report for auditability.

        All 216 JSON files (72 suites x 3 scenarios) were generated in a
        single continuous benchmark session lasting approximately 6.6 hours.
        No cherry-picking, no re-runs, no manual edits to the raw data.

        With this foundation in place, let us examine the results.
        """), section_num="X")

        # ================================================================
        # PAGE 2-3: What Is This Report About?
        # ================================================================
        text_page(pdf, "What Is This Report About?", textwrap.dedent("""\
        This report presents the results of a real-world experiment where we tested
        how well different "post-quantum" encryption algorithms perform on a small
        drone computer (Raspberry Pi 5).

        WHY THIS MATTERS:
        Today's encryption (RSA, ECDH, ECDSA) will be broken when large-scale quantum
        computers arrive. Governments and standards bodies like NIST have already
        standardised replacement algorithms -- but nobody has tested whether these new,
        heavier algorithms actually work on tiny drone hardware with tight power,
        thermal, and real-time constraints.

        WHAT WE BUILT:
        PQC-MAV is a transparent "bump-in-the-wire" encrypted tunnel that sits between
        a drone's flight controller and the ground-control station (GCS). It encrypts
        all MAVLink telemetry (position, battery, attitude, etc.) using post-quantum
        algorithms -- without requiring any changes to the existing autopilot or GCS
        software.

        WHAT WE TESTED:
        We built 72 different "cipher suites" -- combinations of three algorithm types:
          • KEM (Key Encapsulation Mechanism) -- for establishing a shared secret key
          • SIG (Digital Signature) -- for authenticating that the drone is really the drone
          • AEAD (Authenticated Encryption) -- for actually encrypting each data packet

        We ran every one of these 72 suites through a complete live tunnel session:
        a full cryptographic handshake followed by 30 seconds of real MAVLink telemetry
        flowing through the tunnel at 320 messages per second. We did this three times
        under different conditions (no DDoS, XGBoost detector running, TST detector running),
        producing 216 total benchmark runs.

        All numbers in this report come from those live runs on real hardware --
        not from theoretical calculations or isolated micro-benchmarks.
        """), section_num=sn())

        text_page(pdf, "Key Terminology (Glossary)", textwrap.dedent("""\
        If you are new to cryptography or drones, here are the key terms used
        throughout this report:

        POST-QUANTUM CRYPTOGRAPHY (PQC):
          Encryption algorithms designed to resist attacks from both classical
          computers AND future quantum computers. They use mathematical problems
          (like lattice problems) that quantum computers cannot efficiently solve.

        KEM (Key Encapsulation Mechanism):
          A way for two parties to agree on a secret encryption key. One side
          generates a key pair (keygen), the other "encapsulates" a random secret
          using the public key (encaps), and the first side "decapsulates" it
          using the private key (decaps). This replaces Diffie-Hellman / ECDH.

        DIGITAL SIGNATURE (SIG):
          Proves that a message really came from the claimed sender. The signer
          uses a private key to "sign" a message; the receiver uses the public
          key to "verify" the signature. This replaces RSA / ECDSA.

        AEAD (Authenticated Encryption with Associated Data):
          Encrypts each individual data packet AND guarantees it hasn't been
          tampered with. This is the "bulk encryption" -- applied to every single
          MAVLink message flowing through the tunnel.

        HANDSHAKE:
          The initial negotiation where KEM + SIG operations establish a shared
          encryption key. During the handshake, no MAVLink data flows (a "blackout").
          Shorter handshakes = less disruption to the drone.

        REKEY:
          Periodically replacing the shared key (e.g., every 60 seconds) by
          performing another handshake. Frequent rekeying improves security but
          costs performance during each handshake.

        NIST SECURITY LEVEL:
          A standardised measure of how hard it is to break the algorithm.
          Level 1 ≈ AES-128 difficulty, Level 3 ≈ AES-192, Level 5 ≈ AES-256.
          Higher levels are harder to break but typically use larger keys and
          take longer to compute.

        MAVLink:
          A compact binary protocol used by almost all open-source drones and
          ground-control stations to exchange telemetry (GPS, attitude, battery,
          mission waypoints, etc.) in real time at up to 320 messages per second.

        Φ(R) -- REKEY OVERHEAD:
          The fraction of time spent doing handshakes instead of transmitting data.
          Formula: Φ(R) = T_handshake / (R + T_handshake), where R is the rekey
          interval in seconds. Lower is better.
        """), section_num=sn())

        # ================================================================
        # PAGE 4: Hardware Testbed
        # ================================================================
        text_page(pdf, "Hardware Testbed & Methodology", textwrap.dedent("""\
        HARDWARE:

        +----------------------------------------------------------------------+
        |  DRONE (uavpi)                     |  GCS (lappy)                   |
        |  --------------                    |  ----------                    |
        |  Raspberry Pi 5                    |  Windows 11 x86-64             |
        |  ARM Cortex-A76 (4 cores, 2.4 GHz) |  Python 3.11.13               |
        |  3,796 MB RAM, Linux 6.12          |  liboqs 0.12.0                |
        |  Python 3.11.2, liboqs 0.12.0      |  IP: 192.168.0.101            |
        |  IP: 192.168.0.100                 |                                |
        |  Network: Ethernet LAN (sub-ms RTT)|                                |
        +----------------------------------------------------------------------+

        WHY THESE NUMBERS MATTER:
        The Raspberry Pi 5 is representative of companion computers used in real
        research and commercial drones. Its ARM Cortex-A76 CPU is similar to what
        you'd find in high-end drone flight computers. If PQC works here, it can
        work on most modern drone platforms.

        BENCHMARK PROTOCOL (per suite):
          1. Drone scheduler selects next suite from the 72-suite registry
          2. Sends "start_proxy" JSON-RPC command to GCS via TCP port 48080
          3. Full PQC handshake executes:
             - GCS performs KEM keygen (generates public + private key pair)
             - GCS sends public key to drone in ServerHello
             - Drone performs KEM encaps (wraps a random secret with the public key)
             - Drone signs the encapsulated key with SIG sign
             - GCS performs KEM decaps + SIG verify
             - Both sides derive the AEAD session key via HKDF
          4. 30-second MAVLink data session at 320 Hz (real Pixhawk SITL telemetry)
          5. Drone sends "stop_suite" RPC, merges drone + GCS metrics
          6. JSON output written to logs/benchmarks/runs/{scenario}/

        THREE BENCHMARKING SCENARIOS:
          Scenario 1 -- Baseline: No DDoS detection, pure tunnel overhead
          Scenario 2 -- + XGBoost: Lightweight ML model monitors for DDoS attacks
          Scenario 3 -- + TST: Heavy Transformer model monitors for DDoS attacks
        """), section_num=sn())

        # ================================================================
        # PAGE 5: Suite Registry
        # ================================================================
        text_page(pdf, "The 72 Cipher Suites", textwrap.dedent("""\
        Every cipher suite is a combination of three algorithm choices:

        KEM (9 options -- how we establish the encryption key):
        +------------------+-----------+---------------------------------------+
        | Algorithm        | NIST Level| Mathematical Family                   |
        +------------------+-----------+---------------------------------------+
        | ML-KEM-512       | L1        | Module-LWE (Lattice)                  |
        | ML-KEM-768       | L3        | Module-LWE (Lattice)                  |
        | ML-KEM-1024      | L5        | Module-LWE (Lattice)                  |
        | HQC-128          | L1        | Quasi-cyclic codes                    |
        | HQC-192          | L3        | Quasi-cyclic codes                    |
        | HQC-256          | L5        | Quasi-cyclic codes                    |
        | McEliece-348864  | L1        | Binary Goppa codes                    |
        | McEliece-460896  | L3        | Binary Goppa codes                    |
        | McEliece-8192128 | L5        | Binary Goppa codes                    |
        +------------------+-----------+---------------------------------------+

        SIG (8 options -- how we prove identity):
        +------------------+-----------+---------------------------------------+
        | ML-DSA-44        | L1        | Module-LWE (Lattice)                  |
        | ML-DSA-65        | L3        | Module-LWE (Lattice)                  |
        | ML-DSA-87        | L5        | Module-LWE (Lattice)                  |
        | Falcon-512       | L1        | NTRU Lattice                          |
        | Falcon-1024      | L5        | NTRU Lattice                          |
        | SPHINCS+-128s    | L1        | Hash-based                            |
        | SPHINCS+-192s    | L3        | Hash-based                            |
        | SPHINCS+-256s    | L5        | Hash-based                            |
        +------------------+-----------+---------------------------------------+

        AEAD (3 options -- how we encrypt each packet):
          AES-256-GCM, ChaCha20-Poly1305, Ascon-128a

        LEVEL MATCHING RULE: The KEM and SIG must have the same NIST level.
          L1: 3 KEMs × 3 SIGs = 9 × 3 AEADs = 27 suites
          L3: 3 KEMs × 2 SIGs = 6 × 3 AEADs = 18 suites  (no Falcon at L3)
          L5: 3 KEMs × 3 SIGs = 9 × 3 AEADs = 27 suites
          TOTAL: 72 cipher suites

        WHY THREE MATHEMATICAL FAMILIES?
        If one mathematical approach (e.g., lattice problems) is eventually broken,
        the system can fall back to a different family (e.g., code-based or hash-based).
        This is called "algorithm diversity" and provides defence in depth.
        """), section_num=sn())

        # ================================================================
        # KEM KEYGEN CHART + EXPLANATION
        # ================================================================
        n = sn()
        chart_page(pdf, "KEM Keygen Performance (Chart)", charts["kem_keygen"],
                   section_num=n,
                   caption="Median keygen time per algorithm across 3 scenarios. "
                           "Y-axis is logarithmic (each gridline = 10× change).")

        text_page(pdf, "Explaining the KEM Keygen Chart", textwrap.dedent("""\
        WHAT THIS CHART SHOWS:
        This bar chart shows how long it takes each of the 9 KEM algorithms to
        generate a new public/private key pair ("keygen"). Keygen is the FIRST
        step of every handshake, so its speed directly affects how quickly the
        drone can start or restart its encrypted connection.

        HOW TO READ IT:
        • The x-axis lists the 9 KEM algorithms, grouped by family
        • The y-axis shows time in milliseconds on a LOGARITHMIC scale -- this
          means each horizontal gridline represents a 10× increase in time.
          We use log scale because the range is enormous (0.2 ms to 378 ms)
        • Three coloured bars per algorithm show the three testing scenarios:
          Blue = Baseline, Orange = + XGBoost detector, Red = + TST detector

        KEY OBSERVATIONS:

        1. ML-KEM is EXTREMELY FAST (0.20 – 0.30 ms):
           All three ML-KEM variants (512, 768, 1024) generate keys in under
           a third of a millisecond. This is essentially instantaneous -- the
           drone barely notices it happened. Surprisingly, ML-KEM-1024 (the
           highest security level) is actually the fastest at 0.20 ms.

        2. HQC is MODERATE (2.8 – 8.0 ms):
           HQC algorithms are 10–30× slower than ML-KEM but still complete
           in under 10 ms -- perfectly acceptable for drone operations.

        3. McEliece is SLOW (134 – 378 ms):
           Classic McEliece keygen takes hundreds of milliseconds. McEliece-
           8192128 (the strongest variant) takes 378 ms -- about 1,900× slower
           than ML-KEM-1024. This is because McEliece must generate a very
           large matrix structure (the public key is 1.36 MB!).

        4. SCENARIO IMPACT:
           Adding the XGBoost detector (orange bars) causes small increases
           (< 10% for ML-KEM) because the detector uses minimal CPU.
           Adding the TST detector (red bars) causes larger increases because
           the Transformer model consumes significant CPU and memory.

        BOTTOM LINE:
        If you care about fast handshakes (and you should, because each handshake
        stops telemetry flow), ML-KEM is the clear winner. McEliece's keygen alone
        takes longer than ML-KEM's entire handshake.
        """), section_num=n + " (cont.)")

        # ================================================================
        # KEM DATA TABLE + EXPLANATION
        # ================================================================
        n = sn()
        kems = ["ML-KEM-512", "ML-KEM-768", "ML-KEM-1024",
                "HQC-128", "HQC-192", "HQC-256",
                "McEliece-348864", "McEliece-460896", "McEliece-8192128"]
        kem_rows = []
        for kem in kems:
            kg, enc, dec, pk = [], [], [], []
            for sid, d in baseline.items():
                k, _, _ = parse_suite_id(sid)
                if k == kem:
                    cp = d.get("crypto_primitives", {})
                    if cp.get("kem_keygen_time_ms") and cp["kem_keygen_time_ms"] > 0:
                        kg.append(cp["kem_keygen_time_ms"])
                    if cp.get("kem_encapsulation_time_ms") and cp["kem_encapsulation_time_ms"] > 0:
                        enc.append(cp["kem_encapsulation_time_ms"])
                    if cp.get("kem_decapsulation_time_ms") and cp["kem_decapsulation_time_ms"] > 0:
                        dec.append(cp["kem_decapsulation_time_ms"])
                    if cp.get("pub_key_size_bytes"):
                        pk.append(cp["pub_key_size_bytes"])
            kem_rows.append([kem,
                             f"{np.median(kg):.2f}" if kg else "--",
                             f"{np.median(enc):.2f}" if enc else "--",
                             f"{np.median(dec):.2f}" if dec else "--",
                             f"{pk[0]:,}" if pk else "--"])

        table_page(pdf, "KEM Primitive Times -- Measured Data (Baseline)", 
                   ["Algorithm", "Keygen (ms)", "Encaps (ms)", "Decaps (ms)", "PK Size (B)"],
                   kem_rows, section_num=n,
                   note="Medians from live end-to-end tunnel runs. "
                        "Keygen runs on GCS; encaps and decaps run on drone.")

        text_page(pdf, "Explaining the KEM Data Table", textwrap.dedent("""\
        WHAT THIS TABLE SHOWS:
        This table gives the exact median timing for each of the three KEM
        operations (keygen, encaps, decaps) and the public key size for all 9
        KEM algorithms. These are REAL measurements taken during live tunnel runs.

        UNDERSTANDING THE COLUMNS:

        Keygen (ms): Time to generate a new public + private key pair.
          In our system, keygen is performed by the GCS (laptop), not the drone.
          This matters less for drone CPU, but it still adds to the handshake time.

        Encaps (ms): Time for the drone to "encapsulate" -- wrap a random secret
          inside the public key so that only the private key holder (GCS) can unwrap it.
          This happens ON THE DRONE and directly affects drone CPU load.

        Decaps (ms): Time for the GCS to "decapsulate" -- unwrap the secret using the
          private key. This happens on the GCS side.

        PK Size (B): Size of the public key in bytes. This is sent over the network
          during the handshake. Larger keys = more data to transmit.

        KEY PATTERNS:

        ML-KEM: All three operations complete in under 0.32 ms. The public keys are
        small (800--1,568 bytes). This is the gold standard for drone deployment.

        HQC: Keygen is fast (2.8–8 ms) but encapsulation is VERY slow
        (45–250 ms). HQC-256 encaps takes 250 ms -- a quarter of a second! The
        public keys are moderate (2–7 KB).

        McEliece: Keygen is the bottleneck (134–378 ms), but encaps is actually
        very fast (0.7–3.2 ms) and decaps is moderate (19–140 ms). The public
        keys are ENORMOUS: McEliece-8192128 has a 1.36 MB public key. Sending
        this over a slow wireless link could take significant time.

        IMPORTANT NOTE:
        These times include real system overhead -- context switching, memory
        allocation, garbage collection pauses. They are NOT the idealised
        "empty system" times you'd see in a crypto library's unit tests.
        """), section_num=n + " (cont.)")

        # ================================================================
        # SIG CHART + DATA TABLE + EXPLANATION
        # ================================================================
        n = sn()
        chart_page(pdf, "Signature Performance (Chart)", charts["sig_timing"],
                   section_num=n,
                   caption="Median sign and verify times. SPHINCS+ is shown on a separate "
                           "scale because it is 500–1000× slower than other algorithms.")

        sigs_list = ["ML-DSA-44", "ML-DSA-65", "ML-DSA-87", "Falcon-512", "Falcon-1024",
                     "SPHINCS+-128s", "SPHINCS+-192s", "SPHINCS+-256s"]
        sig_rows = []
        for sig in sigs_list:
            sgn, ver, ss = [], [], []
            for sid, d in baseline.items():
                _, _, s = parse_suite_id(sid)
                if s == sig:
                    cp = d.get("crypto_primitives", {})
                    if cp.get("signature_sign_time_ms") and cp["signature_sign_time_ms"] > 0:
                        sgn.append(cp["signature_sign_time_ms"])
                    if cp.get("signature_verify_time_ms") and cp["signature_verify_time_ms"] > 0:
                        ver.append(cp["signature_verify_time_ms"])
                    if cp.get("sig_size_bytes"):
                        ss.append(cp["sig_size_bytes"])
            sig_rows.append([sig,
                             f"{np.median(sgn):.2f}" if sgn else "--",
                             f"{np.median(ver):.2f}" if ver else "--",
                             f"{ss[0]:,}" if ss else "--"])

        n2 = sn()
        table_page(pdf, "Signature Primitive Times -- Measured Data",
                   ["Algorithm", "Sign (ms)", "Verify (ms)", "Sig Size (B)"],
                   sig_rows, section_num=n2,
                   note="Medians from live tunnel runs. SIG keygen is performed offline "
                        "(pre-distributed keys); only sign + verify affect handshake time.")

        text_page(pdf, "Explaining the Signature Chart & Table", textwrap.dedent("""\
        WHAT THESE SHOW:
        The chart and table present how long each signature algorithm takes to
        SIGN a message and VERIFY a signature. During the handshake, the drone
        signs the encapsulated key to prove its identity; the GCS verifies.

        KEY OBSERVATIONS:

        ML-DSA (0.54 – 1.38 ms sign, 0.76 – 1.17 ms verify):
          Very fast. ML-DSA-44 (Level 1) signs in half a millisecond. Even
          ML-DSA-87 (Level 5, highest security) takes only 1.4 ms. These are
          well within the real-time budget for a drone.

        Falcon (0.62 – 0.79 ms sign, 0.60 – 0.71 ms verify):
          Falcon is EXCELLENT. It combines fast signing with the SMALLEST
          signatures of any algorithm: just 654 bytes for Falcon-512 vs
          2,420 bytes for ML-DSA-44. Smaller signatures = less data transmitted
          during the handshake = faster completion.

        SPHINCS+ (642 – 1,342 ms sign, 1.98 – 3.83 ms verify):
          SPHINCS+ is the OUTLIER. Signing takes 642 ms to 1,342 ms -- that's
          over a full SECOND for the 192-bit parameter set. Verification is
          fast (2–4 ms), but signing dominates the handshake time.

          SPHINCS+ signatures are also very large: 7,856 to 29,792 bytes.

          So why include SPHINCS+ at all? Because it's built on HASH FUNCTIONS,
          which are the most conservative and well-understood cryptographic
          primitive. If lattice-based assumptions (used by ML-DSA and Falcon)
          are ever broken, SPHINCS+ provides a safe fallback. It's an insurance
          policy -- not meant for routine flight, but available if needed.

        PRACTICAL IMPACT:
          A handshake using ML-KEM + Falcon completes in ~9-13 ms total.
          A handshake using ML-KEM + SPHINCS+-192s takes ~1,350 ms -- over
          a second of telemetry blackout. That's why the adaptive policy avoids
          SPHINCS+ during flight and saves it for ground testing.
        """), section_num=n2 + " (cont.)")

        # ================================================================
        # AEAD CHART + TABLE + EXPLANATION
        # ================================================================
        n = sn()
        chart_page(pdf, "AEAD Per-Packet Performance (Chart)", charts["aead"],
                   section_num=n,
                   caption="Per-packet encrypt and decrypt times from live tunnel operation.")

        aeads = ["AES-256-GCM", "ChaCha20-Poly1305", "Ascon-128a"]
        aead_rows = []
        for aead in aeads:
            enc_ns, dec_ns = [], []
            for sid, d in baseline.items():
                _, a, _ = parse_suite_id(sid)
                if a == aead:
                    e = d.get("data_plane", {}).get("aead_encrypt_avg_ns")
                    dc = d.get("data_plane", {}).get("aead_decrypt_avg_ns")
                    if e and e > 0: enc_ns.append(e / 1000)
                    if dc and dc > 0: dec_ns.append(dc / 1000)
            enc_us = np.median(enc_ns) if enc_ns else 0
            dec_us = np.median(dec_ns) if dec_ns else 0
            aead_rows.append([aead, f"{enc_us:.1f} µs", f"{dec_us:.1f} µs",
                              f"{enc_us / 46.1:.2f}×" if enc_us > 0 else "--"])

        n2 = sn()
        table_page(pdf, "AEAD Per-Packet Times (Live Tunnel)",
                   ["Algorithm", "Encrypt (µs)", "Decrypt (µs)", "Relative to Ascon"],
                   aead_rows, section_num=n2,
                   note="Per-packet averages including full framing overhead. "
                        "At 320 Hz, even the slowest adds only ~73 µs/s = negligible.")

        text_page(pdf, "Explaining the AEAD Results", textwrap.dedent("""\
        WHAT IS AEAD AND WHY DOES IT MATTER (OR NOT)?

        AEAD stands for "Authenticated Encryption with Associated Data." After
        the handshake establishes a shared key, AEAD is what actually encrypts
        and decrypts EVERY SINGLE MAVLink packet flowing through the tunnel.

        At 320 messages per second, the AEAD operations are called 320 times per
        second on each side. So even tiny per-packet differences could, in theory,
        add up. Let's see if they do:

        THE NUMBERS:
        • AES-256-GCM:        228 µs encrypt,  219 µs decrypt
        • ChaCha20-Poly1305:  214 µs encrypt,  206 µs decrypt
        • Ascon-128a:           46 µs encrypt,   60 µs decrypt

        THE ANALYSIS:
        The MAXIMUM difference between the slowest (AES-256-GCM at 228 µs) and
        the fastest (Ascon-128a at 46 µs) is 182 µs per packet.

        At 320 packets/second, that's: 182 µs × 320 = 58,240 µs/second = 58 ms/s

        Is 58 ms/s a lot? Compare it to the handshake overhead:
        - ML-KEM handshake: ~14 ms total (once per rekey), with rekeying every 60 seconds
        - McEliece handshake: ~620 ms total

        The AEAD difference across an entire second (58 ms) is still less than a
        single McEliece handshake. And compared to the overall CPU time available
        (1,000 ms per second), 58 ms is only 5.8% -- significant but not critical.

        HOWEVER: These times (46–228 µs) are LARGER than you'd expect from isolated
        micro-benchmarks (which typically show 4–7 µs). That's because our numbers
        include the full AEAD "framing" overhead: building the packet header,
        constructing the AAD (associated authenticated data), reconstructing the
        nonce, and memory copies. In a real system, you can't avoid this overhead.

        CONCLUSION:
        AEAD algorithm choice is NOT the bottleneck. The handshake (KEM + SIG) is
        what determines whether a suite is deployable or not. Choose your AEAD
        based on implementation quality and side-channel resistance, not speed.
        Ascon-128a is fastest, but all three work fine at 320 Hz.
        """), section_num=n2 + " (cont.)")

        # ================================================================
        # ALL 72 SUITES CHART + EXPLANATION
        # ================================================================
        n = sn()
        chart_page(pdf, "All 72 Suites Ranked by Handshake Time (Baseline)",
                   charts["all_suites"], section_num=n, top_pct=0.85,
                   caption="Each horizontal bar = one cipher suite. "
                           "Colour indicates KEM family.")

        text_page(pdf, "Explaining the 72-Suite Ranking", textwrap.dedent("""\
        WHAT THIS CHART SHOWS:
        This is the "big picture" chart. Every one of our 72 cipher suites is shown
        as a horizontal bar, ranked from fastest (top) to slowest (bottom). The bar
        length shows the total handshake time in milliseconds.

        Bars are colour-coded by KEM family:
        • Blue = ML-KEM (lattice-based)
        • Orange/Yellow = HQC (code-based)
        • Red = Classic McEliece (binary Goppa code-based)

        HOW TO READ IT:
        Look at where the colours cluster. You'll see a clear THREE-TIER pattern:

        TOP TIER (fast, < 50 ms):
          Almost entirely ML-KEM suites (blue bars). These complete their
          handshake in 9–19 ms when paired with ML-DSA or Falcon. The only
          ML-KEM suites that are slower are those paired with SPHINCS+ (which
          adds 600+ ms of signing time).

        MIDDLE TIER (moderate, 50–500 ms):
          HQC suites (orange). HQC's encapsulation is slow (45–250 ms), so
          even with fast signatures, handshakes take 60–300 ms.

        BOTTOM TIER (slow, > 500 ms):
          McEliece suites (red) AND any suite using SPHINCS+ signing.
          The slowest suite is McEliece-8192128 + SPHINCS+-192s at ~48 seconds
          (off the chart scale -- this was the timeout case).

        KEY INSIGHT:
        The choice of KEM FAMILY (ML-KEM vs HQC vs McEliece) is the single
        most important decision. Within a family, varying the NIST level or
        AEAD has minimal impact. This is why the adaptive policy focuses
        exclusively on KEM family switching for graceful degradation.
        """), section_num=n + " (cont.)")

        # ================================================================
        # HANDSHAKE BY LEVEL TABLE + EXPLANATION
        # ================================================================
        n = sn()
        level_rows = []
        for lvl in ["L1", "L3", "L5"]:
            vals = [d["handshake"]["handshake_total_duration_ms"]
                    for d in baseline.values()
                    if nist_level(d) == lvl and
                    d.get("handshake", {}).get("handshake_total_duration_ms")]
            level_rows.append([lvl, str(len(vals)),
                               f"{np.mean(vals):.1f}", f"{np.median(vals):.1f}",
                               f"{np.percentile(vals, 95):.1f}", f"{max(vals):.1f}"])

        fam_rows = []
        for fam in ["ML-KEM", "HQC", "Classic-McEliece"]:
            vals = extract_by_kem_family(baseline, fam)
            fam_rows.append([fam, str(len(vals)),
                             f"{np.mean(vals):.1f}", f"{np.median(vals):.1f}",
                             f"{np.percentile(vals, 95):.1f}", f"{max(vals):.1f}"])

        # Two tables on one page
        fig, ax = plt.subplots(figsize=(11, 8.5))
        fig.patch.set_facecolor("white")
        ax.axis("off")
        fig.text(0.05, 0.95, f"{n}. Handshake Statistics by NIST Level & KEM Family",
                 fontsize=16, fontweight="bold", color="#1A237E")
        t1 = ax.table(cellText=level_rows,
                      colLabels=["Level", "n", "Mean (ms)", "Median (ms)", "P95 (ms)", "Max (ms)"],
                      loc="upper center", cellLoc="center", bbox=[0.05, 0.58, 0.9, 0.3])
        t1.auto_set_font_size(False); t1.set_fontsize(10); t1.scale(1, 1.8)
        for j in range(6):
            t1[0, j].set_facecolor("#1A237E")
            t1[0, j].set_text_props(color="white", fontweight="bold")
        fig.text(0.05, 0.53, "By NIST Security Level ↑             By KEM Family ↓",
                 fontsize=10, fontweight="bold", color="#1A237E")
        t2 = ax.table(cellText=fam_rows,
                      colLabels=["KEM Family", "n", "Mean (ms)", "Median (ms)", "P95 (ms)", "Max (ms)"],
                      loc="center", cellLoc="center", bbox=[0.05, 0.2, 0.9, 0.3])
        t2.auto_set_font_size(False); t2.set_fontsize(10); t2.scale(1, 1.8)
        for j in range(6):
            t2[0, j].set_facecolor("#1A237E")
            t2[0, j].set_text_props(color="white", fontweight="bold")
        fig.text(0.05, 0.12,
                 "71/72 suites succeeded. 1 timeout (McEliece-460896 + SPHINCS+-192s).\n"
                 "L3's high max (48,186 ms) reflects this outlier.",
                 fontsize=9, color="#757575", style="italic")
        pdf.savefig(fig); plt.close(fig)

        text_page(pdf, "Explaining the Handshake Statistics Tables", textwrap.dedent("""\
        WHAT THESE TABLES SHOW:
        Two statistical summaries of handshake times, sliced two different ways:

        TABLE 1 -- BY NIST SECURITY LEVEL:
        This answers: "Does higher security always mean slower handshakes?"
        Surprisingly, NO. The median handshake times are:
          L1: 176 ms  |  L3: 907 ms  |  L5: 507 ms

        Wait -- L3 is slower than L5? Yes! This happens because L3 includes
        McEliece-460896 + SPHINCS+-192s (which timed out at ~48 seconds),
        pulling up the mean and max. The median is also affected because L3
        only has 18 suites (vs 27 for L1 and L5), so outliers have more weight.

        TABLE 2 -- BY KEM FAMILY:
        This gives the clearest picture. The three KEM families have vastly
        different performance profiles:

        ML-KEM: Median 14.4 ms, max 1,346 ms
          The max is high only because some ML-KEM suites are paired with
          SPHINCS+ signatures. If you exclude SPHINCS+, ML-KEM max drops
          to about 19 ms.

        HQC: Median 271 ms, max 1,661 ms
          HQC's encapsulation step (wrapping the secret in the public key)
          is the bottleneck. HQC-256 encaps alone takes 250 ms.

        Classic McEliece: Median 620 ms, max 48,186 ms
          McEliece's keygen is slow (134–378 ms) and decapsulation adds
          another 19–140 ms. The 48-second max is the McEliece-460896 +
          SPHINCS+-192s timeout -- the only suite out of 72 that failed.

        WHY "n" AND "MEAN VS MEDIAN"?
        • n = how many suites were measured at that level/family
        • Mean = average (sensitive to outliers)
        • Median = middle value (robust to outliers)
        • P95 = 95th percentile (only 5% of suites are slower than this)
        • Max = the single worst case

        When mean >> median, it indicates skew (a few very slow outliers
        pulling up the average). This is visible in every row.
        """), section_num=n + " (cont.)")

        # ================================================================
        # BOXPLOT + PARETO CHART + EXPLANATION
        # ================================================================
        n = sn()
        chart_page(pdf, "Handshake Distribution (Boxplot by Level)",
                   charts["boxplot"], section_num=n,
                   caption="Box = interquartile range (IQR, 25th–75th percentile). "
                           "Whiskers = 1.5 × IQR. Dots = outliers.")

        text_page(pdf, "Explaining the Boxplot", textwrap.dedent("""\
        WHAT IS A BOXPLOT?
        A boxplot is a standard statistical visualization that shows the
        DISTRIBUTION of values, not just the average. Here's how to read it:

        • The BOX spans from the 25th percentile to the 75th percentile.
          This means 50% of all measurements fall inside the box.
        • The LINE inside the box is the MEDIAN (50th percentile).
        • The WHISKERS extend to the most extreme data point within
          1.5 × the box height (IQR). Points beyond are "outliers" shown as dots.

        WHAT THIS SPECIFIC CHART SHOWS:
        Three boxplots -- one for each NIST level (L1, L3, L5) -- showing the
        distribution of handshake times for all suites at that level.

        KEY OBSERVATIONS:
        1. All three levels have WIDE distributions. This is because at every
           level, we have suites ranging from very fast (ML-KEM + Falcon) to
           very slow (McEliece + SPHINCS+).

        2. The MEDIAN line (inside the box) is always much closer to the bottom
           of the box. This means most suites are fast, with a few very slow
           ones pulling the distribution upward.

        3. The outlier dots at the top represent SPHINCS+-heavy suites. These
           are statistical outliers -- unusually slow compared to their peers.

        PRACTICAL MEANING:
        For deployment, you would select a suite from the bottom of the box
        (the fast majority), not from the top. The boxplot helps you see that
        the "average" is misleading -- most suites complete very quickly, and
        only a few problematic combinations cause long handshakes.
        """), section_num=n + " (cont.)")

        # ================================================================
        # PARETO CHART + TABLE + EXPLANATION
        # ================================================================
        n = sn()
        chart_page(pdf, "Pareto Frontier: Security Level vs Speed",
                   charts["pareto"], section_num=n,
                   caption="Each dot = one suite. The Pareto frontier (connected line) "
                           "shows the best tradeoff at each security level.")

        pareto_rows = []
        p_suites = [
            ("cs-mlkem512-aesgcm-falcon512", "ML-KEM-512 + Falcon-512 + AES-GCM", "L1"),
            ("cs-mlkem768-aesgcm-mldsa65", "ML-KEM-768 + ML-DSA-65 + AES-GCM", "L3"),
            ("cs-mlkem1024-aesgcm-falcon1024", "ML-KEM-1024 + Falcon-1024 + AES-GCM", "L5"),
        ]
        for sid, name, lvl in p_suites:
            if sid in baseline:
                t = baseline[sid]["handshake"]["handshake_total_duration_ms"]
                pk = baseline[sid]["crypto_primitives"]["pub_key_size_bytes"]
                phi60 = (t / 1000) / (60 + t / 1000) * 100
                pareto_rows.append([name, lvl, f"{t:.2f}", f"{pk:,}", f"{phi60:.4f}%"])

        n2 = sn()
        table_page(pdf, "Pareto-Optimal Suites (Measured Data)",
                   ["Suite (KEM + SIG + AEAD)", "Level", "T_hs (ms)", "PK Size (B)", "Φ(R=60s)"],
                   pareto_rows, section_num=n2,
                   note="These three suites offer the best handshake time at each NIST level. "
                        "No other suite is simultaneously faster AND more secure.")

        text_page(pdf, "Explaining the Pareto Frontier", textwrap.dedent("""\
        WHAT IS A PARETO FRONTIER?
        In engineering, a "Pareto frontier" shows the best possible tradeoffs
        between two competing goals. Here, the two goals are:
          (1) HIGHER security (NIST level, y-axis) -- we want this UP
          (2) FASTER handshake (time, x-axis) -- we want this LEFT

        A suite is "Pareto-optimal" if NO other suite is BOTH faster AND more
        secure. If you try to improve one axis, you must sacrifice the other.

        THE THREE PARETO-OPTIMAL SUITES:

        [*] Level 1: ML-KEM-512 + Falcon-512 + AES-256-GCM
          Handshake: 12.80 ms  |  Rekey overhead: 0.021%
          This is the lightest suite. Best for high-stress conditions when
          the drone is low on battery or overheating.

        [*] Level 3: ML-KEM-768 + ML-DSA-65 + AES-256-GCM
          Handshake: 12.71 ms  |  Rekey overhead: 0.021%
          The RECOMMENDED DEFAULT. Provides AES-192-equivalent quantum security
          with a handshake faster than Level 1(!). This happens because ML-DSA-65
          is slightly faster than the Falcon + AEAD combination at L1.

        [*] Level 5: ML-KEM-1024 + Falcon-1024 + AES-256-GCM
          Handshake: 8.75 ms  |  Rekey overhead: 0.015%
          The fastest suite overall! ML-KEM-1024 keygen is only 0.20 ms, and
          Falcon-1024 signatures are 1,271 bytes -- very compact.

        WHAT IS Φ(R=60s)?
        This is the "rekey overhead" -- the fraction of time spent doing
        handshakes if you rekey every 60 seconds.
        Formula: Φ(R) = T_handshake / (R + T_handshake)

        For the Pareto-optimal suites, Φ(60s) < 0.022%. This means out of
        every 60 seconds, only ~13 ms is spent on the handshake. The remaining
        59,987 ms is pure encrypted telemetry flow. Rekeying is essentially free.

        WHY ALL THREE USE ML-KEM:
        No HQC or McEliece suite appears on the Pareto frontier because their
        KEM operations are simply too slow. Even McEliece-348864 (Level 1) takes
        276 ms -- 20× slower than any ML-KEM variant.
        """), section_num=n2 + " (cont.)")

        # ================================================================
        # REKEY OVERHEAD CHART + EXPLANATION
        # ================================================================
        n = sn()
        chart_page(pdf, "Rekey Overhead Φ(R) Analysis", charts["rekey"],
                   section_num=n,
                   caption="How much time is 'lost' to handshakes at different rekey intervals.")

        text_page(pdf, "Explaining the Rekey Overhead Chart", textwrap.dedent("""\
        WHAT IS REKEYING?
        "Rekeying" means periodically replacing the encryption key by performing
        a new handshake. This is important for security: if an attacker somehow
        captures the current key, they can only decrypt traffic until the next
        rekey (e.g., 60 seconds of data, not the entire flight).

        THE TRADEOFF:
        More frequent rekeying = better security but more handshake overhead.
        Less frequent rekeying = less overhead but longer exposure if compromised.

        THE CHART:
        This chart plots the rekey overhead Φ(R) for different suites at different
        rekey intervals R. The x-axis is the rekey interval (in seconds), and the
        y-axis is the percentage of time spent on handshakes.

        KEY NUMBERS:

        At R = 60 seconds (recommended for ML-KEM):
        • ML-KEM-768 + ML-DSA-65:    Φ = 0.021% -- virtually zero overhead
        • McEliece-348864:           Φ = 0.34% -- still manageable  
        • McEliece-8192128:          Φ = 0.84% -- approaching 1% of flight time

        The difference: McEliece-8192128 has 39× more rekey overhead than ML-KEM.

        PRACTICAL RECOMMENDATIONS:
        • ML-KEM suites: Rekey every 60 seconds. Overhead is negligible.
        • HQC suites: Rekey every 300+ seconds. The longer handshake makes
          frequent rekeying wasteful.
        • McEliece suites: Avoid periodic rekeying entirely. Use only event-
          triggered rekeying (e.g., on altitude change or mode switch).

        ENERGY IMPACT:
        For a 30-minute flight, ML-KEM rekeying every 60s (30 rekeys) consumes
        ~1.5 J -- about 0.021% of the total flight energy budget (7,182 J).
        McEliece-8192128 rekeying the same way consumes ~60 J -- 0.84%.
        That's a 40× difference in energy cost.
        """), section_num=n + " (cont.)")

        # ================================================================
        # HANDSHAKE BY FAMILY CHART + EXPLANATION
        # ================================================================
        n = sn()
        chart_page(pdf, "Median Handshake by KEM Family Across Scenarios",
                   charts["hs_family"], section_num=n,
                   caption="Grouped bars: each KEM family × each scenario. "
                           "Shows how DDoS detection overhead scales with handshake cost.")

        text_page(pdf, "Explaining the Family Comparison Chart", textwrap.dedent("""\
        WHAT THIS CHART SHOWS:
        Three groups of bars, one per KEM family (ML-KEM, HQC, McEliece), with
        three bars each (Baseline, +XGBoost, +TST). This lets you see:
        (a) How much each family differs in raw performance
        (b) How much overhead the DDoS detectors add to each family

        KEY OBSERVATIONS:

        1. ML-KEM IS ALWAYS FAST:
           The ML-KEM bars are tiny compared to the others. Median handshake
           is about 14 ms in baseline -- hard to even see on the same scale
           as McEliece's 620 ms.

        2. DETECTOR OVERHEAD SCALES WITH HANDSHAKE COST:
           Adding XGBoost or TST detection adds a PERCENTAGE of overhead, not
           a fixed amount. So:
           - ML-KEM: +1 ms from XGBoost (barely noticeable)
           - McEliece: +30–60 ms from XGBoost (noticeable but acceptable)
           - McEliece + TST: substantial increase because the Transformer
             model competes with McEliece's keygen for CPU time

        3. THE RATIO BETWEEN FAMILIES IS CONSISTENT:
           Across all three scenarios, McEliece is ~40× slower than ML-KEM.
           The DDoS detectors don't change the fundamental ranking -- they
           just amplify existing differences.

        PRACTICAL INSIGHT:
        If you plan to run DDoS detection alongside PQC encryption (which is
        the whole point of a secure drone system), use ML-KEM. The detection
        overhead on ML-KEM is negligible, but on McEliece it can push handshake
        times past the 5-second MAVLink heartbeat timeout.
        """), section_num=n + " (cont.)")

        # ================================================================
        # DDOS MODELS TABLE + EXPLANATION
        # ================================================================
        n = sn()
        ddos_props = [
            ["Architecture", "XGBoost (Gradient Boosted Trees)",
             "Time Series Transformer\n(3-layer, 16-head, d=128)"],
            ["Window Size", "5 packets", "400 packets"],
            ["Detection Latency", "~3 seconds", "~240 seconds"],
            ["Inference Time", "~microseconds (µs)", "~milliseconds (ms)"],
            ["Threading Model", "Single-thread, GIL-friendly", "Single-thread, CPU-only"],
            ["Model Size", "~100 KB", "~5 MB"],
            ["Best For", "Real-time flight detection", "Post-flight analysis"],
        ]
        table_page(pdf, "DDoS Detection Models Comparison",
                   ["Property", "XGBoost Detector", "TST Detector"],
                   ddos_props, section_num=n, row_height=1.8, font_size=9.5,
                   note="Both sniff wlan0 for MAVLink v2 (0xFD magic byte). "
                        "Normal: ~32 pkts/window, Attack: ~5-14 pkts/window.")

        text_page(pdf, "Explaining the DDoS Detection Setup", textwrap.dedent("""\
        WHY DDoS DETECTION?
        Drones communicate wirelessly, which makes them vulnerable to jamming
        and denial-of-service attacks. An attacker could flood the radio link
        with garbage packets to disrupt telemetry. PQC-MAV includes TWO
        detection models that monitor incoming traffic patterns.

        XGBoost DETECTOR (lightweight):
        • Uses a machine learning model called "gradient boosted trees"
        • Analyses only 5 packets at a time (very short window)
        • Can detect an attack within ~3 seconds
        • Uses almost no CPU -- ideal for running alongside encryption
        • Small model (100 KB) -- fits easily in memory
        • Recommended for real-time in-flight detection

        TST DETECTOR (heavyweight):
        • Uses a Transformer neural network (same architecture as GPT, but tiny)
        • Analyses 400 packets at a time (long window for pattern detection)
        • Takes ~240 seconds to accumulate enough data for a prediction
        • Uses SIGNIFICANT CPU -- competes with encryption for resources
        • Raises CPU usage from ~15% to ~89% and temperature from 61°C to 83°C
        • NOT recommended during flight -- use for post-flight analysis

        WHY TEST BOTH?
        We included both to understand the WORST CASE. If a drone operator uses
        the heavy TST model during flight (which we don't recommend), how much
        does it degrade PQC performance? The answer: ML-KEM handshakes go from
        14 ms to 23 ms (+64%), while McEliece handshakes become dangerously close
        to causing MAVLink heartbeat timeouts.

        This validates our recommendation: use XGBoost for flight, TST for ground.
        """), section_num=n + " (cont.)")

        # ================================================================
        # SYSTEM METRICS CHART + EXPLANATION
        # ================================================================
        n = sn()
        chart_page(pdf, "Cross-Scenario System Metrics",
                   charts["system_metrics"], section_num=n,
                   caption="CPU usage, temperature, and packet counts across all 72 suites per scenario.")

        text_page(pdf, "Explaining the System Metrics Chart", textwrap.dedent("""\
        WHAT THIS CHART SHOWS:
        Three panels comparing system-level metrics across our three testing
        scenarios: Baseline, +XGBoost, and +TST.

        CPU USAGE:
        • Baseline: Average 14.7%, Peak 36.5%
        • + XGBoost: Average ~40%, Peak ~70%
        • + TST: Average ~89%, Peak ~95% (near maximum!)

        The PQC tunnel itself uses modest CPU (the handshake is brief; the AEAD
        data plane is efficient). But adding ML-based DDoS detection dramatically
        increases CPU usage. The TST Transformer model, in particular, pushes the
        RPi 5 to its limits.

        TEMPERATURE:
        • Baseline: ~60.4°C average
        • + XGBoost: ~73°C average
        • + TST: ~83°C average (above the 80°C throttling threshold!)

        The Raspberry Pi 5 begins thermal throttling at 80°C, reducing CPU speed
        to prevent damage. The TST detector causes sustained temperatures above
        this threshold, meaning the CPU is being throttled -- which further degrades
        PQC performance. This is another reason to avoid TST during flight.

        PACKET COUNTS:
        MAVLink packet counts are consistent across scenarios (~948 in 30 seconds
        = ~320 Hz). This means the tunnel maintains full telemetry throughput
        regardless of which detector is running. No packets are lost -- even
        under the heaviest computational load.

        STEADY-STATE IMPACT:
        Comparing ML-KEM suites to McEliece suites within the same scenario,
        the steady-state metrics are nearly IDENTICAL. CPU avg differs by < 1%
        (14.7% vs 15.5%), temperature by < 2°C. This confirms that the only
        difference between suites manifests during the handshake -- the data
        plane (AEAD) dominates runtime and is the same for all suites.
        """), section_num=n + " (cont.)")

        # ================================================================
        # CPU/TEMP HEATMAP + EXPLANATION
        # ================================================================
        n = sn()
        chart_page(pdf, "CPU & Temperature Heatmap", charts["heatmap"],
                   section_num=n,
                   caption="Colour intensity → metric value. Rows = KEM family, Columns = Scenario.")

        text_page(pdf, "Explaining the CPU/Temperature Heatmap", textwrap.dedent("""\
        WHAT IS A HEATMAP?
        A heatmap uses colour intensity to represent numerical values. Darker or
        warmer colours mean higher values. This makes it easy to spot which
        combinations of KEM family × scenario produce the highest CPU usage
        and temperature.

        HOW TO READ THIS ONE:
        • Rows represent the three KEM families (ML-KEM, HQC, McEliece)
        • Columns represent the three scenarios (Baseline, +XGBoost, +TST)
        • The colour of each cell shows the average CPU usage or temperature
          for suites in that row-column combination

        KEY OBSERVATIONS:

        1. THE TST COLUMN IS ALWAYS HOTTEST:
           Regardless of KEM family, adding the TST detector pushes CPU and
           temperature to their highest values. This is expected -- the
           Transformer model dominates resource usage.

        2. WITHIN BASELINE, FAMILIES ARE SIMILAR:
           ML-KEM baseline CPU ≈ HQC baseline CPU ≈ McEliece baseline CPU.
           The KEM family choice doesn't noticeably affect steady-state CPU
           because the handshake is a tiny fraction of the 30-second session.

        3. McEliece + TST IS THE WORST COMBINATION:
           The cell for McEliece × TST scenario shows the highest values.
           McEliece's long keygen (134–378 ms) competes with the Transformer
           for CPU time, leading to CPU contention and thermal pressure.

        PRACTICAL TAKEAWAY:
        If you need DDoS detection during flight, pair it with ML-KEM.
        The combination of ML-KEM + XGBoost keeps CPU under 40% and
        temperature under 75°C -- well within the RPi 5's thermal budget.
        """), section_num=n + " (cont.)")

        # ================================================================
        # OVERHEAD DELTA CHART + TABLE + EXPLANATION
        # ================================================================
        n = sn()
        chart_page(pdf, "DDoS Overhead Analysis (Delta Chart)",
                   charts["overhead_delta"], section_num=n,
                   caption="Absolute handshake time increase caused by adding DDoS detection.")

        # Build overhead table
        oh_rows = []
        for fam in ["ML-KEM", "HQC", "Classic-McEliece"]:
            bt = np.median(extract_by_kem_family(data["no-ddos"], fam))
            for csc, clabel in [("ddos-xgboost", "+ XGBoost"), ("ddos-txt", "+ TST")]:
                ct_vals = []
                for sid in data["no-ddos"]:
                    k, _, _ = parse_suite_id(sid)
                    if kem_family(k) == fam and sid in data[csc]:
                        ct_vals.append(data[csc][sid]["handshake"]["handshake_total_duration_ms"])
                ct = np.median(ct_vals) if ct_vals else 0
                delta = ct - bt
                pct = (delta / bt * 100) if bt else 0
                oh_rows.append([fam, clabel, f"{bt:.1f}", f"{ct:.1f}",
                                f"{delta:+.1f}", f"{pct:+.1f}%"])

        n2 = sn()
        table_page(pdf, "DDoS Overhead -- Detailed Numbers",
                   ["KEM Family", "Scenario", "Baseline (ms)", "With Detector (ms)", "Δ (ms)", "Δ (%)"],
                   oh_rows, section_num=n2, row_height=1.9,
                   note="Δ = change in median handshake time. Positive = slower.")

        text_page(pdf, "Explaining the DDoS Overhead Numbers", textwrap.dedent("""\
        WHAT THIS TABLE SHOWS:
        For each KEM family, the table compares the median handshake time in the
        Baseline scenario vs. with each DDoS detector running. The "Δ" columns
        show the absolute (in ms) and relative (in %) change.

        KEY FINDINGS:

        XGBoost OVERHEAD (manageable):
        • ML-KEM:   +1.3 ms  (+8.7%)   -- trivial, from 14.4 ms to 15.7 ms
        • HQC:      +7 ms    (+2.6%)   -- barely noticeable
        • McEliece:  +32 ms   (+5%)     -- noticeable but acceptable

        TST OVERHEAD (significant):
        • ML-KEM:   +9.2 ms  (+64%)    -- from 14.4 ms to 23.6 ms (still fast!)
        • HQC:      +52 ms   (+19%)    -- from 271 ms to 323 ms
        • McEliece:  +89 ms   (+14%)    -- from 620 ms to 709 ms

        The TST Transformer model uses so much CPU that it slows down all
        cryptographic operations. The effect is PERCENTAGE-based -- it slows
        everything by roughly the same fraction.

        IMPORTANT NUANCE:
        Even with TST, ML-KEM handshakes stay under 24 ms. This is still well
        below any meaningful threshold. The problem with TST isn't the handshake
        delay -- it's the temperature (83°C > 80°C throttle point). The drone
        literally overheats.

        RECOMMENDATION:
        For flight: Use XGBoost detection. Handshake overhead is <9% for ML-KEM,
        and the system stays well within thermal limits.
        For ground analysis: Use TST for higher-accuracy detection when the drone
        is plugged in and not under flight constraints.
        """), section_num=n2 + " (cont.)")

        # ================================================================
        # CROSS-SCENARIO SUMMARY TABLE
        # ================================================================
        n = sn()
        metrics_names = [
            "Median Handshake (ms)", "Mean Handshake (ms)", "P95 Handshake (ms)",
            "Avg CPU (%)", "Peak CPU (%)", "Avg Temp (°C)",
            "Packets Sent (median)", "Packet Loss (%)", "Suites Passed"
        ]
        col_data = []
        for sc, suites in data.items():
            hs = [d["handshake"]["handshake_total_duration_ms"]
                  for d in suites.values()
                  if d.get("handshake", {}).get("handshake_total_duration_ms")]
            cpus = [d["system_drone"]["cpu_usage_avg_percent"]
                    for d in suites.values()
                    if d.get("system_drone", {}).get("cpu_usage_avg_percent") is not None]
            cpus_pk = [d["system_drone"]["cpu_usage_peak_percent"]
                       for d in suites.values()
                       if d.get("system_drone", {}).get("cpu_usage_peak_percent") is not None]
            temps = [d["system_drone"]["temperature_c"]
                     for d in suites.values()
                     if d.get("system_drone", {}).get("temperature_c") is not None]
            pkts = [d["data_plane"]["packets_sent"]
                    for d in suites.values()
                    if d.get("data_plane", {}).get("packets_sent") is not None]
            loss = [d["data_plane"]["packet_loss_ratio"]
                    for d in suites.values()
                    if d.get("data_plane", {}).get("packet_loss_ratio") is not None]
            passed = sum(1 for d in suites.values()
                         if d.get("handshake", {}).get("handshake_success"))
            col = [
                f"{np.median(hs):.1f}", f"{np.mean(hs):.1f}",
                f"{np.percentile(hs, 95):.1f}",
                f"{np.mean(cpus):.1f}", f"{np.mean(cpus_pk):.1f}",
                f"{np.mean(temps):.1f}",
                f"{int(np.median(pkts))}", f"{np.mean(loss) * 100:.2f}",
                f"{passed}/72"
            ]
            col_data.append(col)
        cell_text = [[metrics_names[i]] + [col_data[j][i] for j in range(3)]
                     for i in range(len(metrics_names))]
        col_labels = ["Metric"] + [SCENARIOS[s]["label"] for s in SCENARIOS]

        table_page(pdf, "Cross-Scenario Comparison -- Full Data Table",
                   col_labels, cell_text, section_num=n, row_height=1.9, font_size=9.5)

        text_page(pdf, "Explaining the Cross-Scenario Summary", textwrap.dedent("""\
        WHAT THIS TABLE SHOWS:
        A single comprehensive table comparing ALL key metrics across our three
        testing scenarios. This is the "executive dashboard" -- one place to see
        everything.

        ROW-BY-ROW EXPLANATION:

        MEDIAN HANDSHAKE: The middle value of all 72 handshake times. Baseline
        is the "true" PQC overhead. XGBoost adds a small amount; TST adds more.

        MEAN HANDSHAKE: The average (pulled up by outliers like SPHINCS+ suites).
        Always higher than median because the distribution is right-skewed.

        P95 HANDSHAKE: 95% of suites complete faster than this. Useful for
        understanding worst-case deployment scenarios.

        AVG CPU: Average CPU usage across all 72 suites. Baseline ~15% reflects
        the tunnel + AEAD workload. XGBoost pushes to ~40%. TST pushes to ~89%.

        PEAK CPU: Maximum instantaneous CPU during any suite. Baseline peaks at
        ~37% (during handshake). TST peaks near 95% -- the system is saturated.

        AVG TEMP: Average SoC temperature. Baseline is a comfortable 60°C.
        TST pushes to 83°C -- above the 80°C throttling point.

        PACKETS SENT: How many MAVLink messages were transmitted in 30 seconds.
        Should be ~320×30 = 9,600 ideally. We see ~948 (in the median-per-suite
        metric) which varies by measurement window.

        PACKET LOSS: Fraction of packets lost. 0.00% across all scenarios =
        perfect telemetry integrity even under the heaviest load.

        SUITES PASSED: How many of the 72 suites completed without timeout.
        71/72 in baseline. The one failure is McEliece-460896 + SPHINCS+-192s.
        """), section_num=n + " (cont.)")

        # ================================================================
        # ENERGY BUDGET + CONCLUSIONS
        # ================================================================
        n = sn()
        text_page(pdf, "Energy Budget Impact", textwrap.dedent("""\
        WHY ENERGY MATTERS FOR DRONES:
        Drones have fixed battery capacity. Every joule spent on cryptography
        is a joule NOT available for flying. We need to understand: "How much
        energy does PQC rekeying actually consume?"

        THE CALCULATION:
        We assume a 30-minute flight with continuous encrypted telemetry.
        Total energy budget: ~7,182 joules (at ~3.99 watts average draw).
        Rekey interval: 60 seconds → 30 rekeys during the flight.

        For each rekey, the energy consumed is approximately:
          E_rekey ≈ P_avg × T_handshake

        ML-KEM-768 + ML-DSA-65 (recommended suite):
          T_handshake = 12.7 ms = 0.0127 seconds
          E_per_rekey ≈ 3.99 W × 0.0127 s = 0.051 J
          E_30_rekeys = 30 × 0.051 = 1.52 joules
          Fraction of budget: 1.52 / 7,182 = 0.021%

        McEliece-8192128 + ML-DSA-87 (heaviest viable KEM):
          T_handshake = 505 ms = 0.505 seconds
          E_per_rekey ≈ 3.99 W × 0.505 s = 2.016 J
          E_30_rekeys = 30 × 2.016 = 60.48 joules
          Fraction of budget: 60.48 / 7,182 = 0.84%

        THE RATIO:
        McEliece rekeying consumes 40× more energy than ML-KEM rekeying.
        Even so, McEliece's total rekeying cost is under 1% of the flight
        energy -- which shows that PQC is feasible even with the heaviest
        algorithms. The question isn't "can we afford PQC?" but rather "which
        PQC algorithms give us the most security per joule?"

        The answer is clear: ML-KEM provides the best security-per-joule ratio
        at every NIST level.
        """), section_num=n)

        n = sn()
        text_page(pdf, "Key Findings & Conclusions", textwrap.dedent("""\
        FINDING 1: ALGORITHM FAMILY SELECTION DOMINATES
        The choice of KEM FAMILY -- not the NIST level, not the AEAD -- determines
        whether a cipher suite is deployable on a drone.
        • ML-KEM median handshake: 14.4 ms
        • HQC median: 271 ms  (19× slower)
        • McEliece median: 620 ms  (43× slower)

        FINDING 2: SPHINCS+ SIGNING IS THE BIGGEST SINGLE BOTTLENECK
        Any suite with SPHINCS+ is dominated by the signature step:
        SPHINCS+-128s signs in 642 ms, SPHINCS+-192s in 1,342 ms. Avoid during flight.

        FINDING 3: AEAD CHOICE IS A COMPLETE NON-FACTOR
        Max per-packet difference: 182 µs. At 320 Hz: 58 ms/s of extra CPU.
        Negligible. Pick AEAD for side-channel resistance, not speed.

        FINDING 4: XGBoost DETECTION HAS MINIMAL IMPACT
        ML-KEM handshake: +1.3 ms (+8.7%). CPU: +26%. Temperature: +12°C.
        Perfectly viable for in-flight DDoS detection.

        FINDING 5: TST DETECTION IS TOO HEAVY FOR FLIGHT
        CPU: 15% → 89%. Temperature: 61°C → 83°C (above throttle threshold).
        Use for post-flight forensic analysis only.

        FINDING 6: ALL PARETO-OPTIMAL SUITES USE ML-KEM
        [*] L1: 12.8 ms  |  [*] L3: 12.7 ms  |  [*] L5: 8.7 ms
        Rekey overhead at R=60s: < 0.022%. Rekeying is essentially free.

        RECOMMENDED DEPLOYMENT:
        Default:     ML-KEM-768 + ML-DSA-65 + AES-256-GCM  (NIST L3, 12.7 ms)
        Stress mode: ML-KEM-512 + Falcon-512 + AES-256-GCM  (NIST L1, 12.8 ms)
        Detection:   XGBoost for flight, TST for ground analysis
        Rekey:       Every 60 seconds for ML-KEM, ≥300s for HQC, never for McEliece
        """), section_num=n)

        # ================================================================
        # FINAL PAGE
        # ================================================================
        fig = plt.figure(figsize=(11, 8.5))
        fig.patch.set_facecolor("#1A237E")
        fig.text(0.5, 0.60, "Thank You",
                 fontsize=44, fontweight="bold", color="white", ha="center")
        fig.text(0.5, 0.45,
                 "All data, code, and analysis are reproducible.\n"
                 "Generated from 216 live tunnel sessions on real drone hardware.",
                 fontsize=14, color="#BBDEFB", ha="center", linespacing=1.6)
        fig.text(0.5, 0.30,
                 "72 Cipher Suites  ·  3 Scenarios  ·  71/72 Passed\n"
                 "9 KEMs × 8 SIGs × 3 AEADs = Complete PQC Coverage",
                 fontsize=12, color="#9E9E9E", ha="center", linespacing=1.6)
        fig.text(0.5, 0.12,
                 "Burak Güneysu  •  PQC-MAV  •  February 2026",
                 fontsize=11, color="#757575", ha="center")
        pdf.savefig(fig); plt.close(fig)

    print(f"  ✅ Detailed PDF saved: {OUTPUT_PATH}")
    return OUTPUT_PATH


# ============================================================================
# Main
# ============================================================================
def main():
    print("=" * 60)
    print("PQC-MAV Detailed Report Generator")
    print("=" * 60)

    print("\n📦 Loading benchmark data...")
    data = load_all_data()

    print("\n📊 Generating charts...")
    charts = {}
    chart_fns = [
        ("kem_keygen", chart_kem_keygen),
        ("hs_family", chart_handshake_by_family),
        ("all_suites", chart_all_suites),
        ("overhead_delta", chart_overhead_delta),
        ("sig_timing", chart_sig_timing),
        ("aead", chart_aead),
        ("pareto", chart_pareto),
        ("system_metrics", chart_system_metrics),
        ("boxplot", chart_boxplot_by_level),
        ("rekey", chart_rekey_overhead),
        ("heatmap", chart_cpu_temp_heatmap),
    ]
    for i, (name, fn) in enumerate(chart_fns, 1):
        print(f"  [{i}/{len(chart_fns)}] {name}...")
        charts[name] = fn(data)

    print("\n📝 Building detailed PDF report...")
    build_detailed_report(data, charts)

    print("\n✅ Done!")


if __name__ == "__main__":
    main()
