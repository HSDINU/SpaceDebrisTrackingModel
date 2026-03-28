"""
Adım 3 — LightGBM 24h Mesafe Tahmini (Regression)
====================================================
Girdi: data/processed/ml_features_24h.csv

Problem: Verilen yörünge elemanları + t0 mesafesinden,
         24 saat sonraki mesafeyi tahmin et (regression).

Label leakage YOK — target zamanda ayrılmış.
Sentetik veri kullanılmaz.

Metrikler: RMSE, MAE, MAPE, R², 5-fold CV
Baseline : Naive persistence (mesafe_t24 ≈ mesafe_t0)

Çıktı: lightgbm_risk_modeli.pkl + data/processed/ml_step03_report.json

Çalıştırma:
  python -m ml_pipeline.step03_train_baseline
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import KFold, cross_val_score, train_test_split

try:
    import lightgbm as lgb
except ImportError:
    raise SystemExit("lightgbm gerekli: pip install lightgbm")


# Model eğitiminde KULLANILMAYACAK sütunlar
EXCLUDE_COLS = {"mesafe_t24_km", "turk_uydu", "hiz_t24_km_s", "delta_mesafe_km",
                "cop_isim", "cop_kaynak"}
TARGET = "mesafe_t24_km"


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def main() -> int:
    root = project_root()
    feat_path = root / "data" / "processed" / "ml_features_24h.csv"
    report_path = root / "data" / "processed" / "ml_step03_report.json"

    print("=" * 60)
    print("Adım 3 — LightGBM 24h Regression (Gerçek Tahmin)")
    print("=" * 60)

    if not feat_path.exists():
        print(f"EKSİK: {feat_path}")
        return 1

    df = pd.read_csv(feat_path, encoding="utf-8-sig")
    if len(df) < 50:
        print(f"HATA: Yalnızca {len(df)} satır var.")
        return 1

    # Feature sütunları
    feature_cols = [c for c in df.columns if c not in EXCLUDE_COLS]
    print(f"Feature sayısı: {len(feature_cols)}")
    print(f"Feature'lar: {feature_cols}")

    X = df[feature_cols].astype(float)
    y = df[TARGET].astype(float)

    print(f"\nVeri: {len(df):,} satır")
    print(f"Target ({TARGET}):")
    print(f"  min={y.min():.1f}  max={y.max():.1f}  mean={y.mean():.1f}  std={y.std():.1f}")

    # --- Train/Test split ---
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )
    print(f"\nEğitim: {len(X_train):,} | Test: {len(X_test):,}")

    # ════════════════════════════════════════════
    # BASELINE: Naive Persistence (t0 → t24 tahmini)
    # ════════════════════════════════════════════
    print(f"\n{'─' * 60}")
    print("BASELINE: Naive Persistence (mesafe_t24 ≈ mesafe_t0)")
    print(f"{'─' * 60}")

    if "mesafe_t0_km" in X_test.columns:
        y_naive = X_test["mesafe_t0_km"].values
        rmse_naive = np.sqrt(mean_squared_error(y_test, y_naive))
        mae_naive = mean_absolute_error(y_test, y_naive)
        r2_naive = r2_score(y_test, y_naive)
        mape_naive = np.mean(np.abs((y_test.values - y_naive) / np.maximum(y_test.values, 1)) * 100)
        print(f"  RMSE: {rmse_naive:.2f} km")
        print(f"  MAE : {mae_naive:.2f} km")
        print(f"  MAPE: {mape_naive:.2f}%")
        print(f"  R²  : {r2_naive:.6f}")
    else:
        rmse_naive = mae_naive = r2_naive = mape_naive = float("nan")

    # ════════════════════════════════════════════
    # LightGBM Regression
    # ════════════════════════════════════════════
    print(f"\n{'─' * 60}")
    print("LightGBM Regression")
    print(f"{'─' * 60}")

    model = lgb.LGBMRegressor(
        n_estimators=500,
        learning_rate=0.05,
        num_leaves=63,
        max_depth=8,
        min_child_samples=20,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        verbose=-1,
    )

    # 5-fold CV
    cv = KFold(n_splits=5, shuffle=True, random_state=42)

    cv_rmse = -cross_val_score(model, X, y, cv=cv, scoring="neg_root_mean_squared_error")
    cv_mae = -cross_val_score(model, X, y, cv=cv, scoring="neg_mean_absolute_error")
    cv_r2 = cross_val_score(model, X, y, cv=cv, scoring="r2")

    print(f"  CV RMSE : {cv_rmse.mean():.2f} ± {cv_rmse.std():.2f}")
    print(f"  CV MAE  : {cv_mae.mean():.2f} ± {cv_mae.std():.2f}")
    print(f"  CV R²   : {cv_r2.mean():.6f} ± {cv_r2.std():.6f}")

    # Final model
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)

    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    mae = mean_absolute_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)
    mape = np.mean(np.abs((y_test.values - y_pred) / np.maximum(y_test.values, 1)) * 100)

    print(f"\n  Test RMSE: {rmse:.2f} km")
    print(f"  Test MAE : {mae:.2f} km")
    print(f"  Test MAPE: {mape:.2f}%")
    print(f"  Test R²  : {r2:.6f}")

    # ════════════════════════════════════════════
    # KARŞILAŞTIRMA
    # ════════════════════════════════════════════
    print(f"\n{'═' * 60}")
    print("BASELINE vs LightGBM")
    print(f"{'═' * 60}")
    print(f"{'Metrik':<10} {'Naive':>12} {'LightGBM':>12} {'İyileşme':>12}")
    print(f"{'─' * 50}")

    for metric, nv, lv in [
        ("RMSE", rmse_naive, rmse),
        ("MAE", mae_naive, mae),
        ("MAPE%", mape_naive, mape),
        ("R²", r2_naive, r2),
    ]:
        if metric == "R²":
            imp = f"{(lv - nv):.6f}"
        else:
            imp = f"{((nv - lv) / nv * 100):.1f}%" if nv > 0 else "N/A"
        print(f"  {metric:<10} {nv:>12.2f} {lv:>12.2f} {imp:>12}")

    # ════════════════════════════════════════════
    # Feature Importance
    # ════════════════════════════════════════════
    print(f"\n{'─' * 60}")
    print("Feature Importance (gain)")
    print(f"{'─' * 60}")
    importances = model.feature_importances_
    imp_df = pd.DataFrame({
        "feature": feature_cols,
        "importance": importances
    }).sort_values("importance", ascending=False)

    for _, row in imp_df.iterrows():
        bar = "█" * int(row["importance"] / imp_df["importance"].max() * 30)
        print(f"  {row['feature']:<30s} {row['importance']:>8.0f}  {bar}")

    # ════════════════════════════════════════════
    # Rezidüel Analiz
    # ════════════════════════════════════════════
    print(f"\n{'─' * 60}")
    print("Rezidüel Analiz")
    print(f"{'─' * 60}")
    residuals = y_test.values - y_pred
    print(f"  Rezidüel mean: {residuals.mean():.2f} km")
    print(f"  Rezidüel std : {residuals.std():.2f} km")
    print(f"  Rezidüel min : {residuals.min():.2f} km")
    print(f"  Rezidüel max : {residuals.max():.2f} km")
    print(f"  |Rezidüel| < 100 km: {(np.abs(residuals) < 100).sum():,} "
          f"({100 * (np.abs(residuals) < 100).sum() / len(residuals):.1f}%)")
    print(f"  |Rezidüel| < 500 km: {(np.abs(residuals) < 500).sum():,} "
          f"({100 * (np.abs(residuals) < 500).sum() / len(residuals):.1f}%)")

    # ════════════════════════════════════════════
    # KAYDET
    # ════════════════════════════════════════════
    out_model = root / "lightgbm_risk_modeli.pkl"
    joblib.dump(model, out_model)
    print(f"\nModel: {out_model}")

    report = {
        "model_type": "LightGBM Regression (24h Distance Prediction)",
        "n_total": int(len(df)),
        "n_train": int(len(X_train)),
        "n_test": int(len(X_test)),
        "n_features": len(feature_cols),
        "feature_columns": feature_cols,
        "target": TARGET,
        "baseline_naive": {
            "rmse": round(float(rmse_naive), 2),
            "mae": round(float(mae_naive), 2),
            "mape": round(float(mape_naive), 2),
            "r2": round(float(r2_naive), 6),
        },
        "lightgbm": {
            "cv_rmse_mean": round(float(cv_rmse.mean()), 2),
            "cv_rmse_std": round(float(cv_rmse.std()), 2),
            "cv_mae_mean": round(float(cv_mae.mean()), 2),
            "cv_r2_mean": round(float(cv_r2.mean()), 6),
            "test_rmse": round(float(rmse), 2),
            "test_mae": round(float(mae), 2),
            "test_mape": round(float(mape), 2),
            "test_r2": round(float(r2), 6),
        },
        "feature_importance": {
            row["feature"]: int(row["importance"])
            for _, row in imp_df.iterrows()
        },
        "residual_analysis": {
            "mean": round(float(residuals.mean()), 2),
            "std": round(float(residuals.std()), 2),
            "pct_within_100km": round(float(100 * (np.abs(residuals) < 100).sum() / len(residuals)), 2),
            "pct_within_500km": round(float(100 * (np.abs(residuals) < 500).sum() / len(residuals)), 2),
        },
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"Rapor: {report_path}")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
