"""Verify all metric categories in smoke test JSONs."""
import json, os, glob

run_dir = 'logs/benchmarks/runs/no-ddos'
files = glob.glob(os.path.join(run_dir, '*_drone.json'))
files = [f for f in files if '_archived' not in f]
print(f'Found {len(files)} drone JSONs\n')

categories = [
    'run_context', 'crypto_identity', 'lifecycle', 'handshake',
    'crypto_primitives', 'rekey', 'data_plane', 'latency_jitter',
    'mavproxy_drone', 'mavproxy_gcs', 'mavlink_integrity', 'fc_telemetry',
    'control_plane', 'system_drone', 'system_gcs', 'power_energy',
    'observability', 'validation'
]

power_fields = ['voltage_avg_v', 'current_avg_a', 'power_avg_w',
                'energy_total_j', 'power_peak_w', 'power_sampling_rate_hz']

all_ok = True
for f in sorted(files):
    name = os.path.basename(f)
    data = json.load(open(f))

    missing_cats = [c for c in categories if c not in data]
    present_cats = [c for c in categories if c in data]

    pe = data.get('power_energy', {})
    power_ok = all(pe.get(k, 0) > 0 for k in power_fields)
    sensor = pe.get('power_sensor_type', 'MISSING')

    hs = data.get('handshake', {})
    hs_ok = hs.get('handshake_success', False)
    hs_ms = hs.get('handshake_total_duration_ms', 0)

    dp = data.get('data_plane', {})
    ptx = dp.get('ptx_in', 0)

    sd = data.get('system_drone', {})
    cpu = sd.get('cpu_usage_avg_percent', 0)
    temp = sd.get('temperature_c', 0)

    val = data.get('validation', {})
    bench_pass = val.get('benchmark_pass_fail', 'FAIL')

    suite_ok = (not missing_cats) and power_ok and hs_ok and bench_pass == 'PASS'
    if not suite_ok:
        all_ok = False

    print(f'--- {name[:65]} ---')
    cat_status = 'PASS' if not missing_cats else f'MISS: {missing_cats}'
    print(f'  Categories: {len(present_cats)}/{len(categories)} ({cat_status})')
    print(f'  Handshake: {"OK" if hs_ok else "FAIL"} ({hs_ms:.1f}ms)')
    print(f'  Data plane: ptx_in={ptx}, enc_out={dp.get("enc_out",0)}')
    print(f'  Power: sensor={sensor}, V={pe.get("voltage_avg_v",0):.3f}V, '
          f'I={pe.get("current_avg_a",0):.3f}A, P={pe.get("power_avg_w",0):.3f}W, '
          f'E={pe.get("energy_total_j",0):.3f}J, peak={pe.get("power_peak_w",0):.3f}W')
    print(f'  Power rate: {pe.get("power_sampling_rate_hz",0):.0f}Hz | all_nonzero={power_ok}')
    print(f'  System: cpu={cpu:.1f}%, temp={temp:.1f}C, rss={sd.get("memory_rss_mb",0):.1f}MB')
    print(f'  Crypto: kem_keygen={data.get("crypto_primitives",{}).get("kem_keygen_time_ms",0):.2f}ms')
    print(f'  Validation: {bench_pass}')
    print(f'  Suite verdict: {"PASS" if suite_ok else "FAIL"}')
    print()

status = "ALL PASS" if all_ok else "SOME FAILED"
print(f'========================================')
print(f'SMOKE TEST RESULT: {status} ({len(files)} suites)')
print(f'========================================')
