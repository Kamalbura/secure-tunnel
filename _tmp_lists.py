import json, pathlib
p = pathlib.Path(r"c:\Users\burak\ptojects\secure-tunnel\logs\benchmarks\analysis_metrics\schema_vs_observed.json")
sv = json.load(p.open("r", encoding="utf-8"))
print("EXTRA_KEYS")
for k in sv["extra_keys"]:
    print(k)
print("MISSING_KEYS")
for k in sv["missing_keys"]:
    print(k)
