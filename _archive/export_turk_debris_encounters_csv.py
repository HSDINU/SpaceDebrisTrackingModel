"""
Türk uyduları × uzay çöpü yakınlaşmalarını tek bir ML odaklı CSV'ye aktarır.

İlişki:
  - data/processed/*_combined.csv  → Kepler elemanları (.dat boru hattı, genel deb/uydü seti)
  - Bu scriptin çıktısı            → TLE + SGP4 ile seçilen Türk varlıklarına özgü yakınlaşma olayları

Varsayılan mod: Her (Türk uydu, çöp) çifti için simülasyon penceresindeki *en yakın geçiş* (TCA)
tek satırda; ml_modeli.py ile aynı mesafe/hız eşiklerinden türetilen risk_sinifi sütunu.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sgp4.api import Satrec, jday


def norad_from_tle_line1(line1: str) -> str:
    parts = line1.split()
    if len(parts) > 1:
        return parts[1].rstrip("U")
    return ""


def risk_sinifi(mesafe_km: float, bagil_hiz_km_s: float) -> int:
    """ml_modeli.risk_etiketle ile aynı mantık (0=düşük, 1=orta, 2=yüksek)."""
    if mesafe_km < 15.0 and bagil_hiz_km_s > 7.0:
        return 2
    if mesafe_km < 40.0:
        return 1
    return 0


def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def run_encounters(
    turk_path: Path,
    cop_path: Path,
    *,
    zaman_adimi_dk: int,
    sure_saat: int,
    mesafe_esik_km: float,
    max_debris: int | None,
    raw_timesteps: bool,
) -> list[dict]:
    hedefler = load_json(turk_path)
    coplar = load_json(cop_path)
    if max_debris is not None and max_debris > 0:
        coplar = coplar[:max_debris]

    t0 = datetime.now(timezone.utc)
    zaman_adimlari = [
        t0 + timedelta(minutes=zaman_adimi_dk * i)
        for i in range(int(sure_saat * 60 / zaman_adimi_dk))
    ]

    if raw_timesteps:
        satirlar: list[dict] = []
        olay_no = 0
        for hedef in hedefler:
            hedef_satrec = Satrec.twoline2rv(hedef["tle_line1"], hedef["tle_line2"])
            turk_norad = str(hedef.get("norad_id") or norad_from_tle_line1(hedef["tle_line1"]))

            for cop in coplar:
                cop_satrec = Satrec.twoline2rv(cop["tle_line1"], cop["tle_line2"])
                cop_norad = norad_from_tle_line1(cop["tle_line1"])

                for zaman in zaman_adimlari:
                    jd, fr = jday(
                        zaman.year,
                        zaman.month,
                        zaman.day,
                        zaman.hour,
                        zaman.minute,
                        zaman.second,
                    )
                    e_h, r_h, v_h = hedef_satrec.sgp4(jd, fr)
                    e_c, r_c, v_c = cop_satrec.sgp4(jd, fr)
                    if e_h != 0 or e_c != 0:
                        continue

                    mesafe = math.sqrt(
                        (r_h[0] - r_c[0]) ** 2
                        + (r_h[1] - r_c[1]) ** 2
                        + (r_h[2] - r_c[2]) ** 2
                    )
                    if mesafe >= mesafe_esik_km:
                        continue

                    bagil_hiz = math.sqrt(
                        (v_h[0] - v_c[0]) ** 2
                        + (v_h[1] - v_c[1]) ** 2
                        + (v_h[2] - v_c[2]) ** 2
                    )
                    olay_no += 1
                    satirlar.append(
                        {
                            "olay_id": f"RAW-{olay_no:06d}",
                            "turk_uydu_adi": hedef["name"],
                            "turk_norad_id": turk_norad,
                            "cop_parca_adi": cop.get("isim", ""),
                            "cop_norad_id": cop_norad,
                            "cop_kaynak": cop.get("kaynak", ""),
                            "yakinlasma_zamani_utc": zaman.isoformat(),
                            "mesafe_km": round(mesafe, 6),
                            "bagil_hiz_km_s": round(bagil_hiz, 6),
                            "risk_sinifi": risk_sinifi(mesafe, bagil_hiz),
                            "kayit_tipi": "ham_zaman_adimi",
                            "sim_zaman_adimi_dk": zaman_adimi_dk,
                            "sim_horizon_saat": sure_saat,
                            "mesafe_esik_km": mesafe_esik_km,
                        }
                    )
        return satirlar

    # TCA: çift başına penceredeki minimum mesafe (eşik altında en az bir an varsa)
    satirlar_tca: list[dict] = []
    olay_no = 0

    for hedef in hedefler:
        hedef_satrec = Satrec.twoline2rv(hedef["tle_line1"], hedef["tle_line2"])
        turk_norad = str(hedef.get("norad_id") or norad_from_tle_line1(hedef["tle_line1"]))

        for cop in coplar:
            cop_satrec = Satrec.twoline2rv(cop["tle_line1"], cop["tle_line2"])
            cop_norad = norad_from_tle_line1(cop["tle_line1"])

            best_m = None
            best_t = None
            best_vrel = None

            for zaman in zaman_adimlari:
                jd, fr = jday(
                    zaman.year,
                    zaman.month,
                    zaman.day,
                    zaman.hour,
                    zaman.minute,
                    zaman.second,
                )
                e_h, r_h, v_h = hedef_satrec.sgp4(jd, fr)
                e_c, r_c, v_c = cop_satrec.sgp4(jd, fr)
                if e_h != 0 or e_c != 0:
                    continue

                mesafe = math.sqrt(
                    (r_h[0] - r_c[0]) ** 2
                    + (r_h[1] - r_c[1]) ** 2
                    + (r_h[2] - r_c[2]) ** 2
                )
                if mesafe >= mesafe_esik_km:
                    continue

                bagil_hiz = math.sqrt(
                    (v_h[0] - v_c[0]) ** 2
                    + (v_h[1] - v_c[1]) ** 2
                    + (v_h[2] - v_c[2]) ** 2
                )

                if best_m is None or mesafe < best_m:
                    best_m = mesafe
                    best_t = zaman
                    best_vrel = bagil_hiz

            if best_m is not None and best_t is not None and best_vrel is not None:
                olay_no += 1
                satirlar_tca.append(
                    {
                        "olay_id": f"TCA-{olay_no:06d}",
                        "turk_uydu_adi": hedef["name"],
                        "turk_norad_id": turk_norad,
                        "cop_parca_adi": cop.get("isim", ""),
                        "cop_norad_id": cop_norad,
                        "cop_kaynak": cop.get("kaynak", ""),
                        "yakinlasma_zamani_utc": best_t.isoformat(),
                        "mesafe_km": round(best_m, 6),
                        "bagil_hiz_km_s": round(best_vrel, 6),
                        "risk_sinifi": risk_sinifi(best_m, best_vrel),
                        "kayit_tipi": "tca_pencere_minimumu",
                        "sim_zaman_adimi_dk": zaman_adimi_dk,
                        "sim_horizon_saat": sure_saat,
                        "mesafe_esik_km": mesafe_esik_km,
                    }
                )

    return satirlar_tca


def write_csv(rows: list[dict], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "olay_id",
        "turk_uydu_adi",
        "turk_norad_id",
        "cop_parca_adi",
        "cop_norad_id",
        "cop_kaynak",
        "yakinlasma_zamani_utc",
        "mesafe_km",
        "bagil_hiz_km_s",
        "risk_sinifi",
        "kayit_tipi",
        "sim_zaman_adimi_dk",
        "sim_horizon_saat",
        "mesafe_esik_km",
    ]
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(
        description="Türk uyduları ile çöp TLE'leri arasında yakınlaşmaları CSV'ye yazar."
    )
    parser.add_argument(
        "--turk-json",
        type=Path,
        default=root / "turk_uydulari.json",
        help="Türk hedef uyduları JSON (TLE)",
    )
    parser.add_argument(
        "--cop-json",
        type=Path,
        default=root / "cop_verileri.json",
        help="Çöp TLE listesi JSON",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "data" / "processed" / "turk_uydu_cop_yakinlasma_ml.csv",
        help="Çıktı CSV yolu",
    )
    parser.add_argument("--zaman-adimi-dk", type=int, default=5)
    parser.add_argument("--sure-saat", type=int, default=24)
    parser.add_argument("--mesafe-esik-km", type=float, default=50.0)
    parser.add_argument(
        "--max-debris",
        type=int,
        default=1000,
        help="İlk N çöp (hızlı deneme). Tümü için 0.",
    )
    parser.add_argument(
        "--raw-timesteps",
        action="store_true",
        help="Eşik altındaki her zaman adımını ayrı satır yaz (çoğaltılmış veri).",
    )
    args = parser.parse_args()

    turk_path = args.turk_json.resolve()
    cop_path = args.cop_json.resolve()
    out_path = args.output.resolve()

    max_debris = None if args.max_debris == 0 else args.max_debris

    print("Türk uydu × çöp yakınlaşma CSV dışa aktarımı")
    print(f"  Türk JSON: {turk_path}")
    print(f"  Çöp JSON:  {cop_path}")
    print(f"  Çıktı:     {out_path}")
    print(f"  Mod:       {'ham zaman adımı' if args.raw_timesteps else 'TCA (çift başına tek satır)'}")
    print(f"  max_debris: {max_debris if max_debris is not None else 'TÜMÜ'}")

    rows = run_encounters(
        turk_path,
        cop_path,
        zaman_adimi_dk=args.zaman_adimi_dk,
        sure_saat=args.sure_saat,
        mesafe_esik_km=args.mesafe_esik_km,
        max_debris=max_debris,
        raw_timesteps=args.raw_timesteps,
    )
    write_csv(rows, out_path)
    print(f"Bitti. {len(rows)} satır yazıldı.")


if __name__ == "__main__":
    main()
