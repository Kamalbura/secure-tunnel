import sys
import traceback

try:
    print("Attempting import of dashboard.backend.main...")
    import dashboard.backend.main
    print("Import SUCCESS")
except Exception:
    with open("backend_error.log", "w") as f:
        traceback.print_exc(file=f)
    print("Import FAILED - details in backend_error.log")
