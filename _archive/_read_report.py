import json
r = json.load(open("data/processed/ml_step03_report.json", "r", encoding="utf-8"))
b = r["baseline_naive"]
l = r["lightgbm"]
res = r["residual_analysis"]

print("=" * 50)
print("BASELINE (Naive) vs LightGBM")
print("=" * 50)
print(f"{'Metrik':<10} {'Naive':>12} {'LightGBM':>12}")
print("-" * 40)
print(f"RMSE      {b['rmse']:>12.2f} {l['test_rmse']:>12.2f}")
print(f"MAE       {b['mae']:>12.2f} {l['test_mae']:>12.2f}")
print(f"MAPE%     {b['mape']:>12.2f} {l['test_mape']:>12.2f}")
print(f"R2        {b['r2']:>12.6f} {l['test_r2']:>12.6f}")
print()
print(f"CV RMSE: {l['cv_rmse_mean']} +- {l['cv_rmse_std']}")
print(f"CV R2:   {l['cv_r2_mean']}")
print()
print(f"Reziduel <100km: {res['pct_within_100km']}%")
print(f"Reziduel <500km: {res['pct_within_500km']}%")
print()
print("Feature Importance (Top 5):")
fi = r["feature_importance"]
for i, (k, v) in enumerate(sorted(fi.items(), key=lambda x: -x[1])):
    if i >= 5:
        break
    print(f"  {k}: {v}")
