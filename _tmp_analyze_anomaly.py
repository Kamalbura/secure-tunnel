#!/usr/bin/env python3
"""Analyze the DDoS benchmark results for anomalies."""
import json, statistics

SRC = "/home/dev/secure-tunnel/bench_ddos_results/20260209_090851"

for phase in ["baseline", "xgb", "tst"]:
    d = json.load(open(f"{SRC}/{phase}.json"))
    r = d["results"]
    
    cpus = [x["cpu_avg"] for x in r]
    temps = [x["temp_c"] for x in r]
    loads = [x["load_avg"] for x in r]
    means = [x["mean_us"] for x in r if x.get("mean_us")]
    iters = [x["iterations"] for x in r]
    
    print(f"\n=== {phase.upper()} ===")
    print(f"  Timestamp:  {d['timestamp']}")
    print(f"  Elapsed:    {d['phase_elapsed_s']}s")
    print(f"  Suites:     {len(r)}")
    print(f"  CPU:        mean={statistics.mean(cpus):.1f}%, range={min(cpus):.1f}-{max(cpus):.1f}%")
    print(f"  Temp:       mean={statistics.mean(temps):.1f}C, range={min(temps):.1f}-{max(temps):.1f}C")
    print(f"  Load:       mean={statistics.mean(loads):.2f}, range={min(loads):.2f}-{max(loads):.2f}")
    print(f"  Handshake:  mean={statistics.mean(means)/1000:.1f}ms, median={statistics.median(means)/1000:.1f}ms")
    print(f"  Iterations: mean={statistics.mean(iters):.0f}, range={min(iters)}-{max(iters)}")
    
    # Check temperature trend (first 10 vs last 10)
    if len(temps) > 20:
        first10 = statistics.mean(temps[:10])
        last10 = statistics.mean(temps[-10:])
        print(f"  Temp trend: first 10 suites={first10:.1f}C, last 10={last10:.1f}C (delta={last10-first10:+.1f}C)")
    
    # Show the McEliece-8192128 suites (heaviest) to see if they're anomalous
    print(f"\n  Heavy suites (McEliece-8192128):")
    for x in r:
        if "classicmceliece8192128" in x["suite_id"]:
            m = x["mean_us"]/1000
            print(f"    {x['suite_id']:<60s} mean={m:8.1f}ms  iters={x['iterations']:3d}  cpu={x['cpu_avg']:5.1f}%  temp={x['temp_c']:.1f}C")

    # Show ML-KEM-512 suites (lightest)
    print(f"\n  Light suites (ML-KEM-512):")
    for x in r:
        if "mlkem512" in x["suite_id"]:
            m = x["mean_us"]/1000
            print(f"    {x['suite_id']:<60s} mean={m:8.1f}ms  iters={x['iterations']:3d}  cpu={x['cpu_avg']:5.1f}%  temp={x['temp_c']:.1f}C")

# Check current governor
import subprocess
gov = open("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor").read().strip()
freq = int(open("/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq").read().strip())
print(f"\n=== CURRENT SYSTEM STATE ===")
print(f"  Governor: {gov}")
print(f"  CPU freq: {freq/1000:.0f} MHz")
print(f"  Temp: {int(open('/sys/class/thermal/thermal_zone0/temp').read().strip())/1000:.1f}C")
