"""Check power_energy from all three phases."""
import json, glob, os, statistics

for scenario in ["no-ddos", "ddos-xgboost", "ddos-txt"]:
    sdir = os.path.join("logs", "benchmarks", "runs", scenario)
    files = glob.glob(os.path.join(sdir, "*_drone.json"))
    files = [f for f in files if "_archived" not in f]
    
    voltages = []
    currents = []
    powers = []
    for f in files:
        d = json.load(open(f))
        pe = d.get("power_energy", {})
        v = pe.get("voltage_avg_v")
        c = pe.get("current_avg_a")
        p = pe.get("power_avg_w")
        if v and v > 0:
            voltages.append(v)
        if c and c > 0:
            currents.append(c)
        if p and p > 0:
            powers.append(p)
    
    if voltages:
        print(f"\n{scenario} ({len(voltages)} suites with power data):")
        print(f"  Voltage: {statistics.mean(voltages):.4f} ± {statistics.stdev(voltages):.4f} V  "
              f"(min={min(voltages):.4f}, max={max(voltages):.4f})")
        print(f"  Current: {statistics.mean(currents):.4f} ± {statistics.stdev(currents):.4f} A  "
              f"(min={min(currents):.4f}, max={max(currents):.4f})")
        print(f"  Power:   {statistics.mean(powers):.4f} ± {statistics.stdev(powers):.4f} W  "
              f"(min={min(powers):.4f}, max={max(powers):.4f})")
    else:
        print(f"\n{scenario}: NO POWER DATA")
