#!/usr/bin/env python3
"""Check drone environment."""
from core.suites import list_suites
import platform
import psutil

suites = list_suites()
print(f"Drone suites: {len(suites)}")
print(f"Python: {platform.python_version()}")
print(f"psutil: {psutil.__version__}")
print(f"Hostname: {platform.node()}")
