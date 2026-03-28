"""
Çarpışma Rotası Doğrulama + TCA Hesabı
=======================================
Mevcut pipeline'ın eksikliğini doğrular:
  - Sadece t0 ve t24 snapshot'u alıyor
  - t=0..24h arasındaki MINIMUM mesafeyi (TCA) bulmuyordu

Bu script:
1. Mevcut data ile ne hesaplandığını gösterir
2. Seçili YÜKSEK RİSK çiftleri için gerçek TCA hesaplar (SGP4 multi-point)
3. Sonuçları karşılaştırır

Çıktı: data/output/tca_validation.csv
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sgp4.api import Satrec, jday

ROOT = Path(__file__).resolve().parent.parent
RISK_CSV = ROOT / "data" / "output" / "risk_tahmin_kritik.csv"
TLE_JSON = ROOT / "cop_verileri.json"
TURK_JSON = ROOT / "turk_uydulari.json"
OUT_DIR = ROOT / "data" / "output"
OUT_DIR.mkdir(parents=True, exist_ok=True)

DELTA_HOURS = 24
# TCA için zaman resolution (dakika) — her N dakikada bir mesafe hesapla
TCA_STEP_MINUTES = 10

R_EARTH = 6371.0


def sgp4_pos(satrec: Satrec, t: datetime):
    jd, fr = jday(t.year, t.month, t.day, t.hour, t.minute, t.second + t.microsecond / 1e6)
    e, r, v = satrec.sgp4(jd, fr)
    return np.array(r), np.array(v), e


def build_satrec_map(tle_list: list) -> dict:
    """isim → Satrec eşlemesi."""
    mp = {}
    for obj in tle_list:
        l1 = obj.get("tle_line1", "")
        l2 = obj.get("tle_line2", "")
        isim = obj.get("isim", "")
        if l1 and l2 and isim:
            try:
                mp[isim] = Satrec.twoline2rv(l1, l2)
            except Exception:
                pass
    return mp


def tca_search(satrec_sat: Satrec, satrec_cop: Satrec, t0: datetime,
               step_min: int = TCA_STEP_MINUTES, window_h: int = DELTA_HOURS):
    """
    t0'dan window_h saat sonrasına kadar step_min dakika adımlarıyla
    minimum yaklaşma mesafesini ve zamanını bulur.
    
    Dönüş:
      tca_time: datetime — en yakın geçiş zamanı
      tca_dist: float   — minimum mesafe (km)
      t0_dist : float   — t0 anındaki mesafe
      t24_dist: float   — t24 anındaki mesafe
      distances: list   — tüm mesafeler (grafik için)
    """
    n_steps = int(window_h * 60 / step_min) + 1
    times = [t0 + timedelta(minutes=i * step_min) for i in range(n_steps)]
    distances = []
    errors = 0

    for t in times:
        r_sat, _, e_sat = sgp4_pos(satrec_sat, t)
        r_cop, _, e_cop = sgp4_pos(satrec_cop, t)
        if e_sat != 0 or e_cop != 0:
            errors += 1
            distances.append(np.nan)
            continue
        distances.append(float(np.linalg.norm(r_sat - r_cop)))

    dists = np.array(distances)
    valid = ~np.isnan(dists)
    if not np.any(valid):
        return None, np.nan, np.nan, np.nan, []

    min_idx = np.nanargmin(dists)
    return (
        times[min_idx],             # tca_time
        float(dists[min_idx]),      # tca_dist
        float(dists[0]),            # t0_dist
        float(dists[-1]),           # t24_dist
        distances,                  # full time series
    )


def main() -> int:
    print("=" * 65)
    print("ÇARPIŞMA ROTASI DOĞRULAMA — TCA (Time of Closest Approach)")
    print("=" * 65)

    # --- 1. Mevcut pipeline ne yapıyor? ---
    print("\n--- MEVCUT PİPELİNE ANALİZİ ---")
    print("Mevcut build_real_encounters.py:")
    print("  ✓ t0 mesafesi      : SGP4(t=şimdi) → |r_sat - r_cop|")
    print("  ✓ t24 mesafesi     : SGP4(t=+24h)  → |r_sat - r_cop|")
    print("  ✗ TCA (minimum)    : HESAPLANMIYOR")
    print("  ✗ TCA zamanı       : HESAPLANMIYOR")
    print("  ✗ Çarpışma olasılığı: HESAPLANMIYOR")
    print("\n  → Model t0 ve t24 snapshot'unu kullanıyor.")
    print("  → Eğer iki nesne t0–t24 ARASINDA yaklaşıp uzaklaşıyorsa")
    print("    bu geçiş artık KALIP BİLİNMİYOR.")
    print("  → TCA hesabı bu eksiği kapatır.\n")

    # --- 2. Kritik çiftleri yükle ---
    if not RISK_CSV.exists():
        print(f"HATA: {RISK_CSV} bulunamadı — önce predict_risk.py çalıştırın")
        return 1

    risk_df = pd.read_csv(RISK_CSV, encoding="utf-8-sig")
    print(f"Yüksek risk çifti: {len(risk_df):,}")

    # En yakın 30 çifti seç (TCA hesabı yavaş)
    top_n = risk_df.sort_values("tahmin_t24_km").head(30)
    print(f"TCA hesaplanacak : {len(top_n)} çift (en riskli)")

    # --- 3. TLE'leri yükle ---
    with open(TLE_JSON, encoding="utf-8") as f:
        cop_tle_list = json.load(f)
    with open(TURK_JSON, encoding="utf-8") as f:
        turk_tle_list = json.load(f)

    cop_satrec = build_satrec_map(cop_tle_list)
    turk_satrec = {t["name"]: Satrec.twoline2rv(t["tle_line1"], t["tle_line2"])
                   for t in turk_tle_list
                   if t.get("tle_line1") and t.get("tle_line2")}

    t0 = datetime.now(timezone.utc)
    print(f"\nt0 = {t0.isoformat()}")
    print(f"Adım = {TCA_STEP_MINUTES} dakika | Pencere = {DELTA_HOURS} saat")
    print(f"({DELTA_HOURS*60//TCA_STEP_MINUTES + 1} zaman noktası / çift)\n")

    # --- 4. TCA hesapla ---
    results = []
    not_found = 0

    print(f"{'UYDU':<16} {'ÇÖP':<28} {'t0(km)':>8} {'t24(km)':>8} {'TCA(km)':>8} {'TCA_t':>12} {'FARK':>8}")
    print("-" * 90)

    for _, row in top_n.iterrows():
        uydu_adi = row["turk_uydu"]
        cop_adi = row["cop_parca"]

        if uydu_adi not in turk_satrec or cop_adi not in cop_satrec:
            not_found += 1
            continue

        tca_time, tca_dist, t0_dist_actual, t24_dist_actual, _ = tca_search(
            turk_satrec[uydu_adi], cop_satrec[cop_adi], t0
        )

        if tca_time is None:
            not_found += 1
            continue

        snapshot_min = min(t0_dist_actual, t24_dist_actual)
        tca_improvement = snapshot_min - tca_dist  # pozitif → TCA daha yakın

        tca_hour = (tca_time - t0).total_seconds() / 3600

        results.append({
            "turk_uydu": uydu_adi,
            "cop_parca": cop_adi,
            "mesafe_t0_km": round(t0_dist_actual, 2),
            "mesafe_t24_km": round(t24_dist_actual, 2),
            "snapshot_min_km": round(snapshot_min, 2),
            "tca_mesafe_km": round(tca_dist, 2),
            "tca_saat": round(tca_hour, 2),
            "tca_zaman_utc": tca_time.isoformat(),
            "snapshot_vs_tca_fark_km": round(tca_improvement, 2),
            "snapshot_tca_yakalamiyor": tca_improvement > 100,
        })

        flag = "⚠️ YAKALAMIYOR" if tca_improvement > 100 else "OK"
        cop_short = cop_adi[:26]
        print(f"  {uydu_adi:<14} {cop_short:<28} "
              f"{t0_dist_actual:>8.1f} {t24_dist_actual:>8.1f} "
              f"{tca_dist:>8.1f} {tca_hour:>10.1f}h {flag}")

    if not results:
        print("Hiç eşleşme bulunamadı (cop_isim TLE listesiyle eşleşmedi)")
        return 1

    # --- 5. Özet ---
    df_out = pd.DataFrame(results)
    out_csv = OUT_DIR / "tca_validation.csv"
    df_out.to_csv(out_csv, index=False, encoding="utf-8-sig")

    n_missed = df_out["snapshot_tca_yakalamiyor"].sum()
    print(f"\n{'=' * 65}")
    print("TCA DOĞRULAMA SONUÇLARI")
    print(f"{'=' * 65}")
    print(f"Hesaplanan çift    : {len(df_out)}")
    print(f"Snapshot yeterli   : {len(df_out) - n_missed}")
    print(f"Snapshot kaçırıyor : {n_missed} (TCA > 100 km daha yakın)")
    print()
    print(f"TCA mesafe (min)   : {df_out['tca_mesafe_km'].min():.1f} km")
    print(f"TCA mesafe (ortalama): {df_out['tca_mesafe_km'].mean():.1f} km")
    print(f"TCA saat (ortalama): {df_out['tca_saat'].mean():.1f} saat sonra")
    print()

    if n_missed > 0:
        print("⚠️  BULGU: Bazı çiftlerin gerçek TCA'sı snapshot'tan DAHA YAKIN")
        print("   → build_real_encounters.py güncellenmeli: TCA dahil edilmeli")
        missed = df_out[df_out["snapshot_tca_yakalamiyor"]]
        for _, r in missed.iterrows():
            print(f"   {r['turk_uydu']} ↔ {r['cop_parca']}: "
                  f"snapshot={r['snapshot_min_km']:.0f}km → TCA={r['tca_mesafe_km']:.0f}km "
                  f"(t+{r['tca_saat']:.1f}h)")
    else:
        print("✅ Snapshot yeterli: t0 ve t24 mesafeleri TCA'yı yakalıyor")
        print("   (10 dakika çözünürlükte TCA ile snapshot farkı <100 km)")

    print(f"\nDetaylı çıktı: {out_csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
