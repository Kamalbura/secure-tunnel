import sys
import platform
import subprocess

print(f"Python: {sys.version}")
print("-" * 20)
print("Dependencies:")
try:
    subprocess.check_call([sys.executable, "-m", "pip", "list"])
except Exception as e:
    print(f"Pip check failed: {e}")

print("-" * 20)
imports = ["liboqs", "oqs", "pymavlink"]
for m in imports:
    try:
        __import__(m)
        print(f"{m}: OK")
    except ImportError as e:
        print(f"{m}: FAIL {e}")
    except Exception as e:
        print(f"{m}: ERROR {e}")
