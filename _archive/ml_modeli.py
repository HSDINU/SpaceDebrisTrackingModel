"""
LightGBM Risk Modeli — Yalnızca Gerçek Veri
=============================================
Sentetik veri kullanılmaz. Tüm eğitim verisi gerçek yakınlaşma
hesaplamalarından türetilmiştir.

Pipeline sırası:
  1. python cop_verileri_to_csv.py              → cop_verileri_enriched.csv
  2. python -m ml_pipeline.build_real_encounters → turk_uydu_cop_yakinlasma_ml.csv
  3. python -m ml_pipeline.step02_build_features → ml_features_step02.csv
  4. python -m ml_pipeline.step03_train_baseline → lightgbm_risk_modeli.pkl

Bu dosya eğitilmiş modeli yükleyip gerçek veriler üzerinde çalıştırır.
"""

import sys
from pathlib import Path

import joblib
import pandas as pd

ROOT = Path(__file__).resolve().parent
MODEL_PATH = ROOT / "lightgbm_risk_modeli.pkl"
FEATURES_PATH = ROOT / "data" / "processed" / "ml_features_step02.csv"
REPORT_PATH = ROOT / "data" / "processed" / "ml_step03_report.json"

RISK_LABELS = {0: "🟢 Düşük Risk", 1: "🟡 Orta Risk", 2: "🔴 Yüksek Risk"}

# Model eğitiminde kullanılmayan sütunlar
EXCLUDE_COLS = {"risk_sinifi", "turk_uydu_adi", "cop_parca_adi", "cop_kaynak",
                "referans_utc", "turk_norad_id"}


def main() -> int:
    print("=" * 60)
    print("🛰️  LightGBM Risk Modeli — Gerçek Veri")
    print("=" * 60)

    # --- Model kontrolü ---
    if not MODEL_PATH.exists():
        print(
            f"HATA: Model dosyası bulunamadı: {MODEL_PATH}\n"
            "Modeli eğitmek için sırasıyla çalıştırın:\n"
            "  1. python cop_verileri_to_csv.py\n"
            "  2. python -m ml_pipeline.build_real_encounters\n"
            "  3. python -m ml_pipeline.step02_build_features\n"
            "  4. python -m ml_pipeline.step03_train_baseline"
        )
        return 1

    model = joblib.load(MODEL_PATH)
    print(f"Model yüklendi: {MODEL_PATH}")

    # --- Feature dosyası kontrolü ---
    if not FEATURES_PATH.exists():
        print(f"HATA: Feature dosyası bulunamadı: {FEATURES_PATH}")
        return 1

    df = pd.read_csv(FEATURES_PATH, encoding="utf-8-sig")
    feature_cols = [c for c in df.columns if c not in EXCLUDE_COLS]
    X = df[feature_cols].astype(float)
    y_true = df["risk_sinifi"].astype(int) if "risk_sinifi" in df.columns else None

    print(f"Veri: {len(df):,} satır | Feature: {len(feature_cols)} sütun")
    print(f"Feature'lar: {feature_cols}")

    # --- Tahmin ---
    y_pred = model.predict(X)

    # --- Dağılım özeti ---
    print(f"\n--- Tahmin Dağılımı ---")
    for cls in sorted(set(y_pred)):
        n = (y_pred == cls).sum()
        label = RISK_LABELS.get(cls, f"Sınıf {cls}")
        print(f"  {label}: {n:,} ({100*n/len(y_pred):.1f}%)")

    # --- Yüksek riskli olaylar (varsa uydu bilgisi göster) ---
    enc_path = ROOT / "data" / "processed" / "turk_uydu_cop_yakinlasma_ml.csv"
    if enc_path.exists():
        enc_df = pd.read_csv(enc_path, encoding="utf-8-sig")
        high_risk_mask = y_pred == 2
        n_high = high_risk_mask.sum()

        if n_high > 0 and len(enc_df) == len(df):
            print(f"\n--- 🔴 Yüksek Riskli Olaylar (ilk 20) ---")
            high_idx = high_risk_mask.nonzero()[0][:20]
            for idx in high_idx:
                row = enc_df.iloc[idx]
                print(
                    f"  {row.get('turk_uydu_adi', '?')} ← {row.get('cop_parca_adi', '?')} | "
                    f"Mesafe: {row.get('mesafe_km', '?'):.1f} km | "
                    f"Hız: {row.get('bagil_hiz_km_s', '?'):.2f} km/s"
                )

    # --- Rapor bilgisi ---
    if REPORT_PATH.exists():
        import json
        with open(REPORT_PATH, encoding="utf-8") as f:
            report = json.load(f)
        print(f"\n--- Model Eğitim Bilgileri ---")
        print(f"  Eğitim verisi: {report.get('n_train', '?'):,} satır")
        print(f"  Test verisi: {report.get('n_test', '?'):,} satır")
        print(f"  CV Accuracy: {report.get('cv_accuracy_mean', '?')} ± {report.get('cv_accuracy_std', '?')}")
        print(f"  CV F1 Macro: {report.get('cv_f1_macro_mean', '?')} ± {report.get('cv_f1_macro_std', '?')}")
        print(f"  Test Accuracy: {report.get('test_accuracy', '?')}")
        print(f"  Test F1 Macro: {report.get('test_f1_macro', '?')}")

    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())