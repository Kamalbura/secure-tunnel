"""
Forensic analysis of handshake timing inflation.

Theory: The handshake_total_duration_ms is NOT the actual PQC handshake time.
It's measured from record_handshake_start() to record_handshake_end(), which
includes orchestration overhead:

DRONE SIDE timeline:
  1. record_handshake_start()          -> monotonic T0
  2. send_gcs_command("start_proxy")   -> HTTP RPC to GCS (network RTT)
  3. GCS receives, starts proxy subprocess
  4. GCS proxy.start() -> spawns process + time.sleep(2.0) [!!!]  
  5. GCS returns {"status": "ok"} after the 2s sleep
  6. Drone receives response
  7. self.proxy.start(suite_name)      -> spawns drone proxy + time.sleep(1.0) [!!!]
  8. Drone proxy connects to GCS proxy 
  9. Actual PQC handshake happens       (~5-50ms for most suites)
  10. Proxy writes drone_status.json {"status": "handshake_ok"}
  11. read_handshake_status() polls file (0.2s intervals)
  12. record_handshake_end()           -> monotonic T1
  
  Total measured = T1 - T0 = (RPC RTT) + 2.0s + 1.0s + (handshake) + (polling delay)
                  ~= 3.0s + actual_handshake + jitter

GCS SIDE timeline:
  1. Receives "start_proxy" command
  2. record_handshake_start()          -> monotonic T0
  3. proxy.start(suite) -> spawns process + time.sleep(2.0) [!!!]
  4. Returns response to drone
  5. _await_handshake thread polls gcs_status.json (0.2s intervals)
  6. record_handshake_end()            -> monotonic T1

  Total measured = T1 - T0 = 2.0s + (handshake) + (polling delay)
                  ~= 2.0s + actual_handshake + jitter

The REAL handshake time is in crypto_primitives.total_crypto_time_ms
and the proxy's own handshake_metrics.rekey_ms field.
"""
import json, os, statistics

src = 'logs/benchmarks/runs/no-ddos'

records = []
for f in sorted(os.listdir(src)):
    if '20260207' not in f or not f.endswith('_drone.json'):
        continue
    fp = os.path.join(src, f)
    try:
        d = json.load(open(fp))
    except:
        continue
    
    hs = d.get('handshake', {})
    cp = d.get('crypto_primitives', {})
    suite = d.get('run_context', {}).get('suite_id', '?')
    
    total_ms = hs.get('handshake_total_duration_ms')        # What dashboard shows
    protocol_ms = hs.get('protocol_handshake_duration_ms')   # Protocol-level
    crypto_ms = cp.get('total_crypto_time_ms')               # Pure crypto ops
    kem_ms = cp.get('kem_keygen_time_ms', 0) or 0
    
    if total_ms is not None:
        records.append({
            'suite': suite,
            'total_ms': total_ms,
            'protocol_ms': protocol_ms,
            'crypto_ms': crypto_ms,
            'kem_ms': kem_ms,
        })

# === Analysis ===
print(f"Analyzed {len(records)} suites from run 20260207_144051\n")

# 1. The inflated metric (what dashboard shows)
totals = [r['total_ms'] for r in records]
print("=" * 70)
print("METRIC: handshake_total_duration_ms (WHAT DASHBOARD SHOWS)")
print("=" * 70)
print(f"  Min:    {min(totals):>10.1f} ms")
print(f"  Max:    {max(totals):>10.1f} ms")
print(f"  Mean:   {statistics.mean(totals):>10.1f} ms")
print(f"  Median: {statistics.median(totals):>10.1f} ms")

# 2. Protocol handshake (from proxy's own measurement)
protos = [r['protocol_ms'] for r in records if r['protocol_ms'] is not None]
print(f"\n{'=' * 70}")
print("METRIC: protocol_handshake_duration_ms (PROXY'S OWN MEASUREMENT)")
print("=" * 70)
if protos:
    print(f"  Min:    {min(protos):>10.3f} ms")
    print(f"  Max:    {max(protos):>10.3f} ms")
    print(f"  Mean:   {statistics.mean(protos):>10.3f} ms")
    print(f"  Median: {statistics.median(protos):>10.3f} ms")
else:
    print("  No data!")

