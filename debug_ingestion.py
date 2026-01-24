import os
import glob
import requests
import json

def cleanup_old_files():
    files = glob.glob('dashboard/data/benchmark_runs/manual_sync/**/*.jsonl', recursive=True)
    print(f"Found {len(files)} old files to delete.")
    for f in files:
        try:
            os.remove(f)
            print(f"Deleted: {f}")
        except Exception as e:
            print(f"Failed to delete {f}: {e}")

def check_errors():
    try:
        resp = requests.get('http://localhost:8000/api/metrics/load-errors')
        data = resp.json()
        errors = data.get('errors', [])
        print(f"Total errors: {len(errors)}")
        
        found = False
        seen_files = set()
        for e in errors:
            seen_files.add(e['file'])
            if 'repaired_metrics.jsonl' in e['file']:
                print(f"ERROR in Repaired File: {json.dumps(e, indent=2)}")
                found = True
        
        print("Files with errors:")
        for f in seen_files:
            print(f" - {f}")
        
        if not found:
            print("No errors found specifically for repaired_metrics.jsonl")
            if errors:
                print(f"Sample error from other file: {json.dumps(errors[0], indent=2)}")
                
    except Exception as e:
        print(f"Failed to check errors: {e}")

if __name__ == "__main__":
    cleanup_old_files()
    check_errors()
