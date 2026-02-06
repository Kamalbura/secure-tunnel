#!/usr/bin/env python3
"""Compare suites in benchmark_results.json vs comprehensive files."""
import json
from pathlib import Path

RUN_DIR = Path(__file__).parent
RESULTS_JSON = RUN_DIR / "benchmark_results_20260205_145749.json"
COMPREHENSIVE_DIR = RUN_DIR / "comprehensive"

# Load main results
with open(RESULTS_JSON) as f:
    results = json.load(f)

benchmark_suites = set(s['suite_id'] for s in results['suites'])

# Load comprehensive suites
comp_suites = set()
for f in COMPREHENSIVE_DIR.glob("*.json"):
    try:
        with open(f) as fp:
            d = json.load(fp)
            suite_id = d.get('run_context', {}).get('suite_id', '')
            if suite_id:
                comp_suites.add(suite_id)
    except:
        pass

print(f"Suites in benchmark_results.json: {len(benchmark_suites)}")
print(f"Suites in comprehensive files:    {len(comp_suites)}")

missing = benchmark_suites - comp_suites
extra = comp_suites - benchmark_suites

if missing:
    print(f"\nMISSING from comprehensive ({len(missing)}):")
    for s in sorted(missing):
        print(f"  - {s}")

if extra:
    print(f"\nEXTRA in comprehensive ({len(extra)}):")
    for s in sorted(extra):
        print(f"  - {s}")
