import json

d = json.load(open("bench_ddos_results/20260210_024632/comparison.json"))
mlkem = [s for s in d["per_suite"] if "mlkem" in s["suite_id"]]
print(f"Total ML-KEM suites: {len(mlkem)}\n")

for i, s in enumerate(mlkem, 1):
    cpu_ok = s["baseline_cpu_avg"] <= s["xgb_cpu_avg"] <= s["tst_cpu_avg"]
    pwr_ok = s["baseline_power_mw"] <= s["xgb_power_mw"] <= s["tst_power_mw"]
    print(f"[{i:2d}] {s['suite_id']}")
    print(f"     Latency(ms)  base={s['baseline_mean_ms']:.2f}  xgb={s['xgb_mean_ms']:.2f}  tst={s['tst_mean_ms']:.2f}")
    print(f"     Overhead     xgb={s['xgb_overhead_pct']:.2f}%  tst={s['tst_overhead_pct']:.2f}%")
    print(f"     CPU          base={s['baseline_cpu_avg']:.2f}  xgb={s['xgb_cpu_avg']:.2f}  tst={s['tst_cpu_avg']:.2f}  OK={cpu_ok}")
    print(f"     Power(mW)    base={s['baseline_power_mw']:.1f}  xgb={s['xgb_power_mw']:.1f}  tst={s['tst_power_mw']:.1f}  OK={pwr_ok}")
    print()

cpu_ok_count = sum(1 for s in mlkem if s["baseline_cpu_avg"] <= s["xgb_cpu_avg"] <= s["tst_cpu_avg"])
pwr_ok_count = sum(1 for s in mlkem if s["baseline_power_mw"] <= s["xgb_power_mw"] <= s["tst_power_mw"])
print("=" * 60)
print(f"ML-KEM suites total:  {len(mlkem)}")
print(f"CPU ordering correct: {cpu_ok_count}/{len(mlkem)}  ({100*cpu_ok_count/len(mlkem):.1f}%)")
print(f"Power ordering correct: {pwr_ok_count}/{len(mlkem)}  ({100*pwr_ok_count/len(mlkem):.1f}%)")
