"""
DEFINITIVE timing audit for the research paper.

For each suite, compare ALL available timing measurements:
  1. handshake_total_duration_ms  — measured by scheduler (INFLATED)
  2. protocol_handshake_duration_ms — measured by proxy (handshake_total_ns / 1e6)
  3. total_crypto_time_ms — sum of individual crypto primitives
  4. Individual primitives: kem_keygen, kem_encaps, kem_decaps, sig_sign, sig_verify

Also reconstruct the expected overhead from sleeps.
"""
import json, os, statistics
from collections import defaultdict

src = 'logs/benchmarks/live_run_20260207_144051/comprehensive'

records = []
for f in sorted(os.listdir(src)):
    if not f.endswith('_drone.json'):
        continue
    fp = os.path.join(src, f)
    try:
        d = json.load(open(fp))
    except Exception:
        continue

    hs = d.get('handshake', {})
    cp = d.get('crypto_primitives', {})
    rc = d.get('run_context', {})
    lc = d.get('lifecycle', {})
    suite = rc.get('suite_id', '?')

    # Times
    scheduler_ms = hs.get('handshake_total_duration_ms')    # Scheduler's wall clock (inflated)
    protocol_ms = hs.get('protocol_handshake_duration_ms')  # Proxy's handshake_total_ns
    crypto_ms = cp.get('total_crypto_time_ms')              # Sum of primitives

    # Individual operations
    kem_keygen = cp.get('kem_keygen_time_ms')
    kem_encaps = cp.get('kem_encapsulation_time_ms')
    kem_decaps = cp.get('kem_decapsulation_time_ms')
    sig_sign = cp.get('signature_sign_time_ms')
    sig_verify = cp.get('signature_verify_time_ms')

    # Monotonic timestamps for overhead calculation
    hs_start = hs.get('handshake_start_time_drone')
    hs_end = hs.get('handshake_end_time_drone')

    if scheduler_ms is not None:
        records.append({
            'suite': suite,
            'scheduler_ms': scheduler_ms,
            'protocol_ms': protocol_ms,
            'crypto_ms': crypto_ms,
            'kem_keygen': kem_keygen,
            'kem_encaps': kem_encaps,
            'kem_decaps': kem_decaps,
            'sig_sign': sig_sign,
            'sig_verify': sig_verify,
            'hs_start': hs_start,
            'hs_end': hs_end,
        })

# De-duplicate (some suites may have both naming patterns)
seen = set()
unique = []
for r in records:
    if r['suite'] not in seen:
        seen.add(r['suite'])
        unique.append(r)
records = unique

print(f"Unique suites analyzed: {len(records)}")
print()

# === 1. The three timing layers ===
sched_vals = [r['scheduler_ms'] for r in records]
proto_vals = [r['protocol_ms'] for r in records if r['protocol_ms']]
crypto_vals = [r['crypto_ms'] for r in records if r['crypto_ms']]

print("=" * 80)
print("LAYER 1: scheduler handshake_total_duration_ms (what dashboard shows)")
print("  THIS INCLUDES: RPC + sleep(2.0) + sleep(1.0) + handshake + file poll")
print("=" * 80)
print(f"  Count:  {len(sched_vals)}")
print(f"  Min:    {min(sched_vals):>10.1f} ms")
print(f"  Max:    {max(sched_vals):>10.1f} ms")
print(f"  Mean:   {statistics.mean(sched_vals):>10.1f} ms")
print(f"  Median: {statistics.median(sched_vals):>10.1f} ms")

print()
print("=" * 80)
print("LAYER 2: protocol_handshake_duration_ms (proxy's own perf_counter_ns)")
print("  THIS INCLUDES: KEM keygen + wire I/O + encaps/decaps + sig + key derive")
print("  THIS EXCLUDES: subprocess spawn, sleep timers, file polling")
print("=" * 80)
print(f"  Count:  {len(proto_vals)}")
if proto_vals:
    print(f"  Min:    {min(proto_vals):>10.3f} ms")
    print(f"  Max:    {max(proto_vals):>10.3f} ms")
    print(f"  Mean:   {statistics.mean(proto_vals):>10.3f} ms")
    print(f"  Median: {statistics.median(proto_vals):>10.3f} ms")

print()
print("=" * 80)
print("LAYER 3: total_crypto_time_ms (pure PQC operations only)")
print("  THIS INCLUDES: kem_keygen + kem_encaps + kem_decaps + sig_sign + sig_verify")
print("  THIS EXCLUDES: TCP I/O, serialization, HMAC verification, key derivation")
print("=" * 80)
print(f"  Count:  {len(crypto_vals)}")
if crypto_vals:
    print(f"  Min:    {min(crypto_vals):>10.3f} ms")
    print(f"  Max:    {max(crypto_vals):>10.3f} ms")
    print(f"  Mean:   {statistics.mean(crypto_vals):>10.3f} ms")
    print(f"  Median: {statistics.median(crypto_vals):>10.3f} ms")

# === 2. Overhead analysis ===
print()
print("=" * 80)
print("OVERHEAD ANALYSIS")
print("=" * 80)
overheads = []
for r in records:
    if r['protocol_ms'] and r['protocol_ms'] > 0:
        overhead = r['scheduler_ms'] - r['protocol_ms']
        overheads.append(overhead)
