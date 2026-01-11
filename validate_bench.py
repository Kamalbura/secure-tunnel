#!/usr/bin/env python3
"""Validate benchmark results and extract statistics."""
import json
from pathlib import Path
import statistics

def main():
    bench_dir = Path("bench_results")
    raw_dir = bench_dir / "raw"

    results = {
        "kem": {"files": 0, "total_iters": 0, "success": 0, "failed": 0, "timings": []},
        "sig": {"files": 0, "total_iters": 0, "success": 0, "failed": 0, "timings": []},
        "aead": {"files": 0, "total_iters": 0, "success": 0, "failed": 0, "timings": []},
        "suites": {"files": 0, "total_iters": 0, "success": 0, "failed": 0, "timings": []},
    }

    algo_details = {}

    for category in results.keys():
        cat_dir = raw_dir / category
        if not cat_dir.exists():
            continue
        for f in sorted(cat_dir.glob("*.json")):
            results[category]["files"] += 1
            with open(f) as fp:
                data = json.load(fp)
            
            algo_name = data.get("algorithm_name", "unknown")
            operation = data.get("operation", "unknown")
            key = f"{algo_name}_{operation}"
            
            iters = data.get("iterations", [])
            results[category]["total_iters"] += len(iters)
            
            wall_times = []
            perf_times = []
            
            for it in iters:
                if it.get("success"):
                    results[category]["success"] += 1
                    wall_times.append(it.get("wall_time_ns", 0))
                    perf_times.append(it.get("perf_time_ns", 0))
                else:
                    results[category]["failed"] += 1
            
            if wall_times:
                algo_details[key] = {
                    "category": category,
                    "algorithm": algo_name,
                    "operation": operation,
                    "iterations": len(wall_times),
                    "wall_time_mean_ns": statistics.mean(wall_times),
                    "wall_time_median_ns": statistics.median(wall_times),
                    "wall_time_min_ns": min(wall_times),
                    "wall_time_max_ns": max(wall_times),
                    "wall_time_stdev_ns": statistics.stdev(wall_times) if len(wall_times) > 1 else 0,
                    "perf_time_mean_ns": statistics.mean(perf_times),
                    "perf_time_median_ns": statistics.median(perf_times),
                    "public_key_bytes": data.get("public_key_bytes"),
                    "secret_key_bytes": data.get("secret_key_bytes"),
                    "ciphertext_bytes": data.get("ciphertext_bytes"),
                    "signature_bytes": data.get("signature_bytes"),
                    "shared_secret_bytes": data.get("shared_secret_bytes"),
                    "payload_size": data.get("payload_size"),
                }

    print("=" * 60)
    print("BENCHMARK VALIDATION RESULTS")
    print("=" * 60)
    
    total_files = 0
    total_iters = 0
    total_success = 0
    total_failed = 0
    
    for cat, stats in results.items():
        files = stats["files"]
        total = stats["total_iters"]
        succ = stats["success"]
        fail = stats["failed"]
        total_files += files
        total_iters += total
        total_success += succ
        total_failed += fail
        
        print(f"\n{cat.upper()}:")
        print(f"  Files: {files}")
        print(f"  Total iterations: {total}")
        print(f"  Successful: {succ}")
        print(f"  Failed: {fail}")
        if total > 0:
            rate = (succ / total) * 100
            print(f"  Success rate: {rate:.2f}%")

    print(f"\n{'=' * 60}")
    print(f"TOTALS:")
    print(f"  Total files: {total_files}")
    print(f"  Total iterations: {total_iters}")
    print(f"  Total successful: {total_success}")
    print(f"  Total failed: {total_failed}")
    if total_iters > 0:
        print(f"  Overall success rate: {(total_success/total_iters)*100:.2f}%")

    # Environment
    env_file = bench_dir / "environment.json"
    if env_file.exists():
        with open(env_file) as fp:
            env = json.load(fp)
        print(f"\n{'=' * 60}")
        print("ENVIRONMENT:")
        print("=" * 60)
        for k, v in env.items():
            print(f"  {k}: {v}")

    # Print detailed algorithm stats
    print(f"\n{'=' * 60}")
    print("ALGORITHM STATISTICS (sorted by category)")
    print("=" * 60)
    
    for cat in ["kem", "sig", "aead", "suites"]:
        cat_algos = {k: v for k, v in algo_details.items() if v["category"] == cat}
        if not cat_algos:
            continue
        print(f"\n--- {cat.upper()} ---")
        for key in sorted(cat_algos.keys()):
            d = cat_algos[key]
            mean_ms = d["wall_time_mean_ns"] / 1_000_000
            median_ms = d["wall_time_median_ns"] / 1_000_000
            min_ms = d["wall_time_min_ns"] / 1_000_000
            max_ms = d["wall_time_max_ns"] / 1_000_000
            print(f"\n  {d['algorithm']} - {d['operation']}:")
            print(f"    Iterations: {d['iterations']}")
            print(f"    Mean: {mean_ms:.4f} ms")
            print(f"    Median: {median_ms:.4f} ms")
            print(f"    Min: {min_ms:.4f} ms")
            print(f"    Max: {max_ms:.4f} ms")
            if d.get("public_key_bytes"):
                print(f"    Public key: {d['public_key_bytes']} bytes")
            if d.get("secret_key_bytes"):
                print(f"    Secret key: {d['secret_key_bytes']} bytes")
            if d.get("ciphertext_bytes"):
                print(f"    Ciphertext: {d['ciphertext_bytes']} bytes")
            if d.get("signature_bytes"):
                print(f"    Signature: {d['signature_bytes']} bytes")
            if d.get("payload_size"):
                print(f"    Payload: {d['payload_size']} bytes")

if __name__ == "__main__":
    main()
