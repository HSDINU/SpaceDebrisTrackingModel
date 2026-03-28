"""
Outlier Etkisi Analizi — Senior DS Karşılaştırması
=====================================================
1. Outlier DAHİL (mevcut sonuç)
2. Outlier ÇIKARILMIŞ (is_outlier=True satırlar çıkartılır)
3. Naive Baseline her ikisinde de ayrı hesaplanır
4. İstatistiki karşılaştırma + yorum
"""
import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from scipy import stats as scipy_stats
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import KFold, cross_val_score, train_test_split

import lightgbm as lgb

ROOT = Path(__file__).resolve().parent
FEAT_PATH = ROOT / "data" / "processed" / "ml_features_24h.csv"
ENC_PATH = ROOT / "data" / "processed" / "encounters_24h.csv"
CLEANED_PATH = ROOT / "data" / "processed" / "cop_verileri_cleaned.csv"

TARGET = "mesafe_t24_km"
EXCLUDE = {"mesafe_t24_km", "turk_uydu", "hiz_t24_km_s", "delta_mesafe_km"}


def train_and_evaluate(X_train, X_test, y_train, y_test, label, feature_cols):
    """LightGBM eğit ve sonuçları döndür."""
    model = lgb.LGBMRegressor(
        n_estimators=500, learning_rate=0.05, num_leaves=63,
        max_depth=8, min_child_samples=20, subsample=0.8,
        colsample_bytree=0.8, random_state=42, verbose=-1,
    )

    # CV
    cv = KFold(n_splits=5, shuffle=True, random_state=42)
    X_all = pd.concat([X_train, X_test])
    y_all = pd.concat([y_train, y_test])
    cv_rmse = -cross_val_score(model, X_all, y_all, cv=cv, scoring="neg_root_mean_squared_error")
    cv_r2 = cross_val_score(model, X_all, y_all, cv=cv, scoring="r2")

    # Final model
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)

    # Naive baseline
    y_naive = X_test["mesafe_t0_km"].values if "mesafe_t0_km" in X_test.columns else y_test.values

    results = {
        "label": label,
        "n_train": len(X_train),
        "n_test": len(X_test),
        "n_total": len(X_all),
        # Naive
        "naive_rmse": np.sqrt(mean_squared_error(y_test, y_naive)),
        "naive_mae": mean_absolute_error(y_test, y_naive),
        "naive_r2": r2_score(y_test, y_naive),
        # LightGBM
        "lgbm_rmse": np.sqrt(mean_squared_error(y_test, y_pred)),
        "lgbm_mae": mean_absolute_error(y_test, y_pred),
        "lgbm_r2": r2_score(y_test, y_pred),
        "lgbm_cv_rmse_mean": cv_rmse.mean(),
        "lgbm_cv_rmse_std": cv_rmse.std(),
        "lgbm_cv_r2_mean": cv_r2.mean(),
        "lgbm_cv_r2_std": cv_r2.std(),
        # Residuals
        "residuals": y_test.values - y_pred,
        "y_pred": y_pred,
        "y_test": y_test.values,
    }
    return results, model


