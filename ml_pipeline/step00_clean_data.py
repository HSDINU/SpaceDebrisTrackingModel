"""
Adım 0 — Veri Temizleme (İstatistiki Teste Dayalı)
=====================================================
cop_verileri_enriched.csv üzerinde:
  1. Açısal wrap-around düzeltme (>360° → mod 360)
  2. Fiziksel sınır kontrolü (e∈[0,1), i∈[0,180], SMA>R_Earth)
  3. bstar_drag negatif → clip
  4. IQR*3 outlier flagging (silmek yerine flag)
  5. Log-transform (sağa çarpık dağılımlar)
  6. Shapiro-Wilk + skewness/kurtosis raporu

Sentetik veri kullanılmaz.

Çıktı: data/processed/cop_verileri_cleaned.csv
       data/processed/cleaning_report.json

Çalıştırma:
  python -m ml_pipeline.data.step00_clean_data
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats


R_EARTH = 6371.0


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def main() -> int:
    root = project_root()
    enriched_path = root / "data" / "processed" / "cop_verileri_enriched.csv"
    out_path = root / "data" / "processed" / "cop_verileri_cleaned.csv"
    report_path = root / "data" / "processed" / "cleaning_report.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("Adım 0 — Veri Temizleme (İstatistiki Teste Dayalı)")
    print("=" * 60)

    if not enriched_path.exists():
        print(f"HATA: {enriched_path} bulunamadı.\nÖnce: python cop_verileri_to_csv.py")
        return 1

    df = pd.read_csv(enriched_path, encoding="utf-8-sig")
    n_original = len(df)
    print(f"Orijinal kayıt: {n_original:,}")
    report: dict = {"n_original": n_original, "steps": []}

    # ═══════════════════════════════════════════
    # 1) AÇISAL WRAP-AROUND DÜZELTMESİ
    # ═══════════════════════════════════════════
    print("\n--- 1) Açısal Wrap-Around ---")
    angular_cols = ["raan_deg", "arg_perigee_deg", "mean_anomaly_deg"]
    fixes = {}
    for col in angular_cols:
        if col not in df.columns:
            continue
        bad = ((df[col] < 0) | (df[col] > 360)).sum()
        if bad > 0:
            df[col] = df[col] % 360
            fixes[col] = int(bad)
            print(f"  {col}: {bad} değer düzeltildi (mod 360)")
        else:
            print(f"  {col}: temiz ✓")
    report["steps"].append({"name": "angular_wrap", "fixes": fixes})

    # ═══════════════════════════════════════════
    # 2) FİZİKSEL SINIR KONTROLÜ
    # ═══════════════════════════════════════════
    print("\n--- 2) Fiziksel Sınır Kontrolü ---")
    mask_valid = pd.Series(True, index=df.index)
    phys_drops = {}

    # Eksantrisite [0, 1)
    if "eccentricity" in df.columns:
        bad = (df["eccentricity"] < 0) | (df["eccentricity"] >= 1)
        phys_drops["eccentricity_out_of_range"] = int(bad.sum())
        mask_valid &= ~bad
        print(f"  Eksantrisite [0,1) dışı: {bad.sum()}")

    # Eğim [0, 180]
    if "inclination_deg" in df.columns:
        bad = (df["inclination_deg"] < 0) | (df["inclination_deg"] > 180)
        phys_drops["inclination_out_of_range"] = int(bad.sum())
        mask_valid &= ~bad
        print(f"  Eğim [0,180] dışı: {bad.sum()}")

    # SMA > R_Earth
    if "semi_major_axis_km" in df.columns:
        bad = df["semi_major_axis_km"] < R_EARTH
        phys_drops["sma_below_earth"] = int(bad.sum())
        mask_valid &= ~bad
        print(f"  SMA < R_Earth: {bad.sum()}")

    # Perigee negatif kontrol — çok düşükse çıkar (re-entry)
    if "perigee_alt_km" in df.columns:
        bad = df["perigee_alt_km"] < 0
        phys_drops["negative_perigee"] = int(bad.sum())
        mask_valid &= ~bad
        print(f"  Negatif perigee: {bad.sum()}")

    # Periyot çok kısa (< 30 dakika = fiziksel olarak imkansız)
    if "period_hours" in df.columns:
        bad = df["period_hours"] < 0.5
        phys_drops["period_too_short"] = int(bad.sum())
        mask_valid &= ~bad
        print(f"  Periyot < 30 dk: {bad.sum()}")

    n_phys_dropped = (~mask_valid).sum()
    df = df[mask_valid].reset_index(drop=True)
    print(f"  → Fiziksel ihlallerden düşürülen: {n_phys_dropped}")
    report["steps"].append({"name": "physical_bounds", "dropped": int(n_phys_dropped),
                            "details": phys_drops})

    # ═══════════════════════════════════════════
    # 3) BSTAR DRAG TEMİZLEME
    # ═══════════════════════════════════════════
    print("\n--- 3) bstar_drag Temizleme ---")
    if "bstar_drag" in df.columns:
        n_neg = (df["bstar_drag"] < 0).sum()
        # Aşırı negatif değerler fiziksel değil → clip to [-0.01, 0.5]
        df["bstar_drag"] = df["bstar_drag"].clip(-0.01, 0.5)
        n_clipped = (df["bstar_drag"] == -0.01).sum() + (df["bstar_drag"] == 0.5).sum()
        print(f"  Negatif bstar: {n_neg} → clip [-0.01, 0.5] uygulandı")
        report["steps"].append({"name": "bstar_clip", "n_negative": int(n_neg),
                                "n_clipped": int(n_clipped)})

    # ═══════════════════════════════════════════
    # 4) IQR OUTLIER FLAGGING (silmek yerine flag)
    # ═══════════════════════════════════════════
    print("\n--- 4) IQR*3 Outlier Flagging ---")
    outlier_cols = ["eccentricity", "semi_major_axis_km", "perigee_alt_km",
                    "apogee_alt_km", "bstar_drag", "mean_motion_rev_day", "period_hours"]
    df["is_outlier"] = False
    outlier_counts = {}
    for col in outlier_cols:
        if col not in df.columns:
            continue
        s = df[col].dropna()
        q1, q3 = s.quantile(0.25), s.quantile(0.75)
        iqr = q3 - q1
        if iqr == 0:
            continue
        low, high = q1 - 3 * iqr, q3 + 3 * iqr
        is_out = (df[col] < low) | (df[col] > high)
        n_out = is_out.sum()
        df.loc[is_out, "is_outlier"] = True
        outlier_counts[col] = int(n_out)
        if n_out > 0:
            print(f"  {col:<25s}: {n_out:,} outlier ({100*n_out/len(df):.1f}%)")
    total_outlier = df["is_outlier"].sum()
    print(f"  → Toplam outlier-flagged satır: {total_outlier:,} ({100*total_outlier/len(df):.1f}%)")
    report["steps"].append({"name": "outlier_flagging", "counts": outlier_counts,
                            "total_flagged": int(total_outlier)})

    # ═══════════════════════════════════════════
    # 5) İSTATİSTİKİ TESTLER
    # ═══════════════════════════════════════════
    print("\n--- 5) İstatistiki Testler ---")
    test_cols = ["inclination_deg", "eccentricity", "semi_major_axis_km",
                 "perigee_alt_km", "apogee_alt_km", "bstar_drag"]
    stat_results = {}
    for col in test_cols:
        if col not in df.columns:
            continue
        s = df[col].dropna()
        sample = s.sample(min(5000, len(s)), random_state=42)
        # Shapiro-Wilk
        w_stat, w_p = stats.shapiro(sample)
        skew = float(s.skew())
        kurt = float(s.kurtosis())
        normal = w_p > 0.05
        stat_results[col] = {
            "shapiro_W": round(float(w_stat), 4),
            "shapiro_p": float(w_p),
            "skewness": round(skew, 4),
            "kurtosis": round(kurt, 4),
            "is_normal": normal,
        }
        status = "Normal" if normal else "Non-Normal"
        print(f"  {col:<25s}  W={w_stat:.4f}  p={w_p:.2e}  skew={skew:.2f}  "
              f"kurt={kurt:.2f}  → {status}")
    report["steps"].append({"name": "statistical_tests", "results": stat_results})

    # ═══════════════════════════════════════════
    # 6) NaN TEMİZLEME
    # ═══════════════════════════════════════════
    print("\n--- 6) NaN Temizleme ---")
    nan_before = df.isna().sum().sum()
    n_before = len(df)
    df = df.dropna(subset=["inclination_deg", "eccentricity", "semi_major_axis_km",
                            "perigee_alt_km", "apogee_alt_km"])
    n_nan_dropped = n_before - len(df)
    print(f"  NaN hücre: {nan_before} → {n_nan_dropped} satır düşürüldü")
    report["steps"].append({"name": "nan_cleanup", "nan_cells": int(nan_before),
                            "rows_dropped": int(n_nan_dropped)})

    # ═══════════════════════════════════════════
    # KAYDET
    # ═══════════════════════════════════════════
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    report["n_final"] = len(df)
    report["n_total_dropped"] = n_original - len(df)

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)

    print(f"\n{'=' * 60}")
    print(f"TEMİZLEME SONUCU")
    print(f"  Orijinal : {n_original:,}")
    print(f"  Düşürülen: {n_original - len(df):,}")
    print(f"  Kalan    : {len(df):,}")
    print(f"  Outlier  : {df['is_outlier'].sum():,} (flagged, silinmedi)")
    print(f"\nÇıktı: {out_path}")
    print(f"Rapor: {report_path}")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