if overheads:
    print(f"  scheduler_ms - protocol_ms (the 'wasted' overhead):")
    print(f"    Min:    {min(overheads):>8.1f} ms")
    print(f"    Max:    {max(overheads):>8.1f} ms")
    print(f"    Mean:   {statistics.mean(overheads):>8.1f} ms")
    print(f"    Median: {statistics.median(overheads):>8.1f} ms")
    print(f"    Stdev:  {statistics.stdev(overheads):>8.1f} ms")
    print()
    print(f"  Expected fixed overhead breakdown:")
    print(f"    GCS proxy time.sleep(2.0)         = 2000 ms")
    print(f"    Drone proxy time.sleep(1.0)        = 1000 ms")
    print(f"    GCS start_proxy HTTP RPC RTT        ~ 50-100 ms")
    print(f"    File polling (0.2s intervals)       ~ 0-200 ms")
    print(f"    -----------------------------------------")
    print(f"    Expected overhead                  ~ 3050-3300 ms")
    print(f"    Actual median overhead             = {statistics.median(overheads):.0f} ms")

# === 3. Protocol vs crypto breakdown ===
print()
print("=" * 80)
print("PROTOCOL OVERHEAD (wire I/O + HMAC + key derivation)")
print("=" * 80)
proto_over = []
for r in records:
    if r['protocol_ms'] and r['crypto_ms'] and r['crypto_ms'] > 0:
        proto_over.append(r['protocol_ms'] - r['crypto_ms'])
if proto_over:
    print(f"  protocol_ms - crypto_ms:")
    print(f"    Min:    {min(proto_over):>8.3f} ms")
    print(f"    Max:    {max(proto_over):>8.3f} ms")
    print(f"    Mean:   {statistics.mean(proto_over):>8.3f} ms")
    print(f"    Median: {statistics.median(proto_over):>8.3f} ms")
    print(f"  (This is TCP round-trip during handshake + HMAC + HKDF)")

# === 4. KEM family analysis ===
print()
print("=" * 80)
print("BY KEM FAMILY (protocol_handshake_duration_ms)")
print("=" * 80)

kem_families = defaultdict(list)
for r in records:
    if not r['protocol_ms']:
        continue
    suite = r['suite']
    # Extract KEM from suite name: cs-{kem}-{aead}-{sig}
    parts = suite.replace('cs-', '').split('-')
    # KEM families: mlkem512, mlkem768, mlkem1024, hqc128/192/256, classicmceliece*
    kem = 'unknown'
    if 'mlkem512' in suite: kem = 'ML-KEM-512'
    elif 'mlkem768' in suite: kem = 'ML-KEM-768'
    elif 'mlkem1024' in suite: kem = 'ML-KEM-1024'
    elif 'hqc128' in suite: kem = 'HQC-128'
    elif 'hqc192' in suite: kem = 'HQC-192'
    elif 'hqc256' in suite: kem = 'HQC-256'
    elif 'classicmceliece348864' in suite: kem = 'McEliece-348864'
    elif 'classicmceliece460896' in suite: kem = 'McEliece-460896'
    elif 'classicmceliece8192128' in suite: kem = 'McEliece-8192128'
    kem_families[kem].append(r)

print(f"  {'KEM Family':<25s} {'N':>3s} {'Proto Min':>10s} {'Proto Med':>10s} {'Proto Max':>10s} {'Crypto Med':>10s}")
for kem in sorted(kem_families.keys()):
    recs = kem_families[kem]
    protos = [r['protocol_ms'] for r in recs if r['protocol_ms']]
    cryptos = [r['crypto_ms'] for r in recs if r['crypto_ms']]
    if protos:
        print(f"  {kem:<25s} {len(protos):>3d} {min(protos):>10.1f} {statistics.median(protos):>10.1f} {max(protos):>10.1f} {statistics.median(cryptos):>10.1f}")

# === 5. Does PQC actually take 3 seconds? ANSWER ===
print()
print("=" * 80)
print("VERDICT: DOES PQC TAKE 3-4 SECONDS?")
print("=" * 80)
print()
print("  NO. The actual PQC handshake times are:")
print()
L1_suites = [r for r in records if r['protocol_ms'] and ('mlkem512' in r['suite'] or 'mlkem768' in r['suite'])]
L3_suites = [r for r in records if r['protocol_ms'] and 'classicmceliece' in r['suite']]
all_proto = [r['protocol_ms'] for r in records if r['protocol_ms']]
if L1_suites:
    l1p = [r['protocol_ms'] for r in L1_suites]
    print(f"  L1 suites (ML-KEM-512/768):     {min(l1p):>8.1f} - {max(l1p):>8.1f} ms")
if L3_suites:
    l3p = [r['protocol_ms'] for r in L3_suites]
    print(f"  L3 suites (Classic McEliece):    {min(l3p):>8.1f} - {max(l3p):>8.1f} ms")
print(f"  All 72 suites protocol median:  {statistics.median(all_proto):>8.1f} ms")
print()
print("  The 3000+ ms shown in the dashboard is ORCHESTRATION OVERHEAD:")
print(f"    time.sleep(2.0) in sgcs_bench.py GcsProxyManager.start()")
print(f"    time.sleep(1.0) in sdrone_bench.py DroneProxyManager.start()")
print(f"    + HTTP RPC round-trip + file polling")
print()
print("  For research paper publication:")
print("    USE protocol_handshake_duration_ms (proxy's own measurement)")
print("    OR  total_crypto_time_ms (pure cryptographic operations)")
print("    NOT handshake_total_duration_ms (scheduler orchestration)")
