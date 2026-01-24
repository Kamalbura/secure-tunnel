import sys
import os
from pathlib import Path

# Add dashboard to path
sys.path.append(os.getcwd())
sys.path.append(os.path.join(os.getcwd(), 'dashboard', 'backend'))

from dashboard.backend.ingest import load_jsonl_file, MetricsStore

def test_load():
    store = MetricsStore()
    f = Path("dashboard/data/repaired_metrics.jsonl")
    if not f.exists():
        print(f"File not found: {f}")
        return

    print(f"Testing load of {f}")
    try:
        count = load_jsonl_file(f, store)
        print(f"Loaded {count} suites")
        print(f"Store errors: {len(store.load_errors)}")
        for e in store.load_errors:
             print(e)
        
        print(f"Total Suites in Store: {store.suite_count}")
        if store.suite_count > 0:
             print("Sample Suite:")
             # keys are run_id:suite_id
             k = list(store._suites.keys())[0]
             print(store._suites[k].json(indent=2))

    except Exception as e:
        print(f"EXCEPTION: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_load()