# 3. Pure crypto time
cryptos = [r['crypto_ms'] for r in records if r['crypto_ms'] is not None]
print(f"\n{'=' * 70}")
print("METRIC: total_crypto_time_ms (PURE CRYPTO OPERATIONS)")
print("=" * 70)
if cryptos:
    print(f"  Min:    {min(cryptos):>10.3f} ms")
    print(f"  Max:    {max(cryptos):>10.3f} ms")
    print(f"  Mean:   {statistics.mean(cryptos):>10.3f} ms")
    print(f"  Median: {statistics.median(cryptos):>10.3f} ms")

# 4. Inflation factor
print(f"\n{'=' * 70}")
print("INFLATION ANALYSIS")
print("=" * 70)
for r in records:
    if r['protocol_ms'] and r['protocol_ms'] > 0:
        r['inflation'] = r['total_ms'] / r['protocol_ms']
    else:
        r['inflation'] = None

with_inflation = [r for r in records if r['inflation'] is not None]
inflations = [r['inflation'] for r in with_inflation]
if inflations:
    print(f"  Inflation factor (total/protocol):")
    print(f"    Min:    {min(inflations):>8.1f}x")
    print(f"    Max:    {max(inflations):>8.1f}x")
    print(f"    Mean:   {statistics.mean(inflations):>8.1f}x")

# 5. Overhead breakdown
overheads = [r['total_ms'] - (r['protocol_ms'] or 0) for r in records if r['protocol_ms']]
if overheads:
    print(f"\n  Fixed overhead (total - protocol):")
    print(f"    Min:    {min(overheads):>8.1f} ms")
    print(f"    Max:    {max(overheads):>8.1f} ms")
    print(f"    Mean:   {statistics.mean(overheads):>8.1f} ms")
    print(f"    Median: {statistics.median(overheads):>8.1f} ms")

# 6. Compare for a few key suites
print(f"\n{'=' * 70}")
print("SUITE-BY-SUITE COMPARISON (sample)")
print("=" * 70)
print(f"  {'Suite':<45s} {'Dashboard':>10s} {'Protocol':>10s} {'Crypto':>10s} {'Overhead':>10s}")
print(f"  {'':−<45s} {'':−>10s} {'':−>10s} {'':−>10s} {'':−>10s}")

# Sort by total_ms 
for r in sorted(records, key=lambda x: x['total_ms'])[:5]:
    short = r['suite'].replace('cs-', '')[:42]
    proto = f"{r['protocol_ms']:.1f}" if r['protocol_ms'] else "N/A"
    crypto = f"{r['crypto_ms']:.1f}" if r['crypto_ms'] else "N/A"
    overhead = f"{r['total_ms'] - (r['protocol_ms'] or 0):.0f}" if r['protocol_ms'] else "?"
    print(f"  {short:<45s} {r['total_ms']:>10.1f} {proto:>10s} {crypto:>10s} {overhead:>10s}")

print()
for r in sorted(records, key=lambda x: x['total_ms'])[-5:]:
    short = r['suite'].replace('cs-', '')[:42]
    proto = f"{r['protocol_ms']:.1f}" if r['protocol_ms'] else "N/A"
    crypto = f"{r['crypto_ms']:.1f}" if r['crypto_ms'] else "N/A"
    overhead = f"{r['total_ms'] - (r['protocol_ms'] or 0):.0f}" if r['protocol_ms'] else "?"
    print(f"  {short:<45s} {r['total_ms']:>10.1f} {proto:>10s} {crypto:>10s} {overhead:>10s}")

# 7. Root cause
print(f"\n{'=' * 70}")
print("ROOT CAUSE")
print("=" * 70)
print("""
  The handshake_total_duration_ms displayed in the dashboard is NOT
  the actual PQC handshake time. It measures the ENTIRE orchestration:

  DRONE (3+ seconds):
    record_handshake_start()
      → HTTP RPC to GCS "start_proxy"
      → GCS spawns proxy + time.sleep(2.0)     ← 2000ms fixed sleep
      → GCS responds
      → Drone spawns proxy + time.sleep(1.0)    ← 1000ms fixed sleep
      → TCP connect + actual PQC handshake       ← 5-50ms typically
      → File polling (0.2s intervals)             ← 0-200ms jitter
    record_handshake_end()

  GCS (2+ seconds):
    record_handshake_start()
      → proxy.start() → time.sleep(2.0)        ← 2000ms fixed sleep
      → File polling for handshake_ok             ← variable
    record_handshake_end()

  The REAL handshake time is:
    • protocol_handshake_duration_ms  (what the proxy measures internally)
    • total_crypto_time_ms            (pure cryptographic operations)
""")
