import os
import json

def verify():
    # 1. Check if logs folder exists
    if not os.path.exists("logs"):
        print("FAIL: logs/ dir not found")
        return

    # 2. Find latest run folder
    runs = sorted([d for d in os.listdir("logs") if d.startswith("run_")])
    if not runs:
        print("FAIL: No run_ folders found")
        return
    
    latest_run = os.path.join("logs", runs[-1])
    print(f"Checking {latest_run}...")

    # 3. Check for JSONL files
    expected = ["drone_telemetry.jsonl", "gcs_telemetry.jsonl"]
    for f in expected:
        f_path = os.path.join(latest_run, f)
        if os.path.exists(f_path):
            print(f"  [OK] Found {f}")
            # Validate JSON content
            try:
                with open(f_path, 'r') as json_file:
                    first_line = json.loads(json_file.readline())
                    if "suite" in first_line and "metrics" in first_line:
                        print(f"       Content Valid. Suite: {first_line['suite']}")
                    else:
                        print(f"       FAIL: Invalid JSON structure")
            except Exception:
                print("       FAIL: Could not parse JSON")
        else:
            print(f"  [MISSING] Could not find {f}")

if __name__ == "__main__":
    verify()
