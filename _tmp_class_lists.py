import csv, pathlib
p = pathlib.Path(r"c:\Users\burak\ptojects\secure-tunnel\logs\benchmarks\analysis_metrics\consistency_matrix.csv")
rows = list(csv.DictReader(p.open("r", encoding="utf-8")))

by_class = {}
for r in rows:
    by_class.setdefault(r["classification"], []).append(r["metric_key"])

for k in sorted(by_class.keys()):
    print(k)
    for m in by_class[k]:
        print(m)
