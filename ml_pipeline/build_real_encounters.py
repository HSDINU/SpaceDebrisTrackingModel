"""
Gerçek Karşılaşma Tablosu — 24 Saatlik Tahmin
===============================================
Her (Türk uydu, çöp) çifti için:
  - t=ŞİMDİ   → mesafe_t0, hız_t0
  - t=+24 saat → mesafe_t24, hız_t24

Feature: yörünge elemanları + mesafe_t0 + hız_t0
Target : mesafe_t24 (gerçek prediction — label leakage yok)

Veri kaynakları:
  - data/processed/cop_verileri_cleaned.csv (temizlenmiş çöp verileri)
  - turk_uydulari.json (9 Türk uydusu TLE)
  - tum_uzay_copleri.csv (ECI snapshot — t0 pozisyonları)
  - cop_verileri.json (TLE — t+24h SGP4 propagation için)

Sentetik veri kullanılmaz.

Çıktı: data/processed/encounters_24h.csv

Çalıştırma:
  python -m ml_pipeline.build_real_encounters
"""
from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sgp4.api import Satrec, jday


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


R_EARTH = 6371.0
DELTA_HOURS = 24  # tahmin penceresi


def sgp4_position(satrec: Satrec, t: datetime):
    """SGP4 ile pozisyon ve hız hesapla."""
    jd, fr = jday(t.year, t.month, t.day, t.hour, t.minute, t.second)
    e, r, v = satrec.sgp4(jd, fr)
    return r, v, e


def parse_tle_orbital(line2: str) -> dict:
    """TLE line2'den yörünge elemanlarını çıkarır."""
    try:
        return {
            "inclination_deg": float(line2[8:16].strip()),
            "raan_deg": float(line2[17:25].strip()),
            "eccentricity": float(f"0.{line2[26:33].strip()}"),
            "arg_perigee_deg": float(line2[34:42].strip()),
            "mean_anomaly_deg": float(line2[43:51].strip()),
            "mean_motion_rev_day": float(line2[52:63].strip()),
        }
    except (ValueError, IndexError):
        return {}


def mean_motion_to_derived(n_rev_day: float, ecc: float) -> dict:
    """Ortalama hareketten türetilmiş parametreler."""
    MU = 398600.4418
    if n_rev_day <= 0:
        return {"semi_major_axis_km": np.nan, "perigee_alt_km": np.nan,
                "apogee_alt_km": np.nan, "period_hours": np.nan}
    n_rad_sec = n_rev_day * 2 * math.pi / 86400.0
    a = (MU / (n_rad_sec ** 2)) ** (1.0 / 3.0)
    return {
        "semi_major_axis_km": round(a, 4),
        "perigee_alt_km": round(a * (1 - ecc) - R_EARTH, 4),
        "apogee_alt_km": round(a * (1 + ecc) - R_EARTH, 4),
        "period_hours": round(2 * math.pi * math.sqrt(a ** 3 / MU) / 3600, 4),
    }


def parse_bstar(line1: str) -> float:
    """TLE line1'den B* sürükleme katsayısını çıkarır."""
    bstar_str = line1[53:61].strip()
    if not bstar_str:
        return 0.0
    try:
        mantissa = bstar_str[:-2].strip()
        exponent = bstar_str[-2:]
        sign = -1 if mantissa[0] == "-" else 1
        if mantissa[0] in "+-":
            mantissa = mantissa[1:]
        return sign * float(f"0.{mantissa}e{exponent}")
    except (ValueError, IndexError):
        return 0.0


TCA_STEP_MIN = 30       # dakika — çözünürlük (hız/kalite dengesi)
TCA_THRESHOLD_KM = 20_000  # km — bu uzaktan yakın TCA hesaplama


def compute_tca(satrec_sat: Satrec, satrec_cop: Satrec,
                t0: datetime, window_h: int = 24,
                step_min: int = TCA_STEP_MIN):
    """
    t0'dan window_h saat içinde minimum yaklaşma mesafesi (TCA) ve zamanı.
    Dönüş: (tca_dist_km, tca_saat_sonra) veya (nan, nan).
    """
    n_steps = int(window_h * 60 / step_min) + 1
    min_dist = float("inf")
    min_t_h = float("nan")
    for i in range(n_steps):
        t = t0 + timedelta(minutes=i * step_min)
        jd, fr = jday(t.year, t.month, t.day, t.hour, t.minute, t.second)
        e_s, r_s, _ = satrec_sat.sgp4(jd, fr)
        e_c, r_c, _ = satrec_cop.sgp4(jd, fr)
        if e_s != 0 or e_c != 0:
            continue
        d = math.sqrt(sum((a - b) ** 2 for a, b in zip(r_s, r_c)))
        if d < min_dist:
            min_dist = d
            min_t_h = i * step_min / 60.0
    return (round(min_dist, 4) if min_dist < float("inf") else float("nan")), min_t_h



