#!/usr/bin/env python3
"""
Check if mean power converges despite noisy individual samples.
This validates whether our energy integration is reliable.
"""
import sys, time, statistics
sys.path.insert(0, "/home/dev/secure-tunnel")

from core.metrics_collectors import PowerCollector

pc = PowerCollector(backend="auto")

# Run 3 independent 3-second captures
results = []
for trial in range(3):
    print(f"\n[Trial {trial+1}/3] Sampling 1kHz for 3 seconds...")
    pc.start_sampling(rate_hz=1000.0)
    time.sleep(3.0)
    samples = pc.stop_sampling()
    stats = pc.get_energy_stats(samples)
    
    voltages = [s["voltage_v"] for s in samples if s.get("voltage_v")]
    powers = [s["power_w"] for s in samples if s.get("power_w")]
    
    result = {
        "n": len(samples),
        "rate": (len(samples)-1) / (samples[-1]["mono_time"] - samples[0]["mono_time"]),
        "v_mean": statistics.mean(voltages),
        "v_std": statistics.stdev(voltages),
        "p_mean": statistics.mean(powers),
        "p_std": statistics.stdev(powers),
        "energy_j": stats["energy_total_j"],
    }
    results.append(result)
    
    print(f"  Samples={result['n']} Rate={result['rate']:.0f}Hz")
    print(f"  V={result['v_mean']:.4f}±{result['v_std']:.4f}V")
    print(f"  P={result['p_mean']:.4f}±{result['p_std']:.4f}W")
    print(f"  E={result['energy_j']:.4f}J")
    
    time.sleep(0.5)  # Brief gap between trials

# Cross-trial consistency
print(f"\n{'='*60}")
print("CROSS-TRIAL CONSISTENCY")
print(f"{'='*60}")
p_means = [r["p_mean"] for r in results]
v_means = [r["v_mean"] for r in results]
e_vals = [r["energy_j"] for r in results]

print(f"  Power means: {[f'{p:.4f}W' for p in p_means]}")
print(f"  Power CV across trials: {statistics.stdev(p_means)/statistics.mean(p_means)*100:.2f}%")
print(f"  Voltage means: {[f'{v:.4f}V' for v in v_means]}")
print(f"  Energy values: {[f'{e:.4f}J' for e in e_vals]}")
print(f"  Energy CV across trials: {statistics.stdev(e_vals)/statistics.mean(e_vals)*100:.2f}%")

# Also test via MetricsAggregator path
print(f"\n{'='*60}")
print("METRICSAGGREGATOR PIPELINE TEST")
print(f"{'='*60}")
from core.metrics_aggregator import MetricsAggregator

agg = MetricsAggregator(role="drone", output_dir="/tmp/test_metrics_agg")
print(f"Power backend: {agg.power_collector.backend}")

# Simulate a suite lifecycle
agg.start_suite("test-kyber768-falcon512-aesgcm", {"kem": "Kyber768", "sig": "Falcon-512"})
time.sleep(3.0)  # Simulate 3-second suite
data = agg.finalize_suite()

# Check the power data in the output
print(f"  power_sensor_type: {data.power_energy.power_sensor_type}")
print(f"  power_sampling_rate_hz: {data.power_energy.power_sampling_rate_hz}")
print(f"  voltage_avg_v: {data.power_energy.voltage_avg_v}")
print(f"  current_avg_a: {data.power_energy.current_avg_a}")
print(f"  power_avg_w: {data.power_energy.power_avg_w}")
print(f"  power_peak_w: {data.power_energy.power_peak_w}")
print(f"  energy_total_j: {data.power_energy.energy_total_j}")
print(f"  energy_per_handshake_j: {data.power_energy.energy_per_handshake_j}")

# System drone too
print(f"\n  cpu_usage_avg: {data.system_drone.cpu_usage_avg_percent}")
print(f"  temperature_c: {data.system_drone.temperature_c}")
print(f"  memory_rss_mb: {data.system_drone.memory_rss_mb}")

print(f"\n{'='*60}")
print("RESULT: Power pipeline is " + ("WORKING" if data.power_energy.power_avg_w and data.power_energy.power_avg_w > 0 else "BROKEN"))
print(f"{'='*60}")
