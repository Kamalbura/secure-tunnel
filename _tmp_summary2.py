import csv, json, pathlib
p = pathlib.Path(r"c:\Users\burak\ptojects\secure-tunnel\logs\benchmarks\analysis_metrics")
rows = list(csv.DictReader((p/"consistency_matrix.csv").open("r", encoding="utf-8")))
counts = {}
for r in rows:
    counts[r["classification"]] = counts.get(r["classification"], 0) + 1
print("CLASS_COUNTS", counts)

sv = json.load((p/"schema_vs_observed.json").open("r", encoding="utf-8"))
print("EXTRA_KEYS", len(sv["extra_keys"]))
print("MISSING_KEYS", len(sv["missing_keys"]))