def main():
    print("=" * 70)
    print("OUTLIER ETKİSİ ANALİZİ — Senior Data Scientist Raporu")
    print("=" * 70)

    # --- Veri yükle ---
    df = pd.read_csv(FEAT_PATH, encoding="utf-8-sig")
    feature_cols = [c for c in df.columns if c not in EXCLUDE]

    # Outlier bilgisi encounter'dan al
    enc_df = pd.read_csv(ENC_PATH, encoding="utf-8-sig")

    # Cleaned CSV'den outlier flag'i al
    cleaned_df = pd.read_csv(CLEANED_PATH, encoding="utf-8-sig")
    outlier_indices = set(cleaned_df[cleaned_df["is_outlier"] == True].index.tolist())

    # Encounter'daki her satır bir (uydu, çöp) çifti
    # Çöp indeksi = satır_no % n_cop (yaklaşık)
    n_cop = len(cleaned_df)

    # Outlier flag'ini feature df'e ekle
    # Encounter sırası: her uydu için tüm çöpler sırayla
    cop_idx_in_enc = np.arange(len(df)) % n_cop
    df["_is_outlier"] = [int(i) in outlier_indices for i in cop_idx_in_enc]

    n_outlier_rows = df["_is_outlier"].sum()
    print(f"\nToplam satır: {len(df):,}")
    print(f"Outlier-flagged satır: {n_outlier_rows:,} ({100*n_outlier_rows/len(df):.1f}%)")
    print(f"Temiz satır: {len(df) - n_outlier_rows:,}")

    # ═══════════════════════════════════════════
    # SENARYO 1: TÜM VERİ (outlier dahil)
    # ═══════════════════════════════════════════
    print(f"\n{'═' * 70}")
    print("SENARYO 1: TÜM VERİ (outlier DAHİL)")
    print(f"{'═' * 70}")

    X1 = df[feature_cols].astype(float)
    y1 = df[TARGET].astype(float)
    X1_train, X1_test, y1_train, y1_test = train_test_split(
        X1, y1, test_size=0.2, random_state=42
    )
    r1, m1 = train_and_evaluate(X1_train, X1_test, y1_train, y1_test, "ALL_DATA", feature_cols)

    print(f"  Naive RMSE : {r1['naive_rmse']:.2f} km | R²: {r1['naive_r2']:.6f}")
    print(f"  LGBM  RMSE : {r1['lgbm_rmse']:.2f} km | R²: {r1['lgbm_r2']:.6f}")
    print(f"  CV    RMSE : {r1['lgbm_cv_rmse_mean']:.2f} ± {r1['lgbm_cv_rmse_std']:.2f}")

    # ═══════════════════════════════════════════
    # SENARYO 2: OUTLIER ÇIKARILMIŞ
    # ═══════════════════════════════════════════
    print(f"\n{'═' * 70}")
    print("SENARYO 2: OUTLIER ÇIKARILMIŞ")
    print(f"{'═' * 70}")

    df_clean = df[~df["_is_outlier"]].copy()
    X2 = df_clean[feature_cols].astype(float)
    y2 = df_clean[TARGET].astype(float)
    X2_train, X2_test, y2_train, y2_test = train_test_split(
        X2, y2, test_size=0.2, random_state=42
    )
    r2, m2 = train_and_evaluate(X2_train, X2_test, y2_train, y2_test, "NO_OUTLIER", feature_cols)

    print(f"  Naive RMSE : {r2['naive_rmse']:.2f} km | R²: {r2['naive_r2']:.6f}")
    print(f"  LGBM  RMSE : {r2['lgbm_rmse']:.2f} km | R²: {r2['lgbm_r2']:.6f}")
    print(f"  CV    RMSE : {r2['lgbm_cv_rmse_mean']:.2f} ± {r2['lgbm_cv_rmse_std']:.2f}")

    # ═══════════════════════════════════════════
    # KARŞILAŞTIRMA TABLOSU
    # ═══════════════════════════════════════════
    print(f"\n{'═' * 70}")
    print("KARŞILAŞTIRMA TABLOSU")
    print(f"{'═' * 70}")
    print(f"\n{'Metrik':<20} {'Tüm Veri':>15} {'Outlier Yok':>15} {'Fark':>12} {'Yorum':>15}")
    print("─" * 80)

    metrics = [
        ("N (satır)", r1["n_total"], r2["n_total"], ""),
        ("Naive RMSE (km)", r1["naive_rmse"], r2["naive_rmse"], "baseline"),
        ("Naive R²", r1["naive_r2"], r2["naive_r2"], "baseline"),
        ("LGBM RMSE (km)", r1["lgbm_rmse"], r2["lgbm_rmse"], "model"),
        ("LGBM MAE (km)", r1["lgbm_mae"], r2["lgbm_mae"], "model"),
        ("LGBM R²", r1["lgbm_r2"], r2["lgbm_r2"], "model"),
        ("CV RMSE (km)", r1["lgbm_cv_rmse_mean"], r2["lgbm_cv_rmse_mean"], "cv"),
        ("CV R²", r1["lgbm_cv_r2_mean"], r2["lgbm_cv_r2_mean"], "cv"),
    ]

    for name, v1, v2, mtype in metrics:
        if isinstance(v1, int):
            diff = f"{v2 - v1:+d}"
            print(f"  {name:<20} {v1:>15,d} {v2:>15,d} {diff:>12}")
        else:
            diff_pct = ((v2 - v1) / abs(v1) * 100) if v1 != 0 else 0
            direction = "↑ iyi" if (mtype == "model" and v2 < v1) or (mtype in ("baseline", "cv") and v2 < v1) else "↓"
            if "R²" in name:
                direction = "↑ iyi" if v2 > v1 else "↓"
            print(f"  {name:<20} {v1:>15.4f} {v2:>15.4f} {diff_pct:>+11.2f}% {direction}")

    # ═══════════════════════════════════════════
    # REZİDÜEL KARŞILAŞTIRMASI
    # ═══════════════════════════════════════════
    print(f"\n{'═' * 70}")
    print("REZİDÜEL ANALİZİ")
    print(f"{'═' * 70}")
    for label, res in [("Tüm Veri", r1), ("Outlier Yok", r2)]:
        resid = res["residuals"]
        print(f"\n  {label}:")
        print(f"    mean  : {resid.mean():>10.2f} km")
        print(f"    std   : {resid.std():>10.2f} km")
        print(f"    median: {np.median(resid):>10.2f} km")
        print(f"    |r|<100km : {100*(np.abs(resid)<100).sum()/len(resid):>6.1f}%")
        print(f"    |r|<500km : {100*(np.abs(resid)<500).sum()/len(resid):>6.1f}%")
        print(f"    |r|<1000km: {100*(np.abs(resid)<1000).sum()/len(resid):>6.1f}%")

        # Shapiro-Wilk on residuals (sample)
        sample = np.random.RandomState(42).choice(resid, min(5000, len(resid)), replace=False)
        w, p = scipy_stats.shapiro(sample)
        print(f"    Rezidüel Shapiro-Wilk: W={w:.4f} p={p:.2e} → {'Normal' if p > 0.05 else 'Non-Normal'}")

    # ═══════════════════════════════════════════
    # LEVENE TESTİ (varyans homojenliği)
    # ═══════════════════════════════════════════
    print(f"\n{'═' * 70}")
    print("LEVENE TESTİ (Rezidüel Varyans Homojenliği)")
    print(f"{'═' * 70}")
    # Outlier grubu vs temiz grup residualleri karşılaştır
    # Bunun için tüm veri modelinin residuallerini outlier/non-outlier grubuna ayır
    full_pred = m1.predict(X1)
    full_resid = y1.values - full_pred
    test_idx = X1_test.index
    train_mask = ~df.index.isin(test_idx)

    outlier_mask_full = df["_is_outlier"].values
    resid_outlier = full_resid[outlier_mask_full]
    resid_clean = full_resid[~outlier_mask_full]

    if len(resid_outlier) > 0 and len(resid_clean) > 0:
        lev_stat, lev_p = scipy_stats.levene(resid_outlier, resid_clean)
        print(f"  Levene statistic: {lev_stat:.4f}")
        print(f"  p-value: {lev_p:.2e}")
        print(f"  Yorum: {'Varyanslar FARKLI (outlier grup daha gürültülü)' if lev_p < 0.05 else 'Varyanslar homojen'}")
        print(f"\n  Outlier grubu rezidüel std : {resid_outlier.std():.2f} km")
        print(f"  Temiz grubu rezidüel std   : {resid_clean.std():.2f} km")
        print(f"  Oran: {resid_outlier.std() / resid_clean.std():.2f}x")

    # ═══════════════════════════════════════════
    # MANN-WHITNEY U TESTİ
    # ═══════════════════════════════════════════
    print(f"\n{'═' * 70}")
    print("MANN-WHITNEY U TESTİ (Rezidüel Dağılım Farkı)")
    print(f"{'═' * 70}")
    if len(resid_outlier) > 0 and len(resid_clean) > 0:
        u_stat, u_p = scipy_stats.mannwhitneyu(
            np.abs(resid_outlier), np.abs(resid_clean), alternative="greater"
        )
        print(f"  U statistic: {u_stat:.0f}")
        print(f"  p-value: {u_p:.2e}")
        print(f"  H0: Outlier grubu hata = Temiz grubu hata")
        print(f"  Yorum: {'REJECT H0 — Outlier grubu SİSTEMATİK olarak daha büyük hata' if u_p < 0.05 else 'H0 reddedilemez'}")

    # ═══════════════════════════════════════════
    # SONUÇ RAPORU
    # ═══════════════════════════════════════════
    print(f"\n{'═' * 70}")
    print("SONUÇ RAPORU")
    print(f"{'═' * 70}")

    rmse_change = (r2["lgbm_rmse"] - r1["lgbm_rmse"]) / r1["lgbm_rmse"] * 100
    r2_change = r2["lgbm_r2"] - r1["lgbm_r2"]

    report = {
        "all_data": {
            "n": r1["n_total"],
            "naive_rmse": round(r1["naive_rmse"], 2),
            "lgbm_rmse": round(r1["lgbm_rmse"], 2),
            "lgbm_r2": round(r1["lgbm_r2"], 6),
        },
        "no_outlier": {
            "n": r2["n_total"],
            "naive_rmse": round(r2["naive_rmse"], 2),
            "lgbm_rmse": round(r2["lgbm_rmse"], 2),
            "lgbm_r2": round(r2["lgbm_r2"], 6),
        },
        "rmse_change_pct": round(rmse_change, 2),
        "r2_change": round(r2_change, 6),
    }

    with open(ROOT / "data" / "processed" / "outlier_analysis_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n  RMSE değişimi: {rmse_change:+.2f}%")
    print(f"  R² değişimi : {r2_change:+.6f}")

    if r2["lgbm_rmse"] < r1["lgbm_rmse"]:
        print("\n  ✅ Outlier çıkarmak modeli İYİLEŞTİRDİ")
        print("     → Outlier'lar modelin öğrenme kapasitesini zorluyor")
    else:
        print("\n  ℹ️  Outlier çıkarmak modeli İYİLEŞTİRMEDİ veya minimal etki")
        print("     → LightGBM tree-based model, outlier'lara doğal olarak dayanıklı")
        print("     → Bu outlier'lar gerçek fiziksel durumları temsil ediyor olabilir (GTO/HEO)")

    print("=" * 70)


if __name__ == "__main__":
    main()
