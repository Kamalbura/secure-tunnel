#!/usr/bin/env python3
"""
Live XGBoost DDoS Detector
==========================
Sniffs MAVLink packets on the network interface, counts them in 0.6 s
windows, and feeds the last 5 counts to the XGBoost model for a live
binary prediction every window.

No CSV inference, no simulation — real packets, real predictions.

Usage (requires root for raw packet capture):
    sudo ~/nenv/bin/python xgb.py
    sudo ~/nenv/bin/python xgb.py --iface eth0        # custom interface
    sudo ~/nenv/bin/python xgb.py --window 0.5         # custom window
"""

import argparse
import os
import sys
import time
from collections import deque
from threading import Thread

import numpy as np
import xgboost as xgb

try:
    import scapy.all as scapy
except ImportError:
    print("Error: scapy not installed.  pip install scapy")
    sys.exit(1)

# ── Configuration ────────────────────────────────────────────────────
MODEL_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "xgboost_model.bin")
LOOKBACK = 5          # model input: 5 consecutive window counts
DEFAULT_WINDOW = 0.60 # seconds per counting window
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
    parser = argparse.ArgumentParser(description="Live XGBoost DDoS detector")
    parser.add_argument("--iface", default=DEFAULT_IFACE,
                        help="Network interface to sniff (default: wlan0)")
    parser.add_argument("--window", type=float, default=DEFAULT_WINDOW,
                        help="Counting window in seconds (default: 0.60)")
    args = parser.parse_args()

    # Load model
    if not os.path.exists(MODEL_FILE):
        print(f"Error: model file not found: {MODEL_FILE}")
        sys.exit(1)

    print(f"[XGB] Loading model from {MODEL_FILE}")
    model = xgb.XGBClassifier()
    model.load_model(MODEL_FILE)
    print(f"[XGB] Model loaded.  lookback={LOOKBACK}  window={args.window}s")

    # Start sniffer
    counter = PacketCounter(args.iface)
    counter.start()
    print(f"[XGB] Sniffing MAVLink packets on '{args.iface}'...")
    print(f"[XGB] Collecting first {LOOKBACK} windows "
          f"({LOOKBACK * args.window:.1f}s) before predictions start.\n")

    history = deque(maxlen=LOOKBACK)
    window_num = 0

    try:
        while True:
            time.sleep(args.window)
            pkt_count = counter.read_and_reset()
            history.append(pkt_count)
            window_num += 1

            if len(history) < LOOKBACK:
                print(f"  Collecting... window {window_num}/{LOOKBACK}  "
                      f"packets={pkt_count}")
                continue

            # No-traffic guard: all-zero windows → tunnel not active
            if sum(history) == 0:
                print(f"  [#{window_num}]  pkts={pkt_count:3d}  "
                      f"window={list(history)}  "
                      f"\033[93mNO TRAFFIC\033[0m")
                continue

            # Predict
            x = np.array(list(history)).reshape(1, -1)
            pred = model.predict(x)[0]
            proba = model.predict_proba(x)[0]
            conf = proba[pred] * 100

            if pred == 1:
                print(f"  [#{window_num}]  pkts={pkt_count:3d}  "
                      f"window={list(history)}  "
                      f"\033[91m>>> ATTACK  ({conf:.1f}%)\033[0m")
            else:
                print(f"  [#{window_num}]  pkts={pkt_count:3d}  "
                      f"window={list(history)}  "
                      f"\033[92mNORMAL  ({conf:.1f}%)\033[0m")

    except KeyboardInterrupt:
        print(f"\n[XGB] Stopped after {window_num} windows.")


if __name__ == "__main__":
    main()
