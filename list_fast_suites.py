#!/usr/bin/env python3
"""List only fast suites (ML-KEM based) for testing."""
from core.suites import list_suites

suites = list_suites()
fast_suites = [s for s, c in suites.items() 
               if "mlkem" in s.lower() and "aesgcm" in c.get("aead", "")]
print(f"Found {len(fast_suites)} fast suites:")
for s in sorted(fast_suites):
    print(f"  {s}")
