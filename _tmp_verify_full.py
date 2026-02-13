"""Verify all 3 phases and check power data quality across the full benchmark."""
import json, os, glob, statistics

run_base = 'logs/benchmarks/runs'
scenarios = ['no-ddos', 'ddos-xgboost', 'ddos-txt']

power_fields = ['voltage_avg_v', 'current_avg_a', 'power_avg_w',
                'energy_total_j', 'power_peak_w', 'power_sampling_rate_hz']

categories = [
    'run_context', 'crypto_identity', 'lifecycle', 'handshake',
    'crypto_primitives', 'rekey', 'data_plane', 'latency_jitter',
    'mavproxy_drone', 'mavproxy_gcs', 'mavlink_integrity', 'fc_telemetry',
    'control_plane', 'system_drone', 'system_gcs', 'power_energy',
    'observability', 'validation'
]

for scenario in scenarios:
    sdir = os.path.join(run_base, scenario)
    files = glob.glob(os.path.join(sdir, '*_drone.json'))
    files = [f for f in files if '_archived' not in f]
    
    # Deduplicate by suite_id
    suites = {}
    for f in files:
        data = json.load(open(f))
        ci = data.get('crypto_identity', {})
        sid = (ci.get('kem_algorithm') or '') + '-' + \
              (ci.get('aead_algorithm') or '') + '-' + \
              (ci.get('sig_algorithm') or '')
        if sid not in suites or os.path.getsize(f) > os.path.getsize(suites[sid][1]):
            suites[sid] = (data, f)
    
    unique_count = len(suites)
    
    # Collect stats
    powers = []
    voltages = []
    energies = []
    cat_issues = 0
    power_issues = 0
    hs_issues = 0
    pass_count = 0
    
    for sid, (data, f) in suites.items():
        # Categories
        missing = [c for c in categories if c not in data]
        if missing:
            cat_issues += 1
        
        # Power
        pe = data.get('power_energy', {})
        pok = all((pe.get(k) or 0) > 0 for k in power_fields)
        if not pok:
            power_issues += 1
        else:
            powers.append(pe.get('power_avg_w', 0))
            voltages.append(pe.get('voltage_avg_v', 0))
            energies.append(pe.get('energy_total_j', 0))
        
        # Handshake
        hs = data.get('handshake', {})
        if not hs.get('handshake_success', False):
            hs_issues += 1
        
        # Validation
        val = data.get('validation', {})
        if val.get('benchmark_pass_fail', 'FAIL') == 'PASS':
            pass_count += 1
    
    print(f'\n{"="*60}')
    print(f'  PHASE: {scenario.upper()}')
    print(f'{"="*60}')
    print(f'  Total drone files: {len(files)} (unique suites: {unique_count})')
    print(f'  Category issues: {cat_issues}/{unique_count}')
    print(f'  Handshake issues: {hs_issues}/{unique_count}')
    print(f'  Power issues: {power_issues}/{unique_count}')
    print(f'  Validation PASS: {pass_count}/{unique_count}')
    
    if powers:
        print(f'\n  Power Stats:')
        print(f'    Voltage: {statistics.mean(voltages):.3f} ± {statistics.stdev(voltages):.3f} V')
        print(f'    Power:   {statistics.mean(powers):.3f} ± {statistics.stdev(powers):.3f} W')
        print(f'    Energy:  {statistics.mean(energies):.2f} ± {statistics.stdev(energies):.2f} J')
        print(f'    Power range: {min(powers):.3f} - {max(powers):.3f} W')

print(f'\n{"="*60}')
print(f'  BENCHMARK VERIFICATION COMPLETE')
print(f'{"="*60}')
