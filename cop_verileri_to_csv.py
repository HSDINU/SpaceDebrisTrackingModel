"""
cop_verileri.json → Zenginleştirilmiş CSV
==========================================
TLE verilerinden yörünge parametrelerini çıkarır, tum_uzay_copleri.csv ile
birleştirerek tek bir analiz-hazır CSV dosyası üretir.

Sentetik veri kullanılmaz — yalnızca gerçek TLE kayıtları.

Çıktı: data/processed/cop_verileri_enriched.csv

Çalıştırma:
  python cop_verileri_to_csv.py
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd


# --- Sabitler ---
R_EARTH = 6371.0        # km
MU = 398600.4418        # km^3/s^2 (Yer standart çekim parametresi)
MINUTES_PER_DAY = 1440.0


def norad_id_from_line1(line1: str) -> str:
    """TLE line1'den NORAD katalog numarasını çıkarır."""
    parts = line1.split()
    if len(parts) > 1:
        return parts[1].rstrip("U")
    return ""


def parse_tle_epoch(line1: str) -> tuple[int, float]:
    """TLE line1'den epoch yılı ve gününü çıkarır."""
    # Kolon 18-31: YYGGG.GGGGGGGG
    epoch_str = line1[18:32].strip()
    year_2d = int(epoch_str[:2])
    day_frac = float(epoch_str[2:])
    year = 2000 + year_2d if year_2d < 57 else 1900 + year_2d
    return year, day_frac


def parse_bstar(line1: str) -> float:
    """TLE line1'den B* sürükleme katsayısını çıkarır."""
    # Kolon 53-61: BSTAR (özel format: ±NNNNN±N)
    bstar_str = line1[53:61].strip()
    if not bstar_str:
        return 0.0
    try:
        # Format: " NNNNN-N" veya " NNNNN+N"
        mantissa = bstar_str[:-2].strip()
        exponent = bstar_str[-2:]
        if mantissa.startswith("+") or mantissa.startswith("-"):
            sign = -1 if mantissa[0] == "-" else 1
            mantissa = mantissa[1:]
        else:
            sign = 1
        return sign * float(f"0.{mantissa}e{exponent}")
    except (ValueError, IndexError):
        return 0.0


def parse_tle_line2(line2: str) -> dict:
    """TLE line2'den yörünge elemanlarını çıkarır."""
    # TLE line2 sabit genişlik formatı:
    # Kolon  9-16: Eğim (derece)
    # Kolon 18-25: RAAN (derece)
    # Kolon 27-33: Eksantrisite (ondalık nokta olmadan)
    # Kolon 35-42: Periapsis argümanı (derece)
    # Kolon 44-51: Ortalama anomali (derece)
    # Kolon 53-63: Ortalama hareket (devir/gün)
    try:
        inclination = float(line2[8:16].strip())
        raan = float(line2[17:25].strip())
        ecc_str = line2[26:33].strip()
        eccentricity = float(f"0.{ecc_str}")
        arg_perigee = float(line2[34:42].strip())
        mean_anomaly = float(line2[43:51].strip())
        mean_motion = float(line2[52:63].strip())
    except (ValueError, IndexError):
        return {}

    return {
        "inclination_deg": inclination,
        "raan_deg": raan,
        "eccentricity": eccentricity,
        "arg_perigee_deg": arg_perigee,
        "mean_anomaly_deg": mean_anomaly,
        "mean_motion_rev_day": mean_motion,
    }


def derived_from_mean_motion(n_rev_day: float, ecc: float) -> dict:
    """Ortalama hareketten türetilmiş yörünge parametrelerini hesaplar."""
    if n_rev_day <= 0:
        return {
            "semi_major_axis_km": float("nan"),
            "perigee_alt_km": float("nan"),
            "apogee_alt_km": float("nan"),
            "period_hours": float("nan"),
        }

    # Yarı büyük eksen: a = (MU / (2*pi*n/86400)^2)^(1/3)
    n_rad_sec = n_rev_day * 2 * math.pi / 86400.0
    a_km = (MU / (n_rad_sec ** 2)) ** (1.0 / 3.0)

    # Perigee & Apogee irtifası
    perigee_alt = a_km * (1 - ecc) - R_EARTH
    apogee_alt = a_km * (1 + ecc) - R_EARTH

    # Periyot
    period_sec = 2 * math.pi * math.sqrt(a_km ** 3 / MU)
    period_hours = period_sec / 3600.0

    return {
        "semi_major_axis_km": round(a_km, 4),
        "perigee_alt_km": round(perigee_alt, 4),
        "apogee_alt_km": round(apogee_alt, 4),
        "period_hours": round(period_hours, 4),
    }


