#!/usr/bin/env python3
"""
Live TST (Time Series Transformer) DDoS Detector
=================================================
Sniffs MAVLink packets on the network interface, counts them in 0.6 s
windows, accumulates 400 counts, and runs the TST model for a live
prediction.  After the first prediction it slides by one window and
predicts continuously.

No CSV inference, no simulation — real packets, real predictions.

The TST model has c_out=1 (single output neuron).  Output is
interpreted via sigmoid:  P(attack) = 1 / (1 + exp(-logit)).

Usage (requires root for raw packet capture):
    sudo ~/nenv/bin/python tst.py
    sudo ~/nenv/bin/python tst.py --iface eth0
    sudo ~/nenv/bin/python tst.py --window 0.5
"""

import argparse
import os
import sys
import time
from collections import deque
from threading import Thread

import numpy as np
import pandas as pd
import torch
from sklearn.preprocessing import StandardScaler

# TST model classes must be importable for torch.load (pickle)
from tstplus import TSTPlus, _TSTBackbone, _TSTEncoder, _TSTEncoderLayer

try:
    import scapy.all as scapy
except ImportError:
    print("Error: scapy not installed.  pip install scapy")
    sys.exit(1)

# ── Configuration ────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_FILE = os.path.join(SCRIPT_DIR, "tst_model.pth")
TRAIN_DATA_FILE = os.path.join(SCRIPT_DIR, "train_ddos_data_0.1.csv")
SEQ_LENGTH = 400       # model input: 400 consecutive window counts
DEFAULT_WINDOW = 0.60  # seconds per counting window
DEFAULT_IFACE = "wlan0"

# ── Packet Sniffer ───────────────────────────────────────────────────
class PacketCounter:
    """Thread-safe live MAVLink packet counter."""

    def __init__(self, iface: str):
        self.iface = iface
        self._count = 0

    def _callback(self, pkt):
        if scapy.IP in pkt and scapy.UDP in pkt and scapy.Raw in pkt:
            if pkt[scapy.Raw].load[:1] == b'\xfd':   # MAVLink v2 magic
                self._count += 1

    def start(self):
        t = Thread(target=scapy.sniff,
                   kwargs={"prn": self._callback, "store": 0,
                           "iface": self.iface},
                   daemon=True)
        t.start()

    def read_and_reset(self) -> int:
        c = self._count
        self._count = 0
        return c

# ── Main Loop ────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Live TST DDoS detector")
    parser.add_argument("--iface", default=DEFAULT_IFACE,
                        help="Network interface to sniff (default: wlan0)")
    parser.add_argument("--window", type=float, default=DEFAULT_WINDOW,
                        help="Counting window in seconds (default: 0.60)")
    args = parser.parse_args()

    # ── Load model ───────────────────────────────────────────────────
    for f in [MODEL_FILE, TRAIN_DATA_FILE]:
        if not os.path.exists(f):
            print(f"Error: required file not found: {f}")
            sys.exit(1)

    print(f"[TST] Loading model from {MODEL_FILE}")
    model = torch.load(MODEL_FILE, map_location=torch.device("cpu"),
                       weights_only=False)
    model.eval()
    print(f"[TST] Model loaded.  c_out={model.c_out}  seq_len={model.seq_len}")

    # ── Fit scaler on training data ──────────────────────────────────
    print(f"[TST] Fitting scaler on {TRAIN_DATA_FILE}")
    train_data = pd.read_csv(TRAIN_DATA_FILE)
    scaler = StandardScaler()
    scaler.fit(train_data[["Mavlink_Count", "Total_length"]])
    print("[TST] Scaler ready.")

    # ── Start sniffer ────────────────────────────────────────────────
    counter = PacketCounter(args.iface)
    counter.start()
    collect_time = SEQ_LENGTH * args.window
    print(f"[TST] Sniffing MAVLink packets on '{args.iface}'...")
    print(f"[TST] Need {SEQ_LENGTH} windows ({collect_time:.0f}s / "
          f"{collect_time / 60:.1f}min) before first prediction.\n")

    history = deque(maxlen=SEQ_LENGTH)
    window_num = 0
    prediction_num = 0

    try:
        while True:
            time.sleep(args.window)
            pkt_count = counter.read_and_reset()
            history.append(pkt_count)
            window_num += 1

            # Still collecting initial data
            if len(history) < SEQ_LENGTH:
                if window_num % 50 == 0 or window_num <= 5:
                    elapsed = window_num * args.window
                    remaining = (SEQ_LENGTH - window_num) * args.window
                    print(f"  Collecting... {window_num}/{SEQ_LENGTH}  "
                          f"({elapsed:.0f}s elapsed, ~{remaining:.0f}s remaining)  "
                          f"last_pkts={pkt_count}")
                continue

            # ── No-traffic guard ──────────────────────────────────
            if sum(history) == 0:
                prediction_num += 1
                print(f"  [Pred #{prediction_num}]  avg_pkts=  0.0  "
                      f"\033[93mNO TRAFFIC\033[0m")
                continue

            # ── Predict ──────────────────────────────────────────────
            t0 = time.perf_counter()

            seq = np.array(list(history), dtype=np.float64).reshape(-1, 1)
            dummy = np.zeros_like(seq)
            scaled = scaler.transform(np.hstack([seq, dummy]))[:, 0]
            x = torch.tensor(scaled, dtype=torch.float32) \
                     .unsqueeze(0).unsqueeze(0)  # [1, 1, 400]

            with torch.no_grad():
                logit = model(x).item()

            # c_out=1 → sigmoid interpretation
            prob_attack = 1.0 / (1.0 + np.exp(-logit))
            pred = 1 if prob_attack > 0.5 else 0

            dt_ms = (time.perf_counter() - t0) * 1000
            prediction_num += 1
            avg_pkt = np.mean(list(history))

            if pred == 1:
                print(f"  [Pred #{prediction_num}]  avg_pkts={avg_pkt:5.1f}  "
                      f"logit={logit:8.3f}  P(attack)={prob_attack:.4f}  "
                      f"{dt_ms:.0f}ms  "
                      f"\033[91m>>> ATTACK\033[0m")
            else:
                print(f"  [Pred #{prediction_num}]  avg_pkts={avg_pkt:5.1f}  "
                      f"logit={logit:8.3f}  P(attack)={prob_attack:.4f}  "
                      f"{dt_ms:.0f}ms  "
                      f"\033[92mNORMAL\033[0m")

    except KeyboardInterrupt:
        print(f"\n[TST] Stopped after {window_num} windows, "
              f"{prediction_num} predictions.")


if __name__ == "__main__":
    main()
