"""
Adım 2 — Feature Engineering (24h tahmin modeli)
=================================================
Girdi: data/processed/encounters_24h.csv
İsteğe bağlı DISCOS: data/processed/discos_object_destination_flat.csv (NORAD birleşimi)

Feature: t0 ölçümleri + yörünge elemanları [+ DISCOS sayısal alanlar]
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

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from ml_pipeline.feature_profiles import CORE_ONLY, get_profile_spec, normalize_profile

def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


# Çekirdek feature'lar — NaN olan satır düşürülür (zorunlu)
CORE_FEATURE_COLS = [
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
META_COLS = [
    "turk_uydu",
    "hiz_t24_km_s",
    "delta_mesafe_km",
    "cop_isim",
    "cop_kaynak",
    "cop_norad_id",
]


def merge_discos_features(df: pd.DataFrame, root: Path, discos_fields: list[str]) -> pd.DataFrame:
    """discos_object_destination_flat.csv ile cop_norad_id üzerinden sol birleşim."""
    if not discos_fields:
        print("\nDISCOS profile kapalı (core_only) — birleşim atlandı.")
        return df
    path = root / "data" / "processed" / "discos_object_destination_flat.csv"
    if not path.exists():
        print(f"\nNOT: DISCOS dosyası yok ({path.name}) — atlanıyor.")
        return df
    if "cop_norad_id" not in df.columns:
        print("\nUYARI: encounters'ta cop_norad_id yok — DISCOS birleştirilemedi.")
        return df
    d = pd.read_csv(path, encoding="utf-8-sig")
    if "norad_id" not in d.columns:
        print("\nUYARI: DISCOS CSV'de norad_id yok.")
        return df
    d = d.sort_values(["norad_id", "destination_orbit_id"], na_position="last")
    d = d.drop_duplicates(subset=["norad_id"], keep="first")
    take = ["norad_id"] + [c for c in discos_fields if c in d.columns]
    d = d[take].copy()
    for c in d.columns:
        if c == "norad_id":
            continue
        d[c] = pd.to_numeric(d[c], errors="coerce")
    ren = {c: f"discos_{c}" for c in d.columns if c != "norad_id"}
    d = d.rename(columns=ren)
    out = df.merge(d, left_on="cop_norad_id", right_on="norad_id", how="left")
    if "norad_id" in out.columns:
        out = out.drop(columns=["norad_id"])
    dcols = [c for c in out.columns if c.startswith("discos_")]
    n_hit = int(out[dcols[0]].notna().sum()) if dcols else 0
    print(f"\nDISCOS birleşimi: {n_hit:,} / {len(out):,} satırda en az bir discos_* alanı dolu")
    return out



def main() -> int:
    ap = argparse.ArgumentParser(description="Feature engineering (dinamik profile)")
    ap.add_argument(
        "--profile",
        default=CORE_ONLY,
        help="Feature profile: core_only | core_plus_discos | core_plus_discos_physical",
    )
    args = ap.parse_args()
    profile = normalize_profile(args.profile)
    spec = get_profile_spec(profile)

    root = project_root()
    in_path = root / "data" / "processed" / "encounters_24h.csv"
    out_path = root / "data" / "processed" / "ml_features_24h.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("Adım 2 — Feature Engineering (24h Tahmin)")
    print("=" * 60)
    print(f"Profile: {spec.profile}")

    if not in_path.exists():
        print(f"HATA: {in_path} bulunamadı.")
        print("Önce: python -m ml_pipeline.build_real_encounters")
        return 1

    df = pd.read_csv(in_path, encoding="utf-8-sig")
    print(f"Kaynak: {len(df):,} satır | {len(df.columns)} sütun")

    df = merge_discos_features(df, root, spec.discos_features)

    # --- Mevcut feature'ları kontrol et ---
    available_core = [c for c in CORE_FEATURE_COLS if c in df.columns]
    missing_features = [c for c in CORE_FEATURE_COLS if c not in df.columns]
    if missing_features:
        print(f"\nUYARI: Eksik çekirdek feature sütunlar: {missing_features}")

    if TARGET_COL not in df.columns:
        print(f"HATA: Target sütun '{TARGET_COL}' bulunamadı.")
        return 1

    discos_feat = [
        c
        for c in df.columns
        if c.startswith("discos_")
        and c.replace("discos_", "", 1) in set(spec.discos_features)
    ]
    print(f"Çekirdek feature: {len(available_core)} | DISCOS (sayısal): {len(discos_feat)}")
    print(f"Target: {TARGET_COL}")

    # --- NaN temizleme (yalnız çekirdek + hedef; DISCOS eksikleri satırı silmez) ---
    n_before = len(df)
    nan_cols = df[available_core + [TARGET_COL]].isna().sum()
    nan_cols_report = nan_cols[nan_cols > 0]
    if len(nan_cols_report) > 0:
        print(f"\nNaN sütunlar:")
        for col, count in nan_cols_report.items():
            print(f"  {col}: {count:,} ({100*count/len(df):.1f}%)")

    df = df.dropna(subset=available_core + [TARGET_COL])
    print(f"\nNaN temizleme: {n_before:,} → {len(df):,} ({n_before - len(df):,} düşürüldü)")

    if len(df) == 0:
        print("HATA: NaN temizleme sonrası veri kalmadı.")
        return 1

    # --- Dağılım kontrolü (skewness) ---
    print(f"\n{'─' * 60}")
    print("DAĞILIM KONTROLÜ")
    print(f"{'─' * 60}")
    available_features = available_core + [c for c in discos_feat if c in df.columns]

    skew_report = {}
    for col in available_features:
        s = df[col].dropna()
        if len(s) < 3:
            print(f"  {col:<25s}  (skew atlandı: yetersiz dolu gözlem)")
            continue
        skew = float(s.skew())
        kurt = float(s.kurtosis())
        skew_report[col] = {"skew": round(skew, 2), "kurt": round(kurt, 2)}
        flag = "⚠️" if abs(skew) > 2 else "✓"
        print(f"  {col:<25s}  skew={skew:>7.2f}  kurt={kurt:>8.2f}  {flag}")

    # --- Log-transform (skew > 2 olan pozitif sütunlar) ---
    log_transformed = []
    for col in available_features:
        s = df[col].dropna()
        if len(s) < 3 or (s <= 0).any():
            continue
        if abs(float(s.skew())) > 2:
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
    corr_matrix = df[available_core].corr()
    high_corr_pairs = []
    for i in range(len(available_core)):
        for j in range(i + 1, len(available_core)):
            r = corr_matrix.iloc[i, j]
            if abs(r) > 0.90:
                high_corr_pairs.append((available_core[i], available_core[j], round(r, 4)))
                print(f"  {available_core[i]:<25s} ↔ {available_core[j]:<25s}  r={r:.4f}")
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
    df_out["feature_profile"] = spec.profile
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