def classify_orbit(period_hours: float, apogee_alt: float, ecc: float) -> str:
    """Yörünge rejimini sınıflandırır."""
    if math.isnan(period_hours):
        return "UNKNOWN"
    if 23.0 < period_hours < 25.0:
        return "GEO"
    if 11.5 < period_hours < 12.5:
        return "MEO"
    if apogee_alt < 2000:
        return "LEO"
    if ecc > 0.5:
        return "HEO"
    return "OTHER"


def main() -> int:
    root = Path(__file__).resolve().parent
    json_path = root / "cop_verileri.json"
    eci_path = root / "tum_uzay_copleri.csv"
    out_dir = root / "data" / "processed"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "cop_verileri_enriched.csv"

    print("=" * 60)
    print("cop_verileri.json → Zenginleştirilmiş CSV")
    print("=" * 60)

    # --- 1. JSON oku ---
    with open(json_path, encoding="utf-8") as f:
        cop_list = json.load(f)
    print(f"JSON kayıt sayısı: {len(cop_list):,}")

    # --- 2. Her kayıttan TLE parametrelerini çıkar ---
    rows: list[dict] = []
    parse_errors = 0

    for idx, cop in enumerate(cop_list):
        line1 = cop.get("tle_line1", "")
        line2 = cop.get("tle_line2", "")

        norad = norad_id_from_line1(line1)
        try:
            epoch_year, epoch_day = parse_tle_epoch(line1)
        except (ValueError, IndexError):
            epoch_year, epoch_day = 0, 0.0

        bstar = parse_bstar(line1)
        orbital = parse_tle_line2(line2)

        if not orbital:
            parse_errors += 1
            continue

        derived = derived_from_mean_motion(
            orbital["mean_motion_rev_day"],
            orbital["eccentricity"],
        )
        orbit_regime = classify_orbit(
            derived["period_hours"],
            derived["apogee_alt_km"],
            orbital["eccentricity"],
        )

        row = {
            "idx": idx,
            "norad_id": norad,
            "isim": cop.get("isim", ""),
            "kaynak": cop.get("kaynak", ""),
            "epoch_year": epoch_year,
            "epoch_day": round(epoch_day, 8),
            "bstar_drag": bstar,
            **orbital,
            **derived,
            "orbit_regime": orbit_regime,
        }
        rows.append(row)

    df_tle = pd.DataFrame(rows)
    print(f"TLE parse başarılı: {len(df_tle):,} | Hata: {parse_errors}")

    # --- 3. tum_uzay_copleri.csv ile birleştir (indeks sırasıyla) ---
    if eci_path.exists():
        df_eci = pd.read_csv(eci_path, encoding="utf-8-sig")
        print(f"ECI snapshot: {len(df_eci):,} satır")

        if len(df_eci) == len(cop_list):
            # JSON ve CSV aynı sırada — indeks eşleştirmesi
            eci_cols = ["x_km", "y_km", "z_km", "hiz_x_kms", "hiz_y_kms", "hiz_z_kms"]
            for col in eci_cols:
                if col in df_eci.columns:
                    df_tle[col] = df_eci[col].values[:len(df_tle)]
            print("ECI pozisyon/hız sütunları eklendi (indeks eşleştirmesi).")
        else:
            print(
                f"UYARI: JSON ({len(cop_list)}) ve CSV ({len(df_eci)}) satır sayısı "
                "farklı — ECI join atlandı."
            )
    else:
        print("BİLGİ: tum_uzay_copleri.csv bulunamadı — ECI sütunları eklenmedi.")

    # --- 4. Kaydet ---
    df_tle.to_csv(out_path, index=False, encoding="utf-8-sig")

    print(f"\nÇıktı: {out_path}")
    print(f"Satır: {len(df_tle):,} | Sütun: {len(df_tle.columns)}")
    print(f"\nSütunlar: {list(df_tle.columns)}")

    # --- 5. Özet istatistikler ---
    print("\n--- Yörünge İstatistikleri ---")
    for col in ["inclination_deg", "eccentricity", "semi_major_axis_km",
                 "perigee_alt_km", "apogee_alt_km", "period_hours"]:
        if col in df_tle.columns:
            s = df_tle[col].dropna()
            print(f"  {col:.<30} min={s.min():.2f}  max={s.max():.2f}  "
                  f"mean={s.mean():.2f}  std={s.std():.2f}")

    print("\n--- Yörünge Rejimi Dağılımı ---")
    for regime, count in df_tle["orbit_regime"].value_counts().items():
        print(f"  {regime}: {count:,} ({100*count/len(df_tle):.1f}%)")

    print("\n--- Kaynak Dağılımı ---")
    for src, count in df_tle["kaynak"].value_counts().items():
        print(f"  {src}: {count:,} ({100*count/len(df_tle):.1f}%)")

    print("=" * 60)
    print("SONUÇ: cop_verileri_enriched.csv hazır.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
