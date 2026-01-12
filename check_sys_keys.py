#!/usr/bin/env python3
"""Check SystemCollector keys."""
from core.metrics_collectors import SystemCollector
s = SystemCollector()
m = s.collect()
print("SystemCollector keys:", list(m.keys()))
