#!/usr/bin/env python3
"""Test scheduler pair on localhost - runs both sdrone and sgcs."""

import os
import sys
import subprocess
import time
import signal

# Set environment for localhost
os.environ["DRONE_HOST"] = "127.0.0.1"
os.environ["GCS_HOST"] = "127.0.0.1"
os.environ["DRONE_CONTROL_HOST"] = "127.0.0.1"
os.environ["ENABLE_PACKET_TYPE"] = "0"

ROOT = os.path.dirname(os.path.abspath(__file__))
PYTHON = sys.executable


def main():
    print("=" * 70)
    print("Scheduler Test - Running sdrone + sgcs on localhost")
    print("=" * 70)
    
    drone_proc = None
    gcs_proc = None
    
    try:
        # Start drone scheduler first (it waits for GCS)
        print("\n[Test] Starting drone scheduler...")
        drone_proc = subprocess.Popen(
            [PYTHON, "scheduler/sdrone.py"],
            env=os.environ.copy(),
            cwd=ROOT,
        )
        
        # Wait for drone control server to be ready
        time.sleep(3)
        
        if drone_proc.poll() is not None:
            print("[Test] ERROR: Drone scheduler exited early!")
            return 1
        
        print("[Test] Drone scheduler running")
        
        # Run GCS scheduler (blocking)
        print("\n[Test] Starting GCS scheduler...")
        gcs_proc = subprocess.Popen(
            [
                PYTHON, "scheduler/sgcs.py",
                "--suites", "cs-mlkem768-aesgcm-mldsa65,cs-mlkem512-aesgcm-mldsa44",
                "--duration", "10",
                "--bandwidth", "110",
            ],
            env=os.environ.copy(),
            cwd=ROOT,
        )
        
        # Wait for GCS to complete
        gcs_proc.wait()
        
        print("\n[Test] GCS scheduler completed with code:", gcs_proc.returncode)
        
        return gcs_proc.returncode
        
    except KeyboardInterrupt:
        print("\n[Test] Interrupted")
        return 1
    finally:
        # Cleanup
        print("\n[Test] Cleaning up...")
        
        if gcs_proc and gcs_proc.poll() is None:
            gcs_proc.terminate()
            try:
                gcs_proc.wait(timeout=5)
            except:
                gcs_proc.kill()
        
        if drone_proc and drone_proc.poll() is None:
            drone_proc.terminate()
            try:
                drone_proc.wait(timeout=5)
            except:
                drone_proc.kill()
        
        print("[Test] Done")


if __name__ == "__main__":
    sys.exit(main())
