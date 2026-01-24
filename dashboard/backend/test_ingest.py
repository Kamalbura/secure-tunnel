from dashboard.backend.ingest import ingest_all_runs, get_run_details
import json

def test():
    print("--- Testing Ingestion ---")
    runs = ingest_all_runs()
    print(f"Found {len(runs)} runs.")
    
    for r in runs:
        print(f"Run: {r.run_id} | TS: {r.timestamp} | Success: {r.success_rate*100:.1f}%")
        
        details = get_run_details(r.run_id)
        print(f"  Loaded {len(details)} suites.")
        if details:
            s1 = details[0]
            print(f"  Suite 1 ID: {s1.suite_id}")
            print(f"  Handshake: {s1.handshake_total_duration_ms} ms")
            print(f"  KEM: {s1.kem_algorithm}")
            print(f"  Power Avg: {s1.power_avg_w} W") # Test comprehensive merge
            
if __name__ == "__main__":
    test()
