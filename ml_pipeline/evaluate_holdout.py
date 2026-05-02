"""
Hold-out test kümesinde modeli yeniden ölç — step03 ile aynı train/test ayrımı.

Data leakage özeti (kod yolu):
  • Hedef: mesafe_t24_km (t+24h gerçek mesafe). Özellikler yalnızca t0 mesafe/hız,
    TLE'den çöp + Türk uydu yörünge elemanları ve türev farklar (build_real_encounters).
  • mesafe_t24_km, hiz_t24_km_s, delta_mesafe_km (t24−t0), turk_uydu, cop_isim,
    cop_kaynak eğitim matrisinden çıkarılıyor (step03 EXCLUDE_COLS).
  • delta_mesafe_km doğrudan hedefle ilişkili; özellik listesinde yok (step02 çekirdek feature).
  • tca_km / tca_saat encounters'ta var; ml_features çıktısına alınmıyor (çekirdek feature dışı).
  • cop_norad_id yalnızca birleştirme anahtarı; eğitim matrisinde yok. İsteğe bağlı DISCOS
    sayısal alanları (discos_*) ESA kataloğundan; hedef veya t+24h etiket sızıntısı değildir.

Bu problem sınıflandırma değil regresyon. "Doğruluk" yerine R², RMSE, MAE, MAPE
ve pratik eşikler: |hata| < 100 km / 500 km oranları raporlanır.

Çalıştırma (repo kökünden):
  python -m ml_pipeline.training.evaluate_holdout
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from ml_pipeline.model_artifact import load_predictor
from ml_pipeline.training.training_split import TARGET, replicate_training_split

ROOT = Path(__file__).resolve().parent.parent
FEAT_PATH = ROOT / "data" / "processed" / "ml_features_24h.csv"
MODEL_PATH = ROOT / "lightgbm_risk_modeli.pkl"
REPORT_PATH = ROOT / "data" / "processed" / "ml_step03_report.json"


def main() -> int:
    print("=" * 62)
    print("Hold-out değerlendirme (kayıtlı model × step03 ile aynı test seti)")
    print("=" * 62)

    if not FEAT_PATH.exists():
        print(f"EKSİK: {FEAT_PATH}")
        return 1
    if not MODEL_PATH.exists():
        print(f"EKSİK: {MODEL_PATH}")
        return 1

    df = pd.read_csv(FEAT_PATH, encoding="utf-8-sig")
    if TARGET not in df.columns:
        print(f"HATA: {TARGET} yok.")
        return 1

    model, feature_cols = load_predictor(MODEL_PATH, REPORT_PATH)
    missing = [c for c in feature_cols if c not in df.columns]
    if missing:
        print("EKSİK SÜTUNLAR:", missing[:15])
        return 1

    X = df[feature_cols].astype(float)
    y = df[TARGET].astype(float)

    X_train, X_test, y_train, y_test, meta = replicate_training_split(df, X, y)
    print(f"\nAyrım: {meta['split_method']}")
    print(f"Test örnekleri: {len(y_test):,}")

    y_pred = model.predict(X_test)
    err = y_test.values - y_pred

    rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))
    mae = float(mean_absolute_error(y_test, y_pred))
    r2 = float(r2_score(y_test, y_pred))
    mape = float(
        np.mean(np.abs(err / np.maximum(y_test.values, 1.0))) * 100.0
    )

    # Naive persistence (aynı test seti)
    if "mesafe_t0_km" in X_test.columns:
        y_naive = X_test["mesafe_t0_km"].values
        rmse_naive = float(np.sqrt(mean_squared_error(y_test, y_naive)))
        mae_naive = float(mean_absolute_error(y_test, y_naive))
    else:
        rmse_naive = mae_naive = float("nan")

    within_100 = float(100.0 * np.mean(np.abs(err) < 100.0))
    within_500 = float(100.0 * np.mean(np.abs(err) < 500.0))
    within_1000 = float(100.0 * np.mean(np.abs(err) < 1000.0))

    print(f"\n{'─' * 62}")
    print("TEST METRİKLERİ (kayıtlı model, sadece X_test ile tahmin)")
    print(f"{'─' * 62}")
    print(f"  RMSE (km)     : {rmse:,.2f}")
    print(f"  MAE  (km)     : {mae:,.2f}")
    print(f"  MAPE (%)      : {mape:.2f}")
    print(f"  R²            : {r2:.6f}")
    print(f"\n  |Hata| < 100 km   : {within_100:.2f}% örnek")
    print(f"  |Hata| < 500 km   : {within_500:.2f}% örnek")
    print(f"  |Hata| < 1000 km  : {within_1000:.2f}% örnek")

    if not np.isnan(rmse_naive):
        print(f"\n{'─' * 62}")
        print("Karşılaştırma: Naive (tahmin ≈ mesafe_t0) — aynı test seti")
        print(f"{'─' * 62}")
        print(f"  Naive RMSE: {rmse_naive:,.2f} km  |  Model RMSE: {rmse:,.2f} km")
        print(f"  Naive MAE : {mae_naive:,.2f} km  |  Model MAE : {mae:,.2f} km")
        if rmse_naive > 0:
            print(f"  RMSE iyileşmesi: {(1 - rmse / rmse_naive) * 100:.1f}%")

    if REPORT_PATH.exists():
        import json

        with open(REPORT_PATH, encoding="utf-8") as f:
            rpt = json.load(f)
        t = rpt.get("lightgbm", {})
        print(f"\n{'─' * 62}")
        print("ml_step03_report.json (eğitim anı — karşılaştırma)")
        print(f"{'─' * 62}")
        print(f"  Rapor test_RMSE: {t.get('test_rmse')}  |  Yeniden ölçüm: {rmse:.2f}")
        print(f"  Rapor test_R²  : {t.get('test_r2')}  |  Yeniden ölçüm: {r2:.6f}")

    print("\nNot: Regresyonda 'doğruluk%' tek sayı değildir; R² ve eşik oranları birlikte okunur.")
    print("=" * 62)
    return 0


if __name__ == "__main__":
    sys.exit(main())
