#!/usr/bin/env python3
"""Quick check of handshake timing in new run JSON files."""
import json, glob, sys
run_id = sys.argv[1] if len(sys.argv) > 1 else "20260207_172159"
files = sorted(glob.glob(f"logs/benchmarks/live_run_{run_id}/comprehensive/*_drone.json"))
print(f"Drone JSON files: {len(files)}")
for f in files:
    try:
        data = json.load(open(f))
        hs = data.get("handshake", {})
        sid = data.get("run_context", {}).get("suite_id", "?")
        total = hs.get("handshake_total_duration_ms")
        proto = hs.get("protocol_handshake_duration_ms")
        match = "OK" if total and proto and abs(total - proto) < 0.001 else "MISMATCH"
        print(f"  {sid[:55]:55s}  total={total:>10.3f}  proto={proto:>10.3f}  [{match}]")
    except Exception as e:
        print(f"  ERROR: {f}: {e}")
