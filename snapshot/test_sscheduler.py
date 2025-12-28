#!/usr/bin/env python3
"""
Test script for sscheduler (drone-controlled scheduler)

Runs sgcs (follower) first, then sdrone (controller) to test
the reversed control flow where drone commands GCS.
"""

import os
import sys
import time
import subprocess
import signal

def main():
    print("=" * 70)
    print("sScheduler Test - Drone Controller + GCS Follower on localhost")
    print("=" * 70)
    print()
    
    # Set environment
    env = os.environ.copy()
    env["DRONE_HOST"] = "127.0.0.1"
    env["GCS_HOST"] = "127.0.0.1"
    env["GCS_CONTROL_HOST"] = "127.0.0.1"
    env["ENABLE_PACKET_TYPE"] = "0"
    
    # Start GCS scheduler (follower) first - it needs to be listening
    print("[Test] Starting GCS scheduler (follower)...")
    gcs_proc = subprocess.Popen(
        [sys.executable, "-m", "sscheduler.sgcs"],
        env=env,
        cwd=os.path.dirname(os.path.abspath(__file__)),
    )
    time.sleep(3)
    
    if gcs_proc.poll() is not None:
        print(f"[Test] ERROR: GCS scheduler exited with code {gcs_proc.returncode}")
        return 1
    
    print("[Test] GCS scheduler running")
    print()
    
    # Start drone scheduler (controller)
    # Use fast ML-KEM suites (ClassicMcEliece are too slow)
    print("[Test] Starting drone scheduler (controller)...")
    drone_proc = subprocess.Popen(
        [sys.executable, "-m", "sscheduler.sdrone", "--max-suites", "2", "--nist-level", "L3"],
        env=env,
        cwd=os.path.dirname(os.path.abspath(__file__)),
    )
    
    # Wait for drone to complete (it's the controller)
    try:
        drone_exit = drone_proc.wait(timeout=300)
        print()
        print(f"[Test] Drone scheduler completed with code: {drone_exit}")
    except subprocess.TimeoutExpired:
        print("[Test] Drone scheduler timed out")
        drone_proc.terminate()
        drone_exit = 1
    
    print()
    print("[Test] Cleaning up...")
    
    # Stop GCS
    if gcs_proc.poll() is None:
        gcs_proc.terminate()
        try:
            gcs_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            gcs_proc.kill()
    
    print("[Test] Done")
    return drone_exit

if __name__ == "__main__":
    sys.exit(main())
