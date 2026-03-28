"""
Adım 2 — Feature Engineering (24h tahmin modeli)
=================================================
Girdi: data/processed/encounters_24h.csv

Feature: t0 ölçümleri + yörünge elemanları
Target : mesafe_t24_km (regression — label leakage yok)

Kontroller:
  1. NaN temizleme
  2. Feature korelasyon analizi
  3. Dağılım kontrolü (skewness)
  4. Log-transform (sağa çarpık sütunlar)
  5. Feature listesi dışarı yaz

Çıktı: data/processed/ml_features_24h.csv

Çalıştırma:
  python -m ml_pipeline.step02_build_features
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


# Feature sütunları (model eğitiminde kullanılacak)
FEATURE_COLS = [
    # t0 ölçümleri
    "mesafe_t0_km",
    "hiz_t0_km_s",
    # Çöp yörünge elemanları
    "cop_inclination_deg",
    "cop_eccentricity",
    "cop_raan_deg",
    "cop_arg_perigee_deg",
    "cop_mean_anomaly_deg",
    "cop_mean_motion",
    "cop_sma_km",
    "cop_perigee_km",
    "cop_apogee_km",
    "cop_period_hours",
    "cop_bstar",
    # Türetilmiş farklar
    "inc_diff_deg",
    "perigee_diff_km",
    "sma_diff_km",
]

# Target
TARGET_COL = "mesafe_t24_km"

# Meta sütunlar (eğitimde kullanılmaz)
META_COLS = ["turk_uydu", "hiz_t24_km_s", "delta_mesafe_km", "cop_isim", "cop_kaynak"]



def main() -> int:
    root = project_root()
    in_path = root / "data" / "processed" / "encounters_24h.csv"
    out_path = root / "data" / "processed" / "ml_features_24h.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("Adım 2 — Feature Engineering (24h Tahmin)")
    print("=" * 60)

    if not in_path.exists():
        print(f"HATA: {in_path} bulunamadı.")
        print("Önce: python -m ml_pipeline.build_real_encounters")
        return 1

    df = pd.read_csv(in_path, encoding="utf-8-sig")
    print(f"Kaynak: {len(df):,} satır | {len(df.columns)} sütun")

    # --- Mevcut feature'ları kontrol et ---
    available_features = [c for c in FEATURE_COLS if c in df.columns]
    missing_features = [c for c in FEATURE_COLS if c not in df.columns]
    if missing_features:
        print(f"\nUYARI: Eksik feature sütunlar: {missing_features}")

    if TARGET_COL not in df.columns:
        print(f"HATA: Target sütun '{TARGET_COL}' bulunamadı.")
        return 1

    print(f"Feature sayısı: {len(available_features)}")
    print(f"Target: {TARGET_COL}")

    # --- NaN temizleme ---
    n_before = len(df)
    nan_cols = df[available_features + [TARGET_COL]].isna().sum()
    nan_cols_report = nan_cols[nan_cols > 0]
    if len(nan_cols_report) > 0:
        print(f"\nNaN sütunlar:")
        for col, count in nan_cols_report.items():
            print(f"  {col}: {count:,} ({100*count/len(df):.1f}%)")

    df = df.dropna(subset=available_features + [TARGET_COL])
    print(f"\nNaN temizleme: {n_before:,} → {len(df):,} ({n_before - len(df):,} düşürüldü)")

    if len(df) == 0:
        print("HATA: NaN temizleme sonrası veri kalmadı.")
        return 1

    # --- Dağılım kontrolü (skewness) ---
    print(f"\n{'─' * 60}")
    print("DAĞILIM KONTROLÜ")
    print(f"{'─' * 60}")
    skew_report = {}
    for col in available_features:
        skew = float(df[col].skew())
        kurt = float(df[col].kurtosis())
        skew_report[col] = {"skew": round(skew, 2), "kurt": round(kurt, 2)}
        flag = "⚠️" if abs(skew) > 2 else "✓"
        print(f"  {col:<25s}  skew={skew:>7.2f}  kurt={kurt:>8.2f}  {flag}")

    # --- Log-transform (skew > 2 olan pozitif sütunlar) ---
    log_transformed = []
    for col in available_features:
        if abs(df[col].skew()) > 2 and (df[col] > 0).all():
            df[f"{col}_log"] = np.log1p(df[col])
            log_transformed.append(col)

    if log_transformed:
        print(f"\nLog-transform uygulanan: {log_transformed}")
        # Log versiyonları ek feature olarak ekle (orijinal de kalır)

    # --- Feature korelasyon analizi ---
    print(f"\n{'─' * 60}")
    print(f"TARGET KORELASYONLARı ({TARGET_COL})")
    print(f"{'─' * 60}")
    all_feature_cols = available_features + [f"{c}_log" for c in log_transformed]
    corr = df[all_feature_cols].corrwith(df[TARGET_COL]).round(4)
    # Korelasyona göre sırala
    corr_sorted = corr.abs().sort_values(ascending=False)
    for col in corr_sorted.index:
        val = corr[col]
        strength = "GÜÇLÜ" if abs(val) > 0.5 else "ORTA" if abs(val) > 0.2 else "ZAYIF"
        print(f"  {col:<30s}  r={val:>7.4f}  ({strength})")

    # --- Feature arası yüksek korelasyon kontrolü ---
    print(f"\n{'─' * 60}")
    print("YÜKSEK FEATURE-FEATURE KORELASYONLARI (|r| > 0.90)")
    print(f"{'─' * 60}")
    corr_matrix = df[available_features].corr()
    high_corr_pairs = []
    for i in range(len(available_features)):
        for j in range(i + 1, len(available_features)):
            r = corr_matrix.iloc[i, j]
            if abs(r) > 0.90:
                high_corr_pairs.append((available_features[i], available_features[j], round(r, 4)))
                print(f"  {available_features[i]:<25s} ↔ {available_features[j]:<25s}  r={r:.4f}")
    if not high_corr_pairs:
        print("  Yüksek korelasyonlu feature çifti yok ✓")

    # --- Çıktı oluştur ---
    output_features = available_features + [f"{c}_log" for c in log_transformed]
    output_cols = output_features + [TARGET_COL]
    # Meta bilgileri de tut (analiz için)
    for mc in META_COLS:
        if mc in df.columns:
            output_cols.append(mc)

    df_out = df[output_cols].copy()
    df_out.to_csv(out_path, index=False, encoding="utf-8-sig")

    print(f"\n{'=' * 60}")
    print(f"Çıktı: {out_path}")
    print(f"Satır: {len(df_out):,}")
    print(f"Feature sayısı: {len(output_features)}")
    print(f"Feature list: {output_features}")
    print(f"Target: {TARGET_COL}")

    # Target özeti
    print(f"\nTarget ({TARGET_COL}) özeti:")
    print(df_out[TARGET_COL].describe().round(2).to_string())
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
