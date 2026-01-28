
import sys

modules = [
    "core.metrics_aggregator",
    "core.mavlink_collector",
    "core.async_proxy",
    "core.handshake",
    "core.metrics_collectors",
    "core.clock_sync"
]

failed = []
print("Checking imports...")
for mod in modules:
    try:
        __import__(mod)
        print(f"[OK] {mod}")
    except ImportError as e:
        print(f"[FAIL] {mod}: {e}")
        failed.append(mod)
    except Exception as e:
        print(f"[ERROR] {mod}: {e}")
        failed.append(mod)

if failed:
    sys.exit(1)
sys.exit(0)
