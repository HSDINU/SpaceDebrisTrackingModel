"""
Adım 3 — LightGBM 24h Mesafe Tahmini (Regression)
====================================================
Girdi: data/processed/ml_features_24h.csv

Problem: Verilen yörünge elemanları + t0 mesafesinden,
         24 saat sonraki mesafeyi tahmin et (regression).

Label leakage YOK — target zamanda ayrılmış.
Sentetik veri kullanılmaz.

Metrikler: RMSE, MAE, MAPE, R²; CV: GroupKFold (cop_isim) veya KFold — yalnızca eğitim kümesi
Baseline : Naive persistence (mesafe_t24 ≈ mesafe_t0)

Ön-adım: replicate_training_split sonrası train-only EDA + KS raporu
  → data/processed/ml_pretrain_eda_report.json

Çıktı: lightgbm_risk_modeli.pkl + data/processed/ml_step03_report.json

Çalıştırma:
  python -m ml_pipeline.training.step03_train_baseline
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold, KFold, cross_val_score, train_test_split

from ml_pipeline.model_artifact import save_training_artifact
from ml_pipeline.profiles.feature_profiles import (
    CORE_ONLY,
    get_profile_spec,
    normalize_profile,
)
from ml_pipeline.analysis.pretrain_eda import run_eda_after_split
from ml_pipeline.training.training_split import replicate_training_split

try:
    import lightgbm as lgb
except ImportError:
    lgb = None  # type: ignore

# Model eğitiminde KULLANILMAYACAK sütunlar (kimlik, hedef, t+24h sızıntısı)
EXCLUDE_COLS = {
    "mesafe_t24_km",
    "turk_uydu",
    "hiz_t24_km_s",
    "delta_mesafe_km",
    "cop_isim",
    "cop_kaynak",
    "cop_norad_id",
}
TARGET = "mesafe_t24_km"


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def main() -> int:
    ap = argparse.ArgumentParser(description="LightGBM trainer (profile-aware)")
    ap.add_argument(
        "--profile",
        default=CORE_ONLY,
        help="Feature profile: core_only | core_plus_discos | core_plus_discos_physical",
    )
    args = ap.parse_args()
    profile = normalize_profile(args.profile)
    _ = get_profile_spec(profile)

    if lgb is None:
        raise SystemExit("lightgbm gerekli: pip install lightgbm")

    root = project_root()
    feat_path = root / "data" / "processed" / "ml_features_24h.csv"
    report_path = root / "data" / "processed" / f"ml_step03_report__{profile}.json"

    print("=" * 60)
    print("Adım 3 — LightGBM 24h Regression (Gerçek Tahmin)")
    print("=" * 60)
    print(f"Profile: {profile}")

    if not feat_path.exists():
        print(f"EKSİK: {feat_path}")
        return 1

    df = pd.read_csv(feat_path, encoding="utf-8-sig")
    if len(df) < 50:
        print(f"HATA: Yalnızca {len(df)} satır var.")
        return 1

    # Yalnızca sayısal sütunlar (DISCOS + çekirdek); kimlik/hedef EXCLUDE_COLS içinde
    feature_cols = [
        c
        for c in df.columns
        if c not in EXCLUDE_COLS
        and c != TARGET
        and pd.api.types.is_numeric_dtype(df[c])
    ]
    print(f"Feature sayısı: {len(feature_cols)}")
    print(f"Feature'lar: {feature_cols}")

    X = df[feature_cols].astype(float)
    y = df[TARGET].astype(float)

    print(f"\nVeri: {len(df):,} satır")
    print(f"Target ({TARGET}):")
    print(f"  min={y.min():.1f}  max={y.max():.1f}  mean={y.mean():.1f}  std={y.std():.1f}")

    # --- Train/Test split (önce ayrım — CV ve EDA test etiketini görmez) ---
    X_train, X_test, y_train, y_test, split_meta = replicate_training_split(df, X, y)
    split_method = split_meta["split_method"]
    group_col = split_meta["group_column"]
    if split_method.startswith("group_shuffle"):
        print(f"\nTrain/Test: grup ayrımı ({group_col}) — aynı çöp/uydu tek tarafta")
    else:
        print("\nTrain/Test: rastgele (grup sütunu yetersiz — cop_isim/turk_uydu kontrol edin)")
    print(f"Eğitim: {len(X_train):,} | Test: {len(X_test):,}")

    eda_path = root / "data" / "processed" / "ml_pretrain_eda_report.json"
    run_eda_after_split(X_train, X_test, y_train, feature_cols, split_meta, eda_path)

    groups: pd.Series | None = None
    if group_col == "cop_isim":
        groups = df["cop_isim"].fillna("__bos__").astype(str)
    elif group_col == "turk_uydu":
        groups = df["turk_uydu"].astype(str)

    groups_train: pd.Series | None = None
    if groups is not None:
        groups_train = groups.loc[X_train.index]

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

    lgb_params = dict(
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
    model = lgb.LGBMRegressor(**lgb_params)

    # CV: gruplar varsa GroupKFold (daha gerçekçi genelleme); yoksa KFold
    print(f"\n{'─' * 60}")
    print("Çapraz doğrulama")
    print(f"{'─' * 60}")
    if groups_train is not None and groups_train.nunique() >= 5:
        n_splits = min(5, int(groups_train.nunique()))
        gkf = GroupKFold(n_splits=n_splits)
        cv_rmse_list: list[float] = []
        cv_mae_list: list[float] = []
        cv_r2_list: list[float] = []
        for tr, va in gkf.split(X_train, y_train, groups_train):
            m = lgb.LGBMRegressor(**lgb_params)
            m.fit(X_train.iloc[tr], y_train.iloc[tr])
            pred = m.predict(X_train.iloc[va])
            cv_rmse_list.append(float(np.sqrt(mean_squared_error(y_train.iloc[va], pred))))
            cv_mae_list.append(float(mean_absolute_error(y_train.iloc[va], pred)))
            cv_r2_list.append(float(r2_score(y_train.iloc[va], pred)))
        cv_rmse = np.array(cv_rmse_list)
        cv_mae = np.array(cv_mae_list)
        cv_r2 = np.array(cv_r2_list)
        print(f"  (GroupKFold yalnızca eğitim, n_splits={n_splits}, grup={group_col})")
    else:
        cv = KFold(n_splits=5, shuffle=True, random_state=42)
        cv_rmse = -cross_val_score(
            lgb.LGBMRegressor(**lgb_params), X_train, y_train, cv=cv, scoring="neg_root_mean_squared_error"
        )
        cv_mae = -cross_val_score(
            lgb.LGBMRegressor(**lgb_params), X_train, y_train, cv=cv, scoring="neg_mean_absolute_error"
        )
        cv_r2 = cross_val_score(
            lgb.LGBMRegressor(**lgb_params), X_train, y_train, cv=cv, scoring="r2"
        )
        print("  (KFold yalnızca eğitim — grup yok)")

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
    # KAYDET (model + tahminde kullanılacak sütun sırası)
    # ════════════════════════════════════════════
    out_model = root / f"lightgbm_risk_modeli__{profile}.pkl"
    save_training_artifact(out_model, model, feature_cols, TARGET)
    print(f"\nModel (artifact): {out_model}")
    if profile == CORE_ONLY:
        legacy_model = root / "lightgbm_risk_modeli.pkl"
        save_training_artifact(legacy_model, model, feature_cols, TARGET)
        print(f"Legacy model de güncellendi: {legacy_model}")

    report = {
        "model_type": "LightGBM Regression (24h Distance Prediction)",
        "feature_profile": profile,
        "artifact_schema_version": 1,
        "n_total": int(len(df)),
        "n_train": int(len(X_train)),
        "n_test": int(len(X_test)),
        "n_features": len(feature_cols),
        "feature_columns": feature_cols,
        "target": TARGET,
        "train_test_split": split_method,
        "group_column": group_col,
        "pretrain_eda_report": str(eda_path.relative_to(root)),
        "dependency_versions": {
            "python": sys.version.split()[0],
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scikit_learn": sklearn.__version__,
            "lightgbm": lgb.__version__,
        },
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
            "cv_mae_std": round(float(cv_mae.std()), 2),
            "cv_r2_mean": round(float(cv_r2.mean()), 6),
            "cv_r2_std": round(float(cv_r2.std()), 6),
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
    if profile == CORE_ONLY:
        legacy_report = root / "data" / "processed" / "ml_step03_report.json"
        with open(legacy_report, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"Legacy rapor da güncellendi: {legacy_report}")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
