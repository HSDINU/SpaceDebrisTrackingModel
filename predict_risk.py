"""
Model Tahmin Çıktısı — Simülasyon için JSON/CSV
=================================================
Eğitilmiş LightGBM modeliyle tüm (Türk uydu, çöp) çiftleri için
t+24h mesafe tahmini yapar ve risk sınıflandırması uygular.

Risk sıralama:
  KRITIK  : tahmin_mesafe_t24 < 1000 km
  YUKSEK  : 1000 km — 5000 km
  ORTA    : 5000 km — 15000 km
  DUSUK   : > 15000 km

Çıktılar:
  data/output/risk_tahmin_tum.csv         — tüm çiftler
  data/output/risk_tahmin_kritik.csv      — kritik + yüksek risk
  data/output/risk_tahmin_simul.json      — arayüz için JSON

Çalıştırma:
  python predict_risk.py
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from ml_pipeline.model_artifact import load_predictor
from ml_pipeline.feature_profiles import CORE_ONLY, get_profile_spec, normalize_profile

ROOT = Path(__file__).resolve().parent
FEAT_PATH = ROOT / "data" / "processed" / "ml_features_24h.csv"
ENC_PATH = ROOT / "data" / "processed" / "encounters_24h.csv"

OUT_DIR = ROOT / "data" / "output"
OUT_DIR.mkdir(parents=True, exist_ok=True)

TARGET = "mesafe_t24_km"

# Risk eşikleri (km)
RISK_THRESHOLDS = {
    "KRITIK": 1_000,
    "YUKSEK": 5_000,
    "ORTA": 15_000,
    "DUSUK": float("inf"),
}

RISK_ORDER = {"KRITIK": 0, "YUKSEK": 1, "ORTA": 2, "DUSUK": 3}

# ── Malzeme Veritabanı (NASA/ESA verilerine dayalı) ─────────────
# Yeniden eğitime GEREK YOK — bu tamamen post-prediction lookup join
# cop_kaynak sütunuyla eşleştiriliyor
MALZEME_DB: dict[str, dict] = {
    "cosmos_1408_copleri": {
        "ana_govde": "Tselina-D Casus Uydusu",
        "olasi_malzeme": "Ağır Alüminyum İskelet, Titanyum Batarya Hücreleri",
        "atmosferde_yanma_orani": "%75",
        "yere_dusme_riski_skoru": 0.80,
    },
    "fengyun_1c_copleri": {
        "ana_govde": "FY-1C Meteoroloji Uydusu",
        "olasi_malzeme": "Hafif Karbon Kompozit, Silikon Güneş Panelleri, Alüminyum",
        "atmosferde_yanma_orani": "%95",
        "yere_dusme_riski_skoru": 0.30,
    },
    "iridium_33_copleri": {
        "ana_govde": "Iridium Haberleşme Uydusu",
        "olasi_malzeme": "Kevlar Kaplama, Titanyum Yakıt Tankları (Hydrazine)",
        "atmosferde_yanma_orani": "%80",
        "yere_dusme_riski_skoru": 0.60,
    },
    "cosmos_2251_copleri": {
        "ana_govde": "Strela-2M Askeri Haberleşme Uydusu",
        "olasi_malzeme": "Alüminyum Alaşım, Çelik Reaksiyon Çarkları",
        "atmosferde_yanma_orani": "%85",
        "yere_dusme_riski_skoru": 0.50,
    },
    # R/B (Roket Gövdesi) — genel: devasa titanyum/çelik motor blokları
    # isimde 'R/B' geçenlere otomatik uygulanır (aşağıdaki is_roket_govdesi)
    "roket_govdesi": {
        "ana_govde": "Roket Üst Kademesi (Rocket Body)",
        "olasi_malzeme": "Titanyum Motor Bloğu, Çelik Yakıt Tankı",
        "atmosferde_yanma_orani": "%30",
        "yere_dusme_riski_skoru": 0.95,  # EN TEHLİKELİ
    },
    # Bilinmeyen — muhafazakâr varsayılan
    "_varsayilan": {
        "ana_govde": "Bilinmiyor",
        "olasi_malzeme": "Karma Malzeme (tahmin edilemiyor)",
        "atmosferde_yanma_orani": "%70",
        "yere_dusme_riski_skoru": 0.40,
    },
}

# Orbital risk skoru → mesafe bandına göre 0–1 (ters: yakın = yüksek)
ORBITAL_RISK_BAND: list[tuple[float, float]] = [
    (1_000,  1.00),   # < 1k km  → 1.00
    (5_000,  0.80),   # < 5k km  → 0.80
    (15_000, 0.50),   # < 15k km → 0.50
    (float("inf"), 0.15),  # uzak    → 0.15
]


def orbital_risk_skoru(dist_km: float) -> float:
    for esik, skor in ORBITAL_RISK_BAND:
        if dist_km < esik:
            return skor
    return 0.15


import re as _re

_RB_PATTERN = _re.compile(r"\bR/B\b|ROCKET\s+BODY", _re.IGNORECASE)


def malzeme_bilgisi(cop_isim: str, cop_kaynak: str) -> dict:
    """cop_isim ve cop_kaynak'a göre malzeme verisini döndür.

    R/B tespiti: Yalnızca 'R/B' (slash ile, kelime sınırlı) veya
    'ROCKET BODY' içeren isimler. 'RB' substring KULLANILMAZ —
    ORBCOMM gibi isimlerde false positive üretiyor.
    """
    # Önce R/B tespiti (roket gövdesi — en tehlikeli)
    if _RB_PATTERN.search(str(cop_isim)):
        return MALZEME_DB["roket_govdesi"]
    # Sonra kaynak eşleştirmesi
    kaynak = str(cop_kaynak).lower().strip()
    return MALZEME_DB.get(kaynak, MALZEME_DB["_varsayilan"])




def risk_sinifi(dist_km: float) -> str:
    for sinif, esik in RISK_THRESHOLDS.items():
        if dist_km < esik:
            return sinif
    return "DUSUK"


def merge_discos_from_cleaned(out: pd.DataFrame, root: Path) -> pd.DataFrame:
    """cop_verileri_cleaned_discos.csv ile isim+kaynak üzerinden DISCOS alanları."""
    p = root / "data" / "processed" / "cop_verileri_cleaned_discos.csv"
    if not p.exists():
        return out
    try:
        cd = pd.read_csv(p, encoding="utf-8-sig")
    except OSError:
        return out
    if "isim" not in cd.columns or "kaynak" not in cd.columns:
        return out
    want = [
        "isim",
        "kaynak",
        "norad_id",
        "discos_object_class",
        "discos_mission",
        "discos_mass_kg",
        "discos_shape",
    ]
    take = [c for c in want if c in cd.columns]
    lu = cd[take].drop_duplicates(subset=["isim", "kaynak"], keep="first")
    merged = out.merge(
        lu,
        left_on=["cop_parca", "cop_kaynak"],
        right_on=["isim", "kaynak"],
        how="left",
    )
    drop_me = [c for c in ("isim", "kaynak") if c in merged.columns]
    if drop_me:
        merged = merged.drop(columns=drop_me)
    if "norad_id" in merged.columns:
        merged = merged.rename(columns={"norad_id": "cop_norad_id"})
    return merged


def main() -> int:
    ap = argparse.ArgumentParser(description="Risk tahmini (profile-aware)")
    ap.add_argument(
        "--profile",
        default=CORE_ONLY,
        help="Feature profile: core_only | core_plus_discos | core_plus_discos_physical",
    )
    ap.add_argument(
        "--orbital-weight",
        type=float,
        default=1.0,
        help="Orbital risk ağırlığı (bilesik_risk_skoru için)",
    )
    ap.add_argument(
        "--material-weight",
        type=float,
        default=1.0,
        help="Malzeme/yere düşme risk ağırlığı (bilesik_risk_skoru için)",
    )
    args = ap.parse_args()
    requested_profile = normalize_profile(args.profile)
    _ = get_profile_spec(requested_profile)
    orbital_w = max(0.05, float(args.orbital_weight))
    material_w = max(0.05, float(args.material_weight))

    print("=" * 65)
    print("🛰️  Risk Tahmin Motoru — Simülasyon Çıktısı")
    print("=" * 65)
    print(f"İstenen profile: {requested_profile}")
    print(f"Risk ağırlıkları: orbital={orbital_w:.2f} | material={material_w:.2f}")

    # --- Model yükle ---
    selected_profile = requested_profile
    model_path = ROOT / f"lightgbm_risk_modeli__{selected_profile}.pkl"
    report_path = ROOT / "data" / "processed" / f"ml_step03_report__{selected_profile}.json"
    if not model_path.exists() and requested_profile != CORE_ONLY:
        print(f"UYARI: {requested_profile} modeli yok, core_only fallback kullanılacak.")
        selected_profile = CORE_ONLY
        model_path = ROOT / f"lightgbm_risk_modeli__{selected_profile}.pkl"
        report_path = ROOT / "data" / "processed" / f"ml_step03_report__{selected_profile}.json"
    if not model_path.exists() and selected_profile == CORE_ONLY:
        legacy = ROOT / "lightgbm_risk_modeli.pkl"
        if legacy.exists():
            model_path = legacy
            report_path = ROOT / "data" / "processed" / "ml_step03_report.json"
    if not model_path.exists():
        print(f"HATA: Model bulunamadı → {model_path}")
        print("Önce: python -m ml_pipeline.step03_train_baseline --profile <profile>")
        return 1
    model, feature_cols = load_predictor(model_path, report_path)
    print(f"Aktif profile: {selected_profile}")

    # --- Feature ve encounter verileri ---
    if not FEAT_PATH.exists() or not ENC_PATH.exists():
        print("HATA: Feature / encounter dosyası eksik.")
        return 1

    feat_df = pd.read_csv(FEAT_PATH, encoding="utf-8-sig")
    enc_df = pd.read_csv(ENC_PATH, encoding="utf-8-sig")

    missing = [c for c in feature_cols if c not in feat_df.columns]
    if missing:
        print("HATA: Modelin beklediği sütunlar feature CSV'de yok:")
        print(f"  {missing[:25]}{'…' if len(missing) > 25 else ''}")
        print("Önce: python -m ml_pipeline.step02_build_features && python -m ml_pipeline.step03_train_baseline")
        return 1
    X = feat_df[feature_cols].astype(float)

    print(f"Feature sayısı (eğitimle aynı sıra): {len(feature_cols)}")
    print(f"Toplam çift   : {len(feat_df):,}")

    # --- Tahmin ---
    print("\nTahmin yapılıyor...")
    tahmin_t24 = model.predict(X)

    # --- Çıktı DataFrame ---
    out = pd.DataFrame()
    out["turk_uydu"]          = enc_df["turk_uydu"]
    out["cop_parca"]          = enc_df.get("cop_isim", pd.Series(["BILINMIYOR"] * len(enc_df))).fillna("BILINMIYOR")
    out["cop_kaynak"]         = enc_df.get("cop_kaynak", pd.Series([""] * len(enc_df))).fillna("")

    # Gerçek t0/t24 değerleri
    out["mesafe_t0_km"]       = feat_df["mesafe_t0_km"].round(2)
    out["hiz_t0_km_s"]        = feat_df["hiz_t0_km_s"].round(3)
    out["tahmin_t24_km"]      = np.round(tahmin_t24, 2)

    # Gerçek t24 (varsa)
    if TARGET in feat_df.columns:
        out["gercek_t24_km"]  = feat_df[TARGET].round(2)
        out["hata_km"]        = (out["gercek_t24_km"] - out["tahmin_t24_km"]).round(2)
    if "hiz_t24_km_s" in enc_df.columns:
        out["hiz_t24_km_s"]   = enc_df["hiz_t24_km_s"].round(3)
    if "delta_mesafe_km" in enc_df.columns:
        out["delta_mesafe_km"] = enc_df["delta_mesafe_km"].round(2)

    # Yörünge bilgileri (görselleştirme için)
    for col in ["cop_inclination_deg", "cop_eccentricity",
                "cop_sma_km", "cop_perigee_km", "cop_apogee_km"]:
        if col in feat_df.columns:
            out[col] = feat_df[col].round(4)

    # Malzeme riski (post-prediction lookup — model yeniden eğitilmez)
    print("Malzeme riski entegre ediliyor...")
    malzeme_rows = [
        malzeme_bilgisi(row["cop_parca"], row["cop_kaynak"])
        for _, row in out[["cop_parca", "cop_kaynak"]].iterrows()
    ]
    out["roket_govdesi"]         = [str(r["ana_govde"]).startswith("Roket") for r in malzeme_rows]
    out["malzeme"]               = [r["olasi_malzeme"] for r in malzeme_rows]
    out["yanma_orani"]           = [r["atmosferde_yanma_orani"] for r in malzeme_rows]
    out["yere_dusme_riski"]      = [r["yere_dusme_riski_skoru"] for r in malzeme_rows]

    # Bileşik risk skoru = ağırlıklı ortalama (orbital vs material)
    # Yorumlama: 1.0 = maksimum tehlike, 0.0 = minimum
    out["orbital_risk_skoru"]    = [orbital_risk_skoru(d) for d in tahmin_t24]
    out["bilesik_risk_skoru"]    = (
        (orbital_w * out["orbital_risk_skoru"] + material_w * out["yere_dusme_riski"])
        / (orbital_w + material_w)
    ).round(4)

    out = merge_discos_from_cleaned(out, ROOT)

    # Risk sınıfı
    out["risk_sinifi"]        = [risk_sinifi(d) for d in tahmin_t24]
    out["risk_order"]         = out["risk_sinifi"].map(RISK_ORDER)

    # Trend: yaklaşıyor mu uzaklaşıyor mu?
    out["trend"] = np.where(
        tahmin_t24 < feat_df["mesafe_t0_km"].values,
        "YAKLASYOR", "UZAKLASYOR"
    )

    # Zaman damgası
    now = datetime.now(timezone.utc).isoformat()
    out["hesap_utc"] = now

    # Sıralama: risk order → bileşik skor (desc) → tahmin mesafe
    out = out.sort_values(
        ["risk_order", "bilesik_risk_skoru", "tahmin_t24_km"],
        ascending=[True, False, True]
    ).reset_index(drop=True)
    out = out.drop(columns=["risk_order"])


    # --- Tüm çiftler CSV ---
    all_csv = OUT_DIR / "risk_tahmin_tum.csv"
    out.to_csv(all_csv, index=False, encoding="utf-8-sig")
    print(f"\n✅ Tüm çiftler → {all_csv} ({len(out):,} satır)")

    # --- Kritik + Yüksek risk CSV ---
    kritik_df = out[out["risk_sinifi"].isin(["KRITIK", "YUKSEK"])].copy()
    kritik_csv = OUT_DIR / "risk_tahmin_kritik.csv"
    kritik_df.to_csv(kritik_csv, index=False, encoding="utf-8-sig")
    print(f"✅ Kritik+Yüksek → {kritik_csv} ({len(kritik_df):,} çift)")

    # --- Risk dağılımı ---
    print(f"\n{'─' * 65}")
    print("RİSK DAĞILIMI")
    print(f"{'─' * 65}")
    dist = out["risk_sinifi"].value_counts().reindex(
        ["KRITIK", "YUKSEK", "ORTA", "DUSUK"], fill_value=0
    )
    for sinif, count in dist.items():
        bar = "█" * min(40, int(40 * count / len(out)))
        esik = {"KRITIK": "<1,000 km", "YUKSEK": "1k-5k km",
                "ORTA": "5k-15k km", "DUSUK": ">15k km"}[sinif]
        print(f"  {sinif:<8}({esik:<12}) {count:>7,}  ({100*count/len(out):>5.1f}%)  {bar}")

    # --- Uydu bazlı özet ---
    print(f"\n{'─' * 65}")
    print("UYDU BAZLI ÖZET")
    print(f"{'─' * 65}")
    for uydu, grp in out.groupby("turk_uydu"):
        k = (grp["risk_sinifi"] == "KRITIK").sum()
        y = (grp["risk_sinifi"] == "YUKSEK").sum()
        en_yakin = grp["tahmin_t24_km"].min()
        en_yakin_cop = grp.loc[grp["tahmin_t24_km"].idxmin(), "cop_parca"]
        print(f"  {uydu:<16}  KRİTİK={k:4d}  YÜKSEK={y:4d}  "
              f"En yakın: {en_yakin:>8,.1f} km  ← {en_yakin_cop}")

    # --- En riskli 20 çift (bileşik skora göre) ---
    print(f"\n{'─' * 75}")
    print("EN RİSKLİ 20 ÇİFT — Bileşik Skor (Orbital × Malzeme)")
    print(f"{'─' * 75}")
    print(f"  {'UYDU':<14} {'ÇÖP':<26} {'t24(km)':>8} {'ORB':>5} {'MAL':>5} {'BILESIK':>8} {'R/B':>4}")
    print(f"  {'─' * 75}")
    for _, row in out.head(20).iterrows():
        cop_short = str(row["cop_parca"])[:24]
        rb_flag = "R/B" if row["roket_govdesi"] else "   "
        trend_icon = "↓" if row["trend"] == "YAKLASYOR" else "↑"
        print(f"  {str(row['turk_uydu']):<14} {cop_short:<26} "
              f"{row['tahmin_t24_km']:>8,.0f} "
              f"{row['orbital_risk_skoru']:>5.2f} "
              f"{row['yere_dusme_riski']:>5.2f} "
              f"{row['bilesik_risk_skoru']:>8.4f} "
              f"{rb_flag} {trend_icon}")


    # --- Simülasyon JSON ---
    simul_data = {
        "meta": {
            "hesap_utc": now,
            "model": "LightGBM 24h Mesafe Tahmini",
            "n_toplam_cift": int(len(out)),
            "data_profile": requested_profile,
            "feature_profile": selected_profile,
            "risk_weights": {
                "orbital": round(orbital_w, 4),
                "material": round(material_w, 4),
            },
        },
        "risk_ozeti": {
            sinif: int(dist.get(sinif, 0))
            for sinif in ["KRITIK", "YUKSEK", "ORTA", "DUSUK"]
        },
        "uydu_ozeti": {},
        "kritik_ciftler": [],
    }

    # Uydu özeti
    for uydu, grp in out.groupby("turk_uydu"):
        en_yakin_row = grp.loc[grp["tahmin_t24_km"].idxmin()]
        simul_data["uydu_ozeti"][uydu] = {
            "kritik_sayisi": int((grp["risk_sinifi"] == "KRITIK").sum()),
            "yuksek_sayisi": int((grp["risk_sinifi"] == "YUKSEK").sum()),
            "orta_sayisi": int((grp["risk_sinifi"] == "ORTA").sum()),
            "en_yakin_tahmin_km": float(round(grp["tahmin_t24_km"].min(), 2)),
            "en_yakin_gercek_km": float(round(grp["mesafe_t0_km"].min(), 2)),
            "en_yakin_cop": str(en_yakin_row["cop_parca"]),
        }

    # Kritik çiftler (tam liste) — malzeme bilgisi dahil
    for _, row in kritik_df.iterrows():
        entry = {
            "turk_uydu": str(row["turk_uydu"]),
            "cop_parca": str(row["cop_parca"]),
            "mesafe_t0_km": float(row["mesafe_t0_km"]),
            "tahmin_t24_km": float(row["tahmin_t24_km"]),
            "trend": str(row["trend"]),
            "risk_sinifi": str(row["risk_sinifi"]),
            # Malzeme
            "roket_govdesi": bool(row["roket_govdesi"]),
            "malzeme": str(row["malzeme"]),
            "yanma_orani": str(row["yanma_orani"]),
            "yere_dusme_riski": float(row["yere_dusme_riski"]),
            "orbital_risk_skoru": float(row["orbital_risk_skoru"]),
            "bilesik_risk_skoru": float(row["bilesik_risk_skoru"]),
        }
        if "gercek_t24_km" in row:
            entry["gercek_t24_km"] = float(row["gercek_t24_km"])
        if "cop_inclination_deg" in row:
            entry["cop_inclination_deg"] = float(row["cop_inclination_deg"])
        if "cop_eccentricity" in row:
            entry["cop_eccentricity"] = float(row["cop_eccentricity"])
        for col in (
            "cop_norad_id",
            "discos_object_class",
            "discos_mission",
            "discos_mass_kg",
            "discos_shape",
        ):
            if col not in row.index:
                continue
            v = row[col]
            if pd.isna(v):
                continue
            if col == "cop_norad_id":
                try:
                    entry[col] = int(v)
                except (ValueError, TypeError):
                    entry[col] = str(v)
            elif col == "discos_mass_kg":
                try:
                    entry[col] = float(v)
                except (ValueError, TypeError):
                    entry[col] = str(v)
            else:
                entry[col] = str(v)
        simul_data["kritik_ciftler"].append(entry)


    simul_json = OUT_DIR / "risk_tahmin_simul.json"
    with open(simul_json, "w", encoding="utf-8") as f:
        json.dump(simul_data, f, ensure_ascii=False, indent=2)
    print(f"\n✅ Simülasyon JSON → {simul_json}")

    # --- Model bilgisi ---
    if report_path.exists():
        with open(report_path, encoding="utf-8") as f:
            rpt = json.load(f)
        lgb = rpt.get("lightgbm", {})
        print(f"\n{'─' * 65}")
        print(f"Model bilgisi: test RMSE={lgb.get('test_rmse')} km | "
              f"R²={lgb.get('test_r2')} | "
              f"CV RMSE={lgb.get('cv_rmse_mean')} ± {lgb.get('cv_rmse_std')} km")

    print(f"\n{'=' * 65}")
    print("TAMAMLANDI.")
    print(f"  📁 {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