def main() -> int:
    root = project_root()
    out_dir = root / "data" / "processed"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "encounters_24h.csv"

    print("=" * 60)
    print(f"Karşılaşma Tablosu — t0 ve t+{DELTA_HOURS}h")
    print("=" * 60)

    # --- 1. Türk uyduları TLE ---
    with open(root / "turk_uydulari.json", encoding="utf-8") as f:
        turk_list = json.load(f)
    print(f"Türk uydusu: {len(turk_list)}")

    # --- 2. Çöp TLE'leri (SGP4 propagation için) ---
    with open(root / "cop_verileri.json", encoding="utf-8") as f:
        cop_tle_list = json.load(f)
    print(f"Çöp TLE: {len(cop_tle_list):,}")

    # --- 3. Temizlenmiş enriched veri (yörünge parametreleri) ---
    cleaned_path = out_dir / "cop_verileri_cleaned.csv"
    if not cleaned_path.exists():
        print("HATA: cop_verileri_cleaned.csv bulunamadı.")
        print("Önce: python -m ml_pipeline.step00_clean_data")
        return 1
    df_clean = pd.read_csv(cleaned_path, encoding="utf-8-sig")
    print(f"Temizlenmiş çöp: {len(df_clean):,}")

    # idx sütunu ile cop_tle_list'e eşleştir
    valid_indices = set(df_clean["idx"].tolist()) if "idx" in df_clean.columns else None

    # --- 4. Referans zamanları ---
    t0 = datetime.now(timezone.utc)
    t24 = t0 + timedelta(hours=DELTA_HOURS)
    print(f"t0  = {t0.isoformat()}")
    print(f"t24 = {t24.isoformat()}")

    # --- 5. Türk uyduları: t0 ve t24 pozisyonları ---
    turk_sats = []
    for sat in turk_list:
        tle1 = sat.get("tle_line1", "")
        tle2 = sat.get("tle_line2", "")
        if not tle1 or not tle2:
            continue

        satrec = Satrec.twoline2rv(tle1, tle2)
        r0, v0, e0 = sgp4_position(satrec, t0)
        r24, v24, e24 = sgp4_position(satrec, t24)

        if e0 != 0 or e24 != 0:
            print(f"  SGP4 hatası: {sat['name']} — atlanıyor")
            continue

        # Türk uydusu yörünge bilgileri
        orb = parse_tle_orbital(tle2)
        derived = mean_motion_to_derived(
            orb.get("mean_motion_rev_day", 0),
            orb.get("eccentricity", 0),
        )

        turk_sats.append({
            "name": sat["name"],
            "norad_id": sat.get("norad_id", ""),
            "satrec": satrec,           # TCA hesabı için
            "r0": np.array(r0), "v0": np.array(v0),
            "r24": np.array(r24), "v24": np.array(v24),
            "turk_inc": orb.get("inclination_deg", np.nan),
            "turk_ecc": orb.get("eccentricity", np.nan),
            "turk_sma": derived.get("semi_major_axis_km", np.nan),
            "turk_perigee": derived.get("perigee_alt_km", np.nan),
        })

    print(f"Hesaplanacak Türk uydusu: {len(turk_sats)}")

    # --- 6. Çöp propagation (t0 ve t24) ---
    print("\nÇöp SGP4 propagation başlıyor...")

    cop_data = []
    sgp4_errors = 0

    for idx, cop in enumerate(cop_tle_list):
        if valid_indices is not None and idx not in valid_indices:
            continue

        tle1 = cop.get("tle_line1", "")
        tle2 = cop.get("tle_line2", "")
        if not tle1 or not tle2:
            continue

        try:
            satrec = Satrec.twoline2rv(tle1, tle2)
            r0, v0, e0 = sgp4_position(satrec, t0)
            r24, v24, e24 = sgp4_position(satrec, t24)
        except Exception:
            sgp4_errors += 1
            continue

        if e0 != 0 or e24 != 0:
            sgp4_errors += 1
            continue

        # Yörünge elemanları
        orb = parse_tle_orbital(tle2)
        derived = mean_motion_to_derived(
            orb.get("mean_motion_rev_day", 0),
            orb.get("eccentricity", 0),
        )
        bstar = parse_bstar(tle1)

        cop_data.append({
            "idx": idx,
            "isim": cop.get("isim", ""),
            "kaynak": cop.get("kaynak", ""),
            "satrec": satrec,           # TCA hesabı için
            "r0": np.array(r0), "v0": np.array(v0),
            "r24": np.array(r24), "v24": np.array(v24),
            "cop_inc": orb.get("inclination_deg", np.nan),
            "cop_ecc": orb.get("eccentricity", np.nan),
            "cop_raan": orb.get("raan_deg", np.nan),
            "cop_argp": orb.get("arg_perigee_deg", np.nan),
            "cop_M": orb.get("mean_anomaly_deg", np.nan),
            "cop_mm": orb.get("mean_motion_rev_day", np.nan),
            "cop_sma": derived.get("semi_major_axis_km", np.nan),
            "cop_perigee": derived.get("perigee_alt_km", np.nan),
            "cop_apogee": derived.get("apogee_alt_km", np.nan),
            "cop_period": derived.get("period_hours", np.nan),
            "cop_bstar": bstar,
        })

    print(f"Başarılı SGP4: {len(cop_data):,} | Hata: {sgp4_errors}")

    # --- 7. Karşılaşma hesabı ---
    print(f"\nKarşılaşma hesabı: {len(turk_sats)} uydu × {len(cop_data):,} çöp...")

    all_rows = []
    for ts in turk_sats:
        r0_sat = ts["r0"]
        v0_sat = ts["v0"]
        r24_sat = ts["r24"]
        v24_sat = ts["v24"]

        for cop in cop_data:
            # t0 mesafe ve hız
            dr0 = np.linalg.norm(r0_sat - cop["r0"])
            dv0 = np.linalg.norm(v0_sat - cop["v0"])

            # t+24h mesafe ve hız
            dr24 = np.linalg.norm(r24_sat - cop["r24"])
            dv24 = np.linalg.norm(v24_sat - cop["v24"])

            # Mesafe değişim trendi
            delta_mesafe = dr24 - dr0  # pozitif=uzaklaşıyor, negatif=yaklaşıyor

            # TCA (Time of Closest Approach) — yalnızca yakın çiftler
            if dr0 < TCA_THRESHOLD_KM and cop.get("satrec") is not None:
                tca_km, tca_saat = compute_tca(ts["satrec"], cop["satrec"], t0)
            else:
                tca_km, tca_saat = float("nan"), float("nan")

            row = {
                # Meta — kimlik bilgileri
                "turk_uydu": ts["name"],
                "cop_isim": cop["isim"],
                "cop_kaynak": cop["kaynak"],
                # Feature: t0 ölçümleri
                "mesafe_t0_km": round(dr0, 4),
                "hiz_t0_km_s": round(dv0, 4),
                # Çöp yörünge elemanları (feature)
                "cop_inclination_deg": cop["cop_inc"],
                "cop_eccentricity": cop["cop_ecc"],
                "cop_raan_deg": cop["cop_raan"],
                "cop_arg_perigee_deg": cop["cop_argp"],
                "cop_mean_anomaly_deg": cop["cop_M"],
                "cop_mean_motion": cop["cop_mm"],
                "cop_sma_km": cop["cop_sma"],
                "cop_perigee_km": cop["cop_perigee"],
                "cop_apogee_km": cop["cop_apogee"],
                "cop_period_hours": cop["cop_period"],
                "cop_bstar": cop["cop_bstar"],
                # Türetilmiş farklar (feature)
                "inc_diff_deg": abs(ts["turk_inc"] - cop["cop_inc"]),
                "perigee_diff_km": abs(ts["turk_perigee"] - cop["cop_perigee"]),
                "sma_diff_km": abs(ts["turk_sma"] - cop["cop_sma"]),
                # Target: t+24h ölçümleri
                "mesafe_t24_km": round(dr24, 4),
                "hiz_t24_km_s": round(dv24, 4),
                "delta_mesafe_km": round(delta_mesafe, 4),
                # TCA — gerçek çarpışma rotası (yakın çiftlerde)
                "tca_km": tca_km,
                "tca_saat": tca_saat,
            }

            all_rows.append(row)

        print(f"  {ts['name']}: {len(cop_data):,} çift  "
              f"(en yakın t0: {min(np.linalg.norm(r0_sat - c['r0']) for c in cop_data):.1f} km)")

    df = pd.DataFrame(all_rows)

    # --- 8. Kaydet ---
    df.to_csv(out_path, index=False, encoding="utf-8-sig")

    print(f"\n{'=' * 60}")
    print(f"Çıktı: {out_path}")
    print(f"Satır: {len(df):,} | Sütun: {len(df.columns)}")
    print(f"\nSütunlar: {list(df.columns)}")

    print(f"\nmesafe_t0 özeti:")
    print(df["mesafe_t0_km"].describe().round(1).to_string())
    print(f"\nmesafe_t24 özeti:")
    print(df["mesafe_t24_km"].describe().round(1).to_string())
    print(f"\ndelta_mesafe özeti:")
    print(df["delta_mesafe_km"].describe().round(1).to_string())

    # Yaklaşan vs uzaklaşan
    yaklasan = (df["delta_mesafe_km"] < 0).sum()
    uzaklasan = (df["delta_mesafe_km"] >= 0).sum()
    print(f"\n24h içinde yaklaşan: {yaklasan:,} ({100*yaklasan/len(df):.1f}%)")
    print(f"24h içinde uzaklaşan: {uzaklasan:,} ({100*uzaklasan/len(df):.1f}%)")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
