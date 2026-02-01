import json, re
from pathlib import Path

dir_path = Path("c:/Users/burak/ptojects/secure-tunnel/logs/benchmarks/comprehensive")
pattern = re.compile(r"20260122_174341")
files = [p for p in dir_path.glob("*_drone.json") if pattern.search(p.name)]
print("FILES", len(files))

def flatten(d, prefix=""):
    out = {}
    if isinstance(d, dict):
        for k, v in d.items():
            key = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                out.update(flatten(v, key))
            else:
                out[key] = v
    else:
        out[prefix] = d
    return out

all_keys = set()
file_flat = {}
for f in files:
    data = json.loads(f.read_text(encoding="utf-8"))
    flat = flatten(data)
    file_flat[f.name] = flat
    all_keys.update(flat.keys())

summary = []
for key in sorted(all_keys):
    types = {}
    null_count = 0
    zero_count = 0
    nonzero_count = 0
    missing_count = 0
    for fname, flat in file_flat.items():
        if key not in flat:
            missing_count += 1
            continue
        v = flat[key]
        if v is None:
            null_count += 1
        else:
            t = type(v).__name__
            types[t] = types.get(t, 0) + 1
            if isinstance(v, (int, float)):
                if v == 0:
                    zero_count += 1
                else:
                    nonzero_count += 1
    summary.append({
        "key": key,
        "missing": missing_count,
        "null": null_count,
        "zero": zero_count,
        "nonzero": nonzero_count,
        "types": ",".join(sorted(types.keys())),
    })

print("SUMMARY_START")
for row in summary:
    print(json.dumps(row, ensure_ascii=False))
print("SUMMARY_END")
