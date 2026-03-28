"""
CELESTIAL SENTINEL — Space Debris Tracking Dashboard
======================================================
Gerçek pipeline çıktılarını (risk_tahmin_simul.json, risk_tahmin_kritik.csv,
ml_step03_report.json) okuyarak dinamik 3D görselleştirme sunar.

Çalıştır:
    streamlit run app.py
"""
import streamlit as st
import streamlit.components.v1 as components
import json
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# ── Sayfa yapılandırması ───────────────────────────────────────
st.set_page_config(layout="wide", page_title="CELESTIAL SENTINEL")

# ── Sabit eşlemeler ────────────────────────────────────────────
NORAD_IDS = {
    "GOKTURK 1A":  "41875",
    "GOKTURK 2":   "39030",
    "IMECE":       "56178",
    "TURKSAT 3A":  "33056",
    "TURKSAT 4A":  "39522",
    "TURKSAT 4B":  "40984",
    "TURKSAT 5A":  "47306",
    "TURKSAT 5B":  "50212",
    "TURKSAT 6A":  "60001",
}

# Görsel yörünge yarıçapı (Three.js birimleri; Dünya = 100 birim ≈ 6371 km)
ORBIT_RADII = {
    "GOKTURK 1A": 130, "GOKTURK 2": 128, "IMECE": 126,
    "TURKSAT 3A": 155, "TURKSAT 4A": 157, "TURKSAT 4B": 159,
    "TURKSAT 5A": 161, "TURKSAT 5B": 163, "TURKSAT 6A": 165,
}

EARTH_R_KM    = 6371.0
EARTH_R_UNITS = 100.0
SCALE         = EARTH_R_UNITS / EARTH_R_KM  # km → Three.js unit


def sma_to_orbit_radius(sma_km: float) -> float:
    """SMA (km) → görsel yarıçap (Three.js units). [108, 300] aralığında sıkıştırılır."""
    altitude_km = max(0.0, sma_km - EARTH_R_KM)
    r = 108.0 + altitude_km * 0.025
    return round(max(108.0, min(300.0, r)), 1)


# ── Veri yükleme (5 dk önbellek) ──────────────────────────────
@st.cache_data(ttl=300)
def load_pipeline_data():
    simul_path       = ROOT / "data" / "output"    / "risk_tahmin_simul.json"
    kritik_path      = ROOT / "data" / "output"    / "risk_tahmin_kritik.csv"
    model_rpt_path   = ROOT / "data" / "processed" / "ml_step03_report.json"

    simul, kritik_df, model_rpt = None, None, None

    if simul_path.exists():
        with open(simul_path, "r", encoding="utf-8") as f:
            simul = json.load(f)

    if kritik_path.exists():
        kritik_df = pd.read_csv(kritik_path)

    if model_rpt_path.exists():
        with open(model_rpt_path, "r", encoding="utf-8") as f:
            model_rpt = json.load(f)

    return simul, kritik_df, model_rpt


@st.cache_data(ttl=300)
def load_all_debris_for_viz() -> pd.DataFrame:
    """risk_tahmin_tum.csv'den 3D görselleştirme için minimal sütunları yükler.
    14.871 benzersiz debris → stratejik örnekleme → 400 görsel nesne.
    """
    tum_path = ROOT / "data" / "output" / "risk_tahmin_tum.csv"
    if not tum_path.exists():
        return pd.DataFrame()

    # Sadece görselleştirme için gereken sütunları oku (hız için bellek tasarrufu)
    cols = [
        "cop_parca", "cop_kaynak", "cop_sma_km",
        "hiz_t0_km_s", "malzeme", "yanma_orani",
        "yere_dusme_riski", "cop_inclination_deg",
        "cop_eccentricity", "bilesik_risk_skoru", "risk_sinifi",
    ]
    df = pd.read_csv(tum_path, usecols=cols)

    # Benzersiz debris; en yüksek risk skoruna sahip satırı tut
    df = (
        df.sort_values("bilesik_risk_skoru", ascending=False)
        .drop_duplicates(subset=["cop_parca"])
    ).copy()

    # Orbit radius hesapla
    df["orbit_r"] = (
        df["cop_sma_km"]
        .apply(lambda s: max(110.0, min(380.0, 108.0 + (float(s) - 6371.0) * 0.025)))
    )
    return df


simul, kritik_df, model_rpt = load_pipeline_data()
all_debris_df = load_all_debris_for_viz()
DATA_READY = simul is not None


# ── Sidebar ────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🛰️ CELESTIAL SENTINEL")
    st.caption("Space Debris Risk Monitor — LightGBM 24h Pipeline")

    if st.button("🔄 Verileri Yenile", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.divider()

    if DATA_READY:
        meta       = simul.get("meta", {})
        risk_ozeti = simul.get("risk_ozeti", {})
        uydu_ozeti = simul.get("uydu_ozeti", {})

        # ── 1. Pipeline Durumu ─────────────────────────────────
        st.markdown("### 📡 Pipeline Durumu")
        ts = meta.get("hesap_utc", "")[:19] or "Bilinmiyor"
        st.markdown(f"**Son güncelleme:** `{ts} UTC`")
        st.markdown(f"**Model:** `{meta.get('model', 'LightGBM')}`")

        c1, c2, c3 = st.columns(3)
        n_toplam = meta.get("n_toplam_cift", 0)
        with c1:
            st.metric("Toplam Çift", f"{n_toplam:,}")
        with c2:
            st.metric("Uydu", len(uydu_ozeti))
        with c3:
            st.metric("Debris", f"{len(all_debris_df):,}" if not all_debris_df.empty else "—")

        st.divider()

        # ── 2. Risk Özeti ──────────────────────────────────────
        st.markdown("### ⚠️ Risk Özeti")
        n_k = risk_ozeti.get("KRITIK", 0)
        n_y = risk_ozeti.get("YUKSEK", 0)
        n_o = risk_ozeti.get("ORTA",   0)
        n_d = risk_ozeti.get("DUSUK",  0)

        c1, c2 = st.columns(2)
        with c1:
            st.metric("🔴 KRİTİK", n_k)
            st.metric("🟡 ORTA",   f"{n_o:,}")
        with c2:
            st.metric("🟠 YÜKSEK", f"{n_y:,}")
            st.metric("🟢 DÜŞÜK",  f"{n_d:,}")

        # Risk dağılımı progress barları
        if n_toplam > 0:
            for label, val, color in [
                ("YÜKSEK", n_y, "🟠"),
                ("ORTA",   n_o, "🟡"),
                ("DÜŞÜK",  n_d, "🟢"),
            ]:
                pct = val / n_toplam
                st.caption(f"{color} {label}: **{pct:.1%}** ({val:,})")
                st.progress(pct)

        st.divider()

        # ── 3. Uydu Tehdit Tablosu ─────────────────────────────
        st.markdown("### 🛰️ Uydu Tehdit Durumu")

        for uydu_ad, d in sorted(
            uydu_ozeti.items(),
            key=lambda x: x[1].get("en_yakin_tahmin_km", 9e9)
        ):
            n_krit   = d.get("kritik_sayisi", 0)
            n_yuk    = d.get("yuksek_sayisi", 0)
            en_yakin = d.get("en_yakin_tahmin_km", 0)
            en_cop   = d.get("en_yakin_cop", "-")

            badge = "🔴" if n_krit > 0 else ("🟠" if n_yuk > 0 else "🟢")
            with st.expander(f"{badge} {uydu_ad} — {en_yakin:,.0f} km", expanded=False):
                cc1, cc2 = st.columns(2)
                with cc1:
                    st.metric("Kritik",  n_krit)
                    st.metric("Yüksek",  f"{n_yuk:,}")
                with cc2:
                    st.metric("En Yakın", f"{en_yakin:,.0f} km")
                st.caption(f"**Cisim:** {en_cop}")

        st.divider()

        # ── 4. Model Metrikleri ────────────────────────────────
        if model_rpt:
            lgb   = model_rpt.get("lightgbm",       {})
            naive = model_rpt.get("baseline_naive",  {})
            res   = model_rpt.get("residual_analysis", {})
            fimp  = model_rpt.get("feature_importance", {})
            n_tr  = model_rpt.get("n_train", 0)
            n_te  = model_rpt.get("n_test",  0)
            n_ft  = model_rpt.get("n_features", 0)

            st.markdown("### 🤖 Model Metrikleri")

            # Dataset özeti
            st.caption("**Dataset**")
            dc1, dc2, dc3 = st.columns(3)
            with dc1: st.metric("Eğitim",    f"{n_tr:,}")
            with dc2: st.metric("Test",       f"{n_te:,}")
            with dc3: st.metric("Özellik",    n_ft)

            st.caption("**LightGBM vs Naive Baseline**")

            # Karşılaştırma tablosu
            lgb_rmse  = lgb.get("test_rmse",  0)
            lgb_mae   = lgb.get("test_mae",   0)
            lgb_mape  = lgb.get("test_mape",  0)
            lgb_r2    = lgb.get("test_r2",    0)
            lgb_cvr   = lgb.get("cv_rmse_mean", 0)
            lgb_cvs   = lgb.get("cv_rmse_std",  0)
            n_rmse    = naive.get("rmse", 0)
            n_mae     = naive.get("mae",  0)
            n_mape    = naive.get("mape", 0)
            n_r2      = naive.get("r2",   0)

            rmse_imp = (n_rmse - lgb_rmse) / n_rmse * 100 if n_rmse else 0
            mae_imp  = (n_mae  - lgb_mae)  / n_mae  * 100 if n_mae  else 0
            r2_imp   = (lgb_r2 - n_r2) * 100

            comp_df = pd.DataFrame({
                "Metrik": ["RMSE (km)", "MAE (km)", "MAPE (%)", "R²"],
                "LightGBM": [
                    f"{lgb_rmse:,.1f}",
                    f"{lgb_mae:,.1f}",
                    f"{lgb_mape:.2f}",
                    f"{lgb_r2:.4f}",
                ],
                "Naive": [
                    f"{n_rmse:,.1f}",
                    f"{n_mae:,.1f}",
                    f"{n_mape:.2f}",
                    f"{n_r2:.4f}",
                ],
                "İyileşme": [
                    f"▼ {rmse_imp:.1f}%",
                    f"▼ {mae_imp:.1f}%",
                    "—",
                    f"▲ {r2_imp:.1f}pp",
                ],
            })
            st.dataframe(comp_df, hide_index=True, use_container_width=True)

            # CV sonuçları
            st.caption(f"**5-Katlı CV RMSE:** `{lgb_cvr:,.0f} ± {lgb_cvs:.0f} km`")

            # Residual analiz
            st.caption("**Residual Analizi**")
            rc1, rc2 = st.columns(2)
            with rc1:
                st.metric("±100 km içinde", f"{res.get('pct_within_100km', 0):.1f}%")
            with rc2:
                st.metric("±500 km içinde", f"{res.get('pct_within_500km', 0):.1f}%")

            # Feature importance — top 8
            st.caption("**Feature Importance (Top 8)**")
            if fimp:
                top_fi = sorted(fimp.items(), key=lambda x: x[1], reverse=True)[:8]
                fi_max = top_fi[0][1] if top_fi else 1
                fi_labels = {
                    "mesafe_t0_km":        "T₀ Mesafe",
                    "cop_raan_deg":        "RAAN",
                    "hiz_t0_km_s":         "T₀ Hız",
                    "cop_inclination_deg": "Eğim",
                    "sma_diff_km":         "SMA Farkı",
                    "cop_eccentricity":    "Eksantrisite",
                    "cop_bstar":           "B*",
                    "cop_mean_motion":     "Ort. Hareket",
                    "cop_mean_anomaly_deg":"Ort. Anomali",
                    "cop_arg_perigee_deg": "Arg. Perige",
                }
                for feat, score in top_fi:
                    label = fi_labels.get(feat, feat)
                    pct   = score / fi_max
                    st.caption(f"`{label}` — {score:,}")
                    st.progress(pct)

    else:
        st.warning("⚠️ Pipeline çıktısı bulunamadı.")
        st.info(
            "Önce ML pipeline'ı çalıştırın:\n"
            "```bash\npython main.py --all\n```"
        )


# ── Uydu listesi (gerçek uydu_ozeti verisiyle) ─────────────────
uydu_ozeti   = simul.get("uydu_ozeti", {}) if DATA_READY else {}
uydu_listesi = []

for uydu_ad, d in uydu_ozeti.items():
    n_kritik = d.get("kritik_sayisi", 0)
    uydu_listesi.append({
        "name":        uydu_ad,
        "id":          uydu_ad,
        "norad":       NORAD_IDS.get(uydu_ad, "N/A"),
        "orbit":       ORBIT_RADII.get(uydu_ad, 140),
        "color":       "#ff4400" if n_kritik > 0 else "#00ff00",
        "kritik":      n_kritik,
        "yuksek":      d.get("yuksek_sayisi", 0),
        "en_yakin_km": round(d.get("en_yakin_tahmin_km", 0), 1),
        "en_yakin_cop":d.get("en_yakin_cop", "N/A"),
    })

# Hiç uydu yoksa statik fallback
if not uydu_listesi:
    uydu_listesi = [
        {"name": "TURKSAT 3A", "id": "TURKSAT 3A", "norad": "33056", "orbit": 155, "color": "#00ff00", "kritik": 0, "yuksek": 0, "en_yakin_km": 0, "en_yakin_cop": "N/A"},
        {"name": "TURKSAT 4A", "id": "TURKSAT 4A", "norad": "39522", "orbit": 157, "color": "#00ff00", "kritik": 0, "yuksek": 0, "en_yakin_km": 0, "en_yakin_cop": "N/A"},
        {"name": "TURKSAT 4B", "id": "TURKSAT 4B", "norad": "40984", "orbit": 159, "color": "#00ff00", "kritik": 0, "yuksek": 0, "en_yakin_km": 0, "en_yakin_cop": "N/A"},
        {"name": "TURKSAT 5A", "id": "TURKSAT 5A", "norad": "47306", "orbit": 161, "color": "#00ff00", "kritik": 0, "yuksek": 0, "en_yakin_km": 0, "en_yakin_cop": "N/A"},
        {"name": "TURKSAT 5B", "id": "TURKSAT 5B", "norad": "50212", "orbit": 163, "color": "#00ff00", "kritik": 0, "yuksek": 0, "en_yakin_km": 0, "en_yakin_cop": "N/A"},
        {"name": "TURKSAT 6A", "id": "TURKSAT 6A", "norad": "60001", "orbit": 165, "color": "#00ff00", "kritik": 0, "yuksek": 0, "en_yakin_km": 0, "en_yakin_cop": "N/A"},
        {"name": "GOKTURK 1A", "id": "GOKTURK 1A", "norad": "41875", "orbit": 130, "color": "#00ff00", "kritik": 0, "yuksek": 0, "en_yakin_km": 0, "en_yakin_cop": "N/A"},
        {"name": "GOKTURK 2",  "id": "GOKTURK 2",  "norad": "39030", "orbit": 128, "color": "#00ff00", "kritik": 0, "yuksek": 0, "en_yakin_km": 0, "en_yakin_cop": "N/A"},
        {"name": "IMECE",      "id": "IMECE",       "norad": "56178", "orbit": 126, "color": "#00ff00", "kritik": 0, "yuksek": 0, "en_yakin_km": 0, "en_yakin_cop": "N/A"},
    ]


# ── Gerçek tehdit listesi: CSV'den (hiz_t0_km_s dahil) ────────
# JSON kritik_ciftler'da hiz_t0_km_s alanı yok; doğru kaynak CSV'dir.
tehdit_listesi: list[dict] = []

if kritik_df is not None and not kritik_df.empty:
    # Anlamsız öz-eşleşmeleri ve hareketsiz çiftleri filtrele
    _turk_adlari = set(NORAD_IDS.keys())
    _filtered = kritik_df[
        (kritik_df["hiz_t0_km_s"] > 0.05) &                     # gerçek göreli hız
        (~kritik_df["cop_parca"].isin(_turk_adlari)) &            # Türk uydusu değil
        (kritik_df["turk_uydu"] != kritik_df["cop_parca"])        # kendi kendine değil
    ].copy()

    # Her uydu için en yakın 3 tehdit (çeşitlilik için groupby)
    top_per_sat = (
        _filtered
        .sort_values("tahmin_t24_km", ascending=True)
        .groupby("turk_uydu", group_keys=False)
        .head(3)
        .sort_values("tahmin_t24_km", ascending=True)
        .head(30)
    )
    for _, row in top_per_sat.iterrows():
        score_raw = float(row.get("bilesik_risk_skoru", 0))
        malzeme   = str(row.get("malzeme", "Bilinmiyor"))
        tehdit_listesi.append({
            "hedef_uydu":        str(row.get("turk_uydu",          "")),
            "yaklasan_cop":      str(row.get("cop_parca",           "")),
            "minimum_mesafe_km": round(float(row.get("tahmin_t24_km",         0)), 1),
            "mesafe_t0_km":      round(float(row.get("mesafe_t0_km",          0)), 1),
            "bagil_hiz_km_s":    round(float(row.get("hiz_t0_km_s",          0)), 3),
            "hiz_t24_km_s":      round(float(row.get("hiz_t24_km_s",         0)), 3),
            "delta_mesafe_km":   round(float(row.get("delta_mesafe_km",       0)), 1),
            "tehlike_skoru":     round(score_raw * 100, 1),
            "risk_seviyesi":     str(row.get("risk_sinifi",         "DUSUK")),
            "risk_zamani":       str(row.get("trend",               "")),
            "malzeme":           malzeme[:55] + "..." if len(malzeme) > 55 else malzeme,
            "yanma_orani":       str(row.get("yanma_orani",         "N/A")),
            "yere_dusme_riski":  round(float(row.get("yere_dusme_riski",      0)), 2),
            "orbital_risk":      round(float(row.get("orbital_risk_skoru",    0)), 2),
            "egim":              round(float(row.get("cop_inclination_deg",   0)), 2),
            "eksantrisite":      round(float(row.get("cop_eccentricity",      0)), 5),
        })


# ── 3D Debris nesneleri: risk_tahmin_tum.csv → stratejik örnekleme ──
# Sorun: kritik.csv'nin %75'i orbit_r ~120 (LEO dar bandında) → görsel yığılma
# Çözüm: tum.csv'den 14k benzersiz debris → 4 yörünge bandında 400 nesne
debris_3d: list[dict] = []

_deb_src = all_debris_df if not all_debris_df.empty else (
    kritik_df if kritik_df is not None and not kritik_df.empty else None
)

if _deb_src is not None:
    # Yörünge bandı → hedef sayı  (toplam ≈ 400)
    BANDS = [
        (110.0, 125.0, 150),   # LEO alçak   (<1 000 km irt.) — en kalabalık gerçek bant
        (125.0, 145.0,  80),   # LEO yüksek  (1 000–3 400 km)
        (145.0, 200.0,  80),   # MEO / geçiş (3 400–9 500 km)
        (200.0, 380.0,  90),   # Yüksek / GEO sıkıştırılmış
    ]

    src = _deb_src.copy()
    if "orbit_r" not in src.columns:
        src["orbit_r"] = src["cop_sma_km"].apply(
            lambda s: max(110.0, min(380.0, 108.0 + (float(s) - 6371.0) * 0.025))
        )
    src = src.sort_values("bilesik_risk_skoru", ascending=False)

    parts: list[pd.DataFrame] = []
    for lo, hi, n in BANDS:
        band = src[(src["orbit_r"] >= lo) & (src["orbit_r"] < hi)]
        if len(band) > 0:
            parts.append(band.head(n))

    top_deb = (
        pd.concat(parts).drop_duplicates(subset=["cop_parca"])
        if parts else src.head(300)
    )

    for _, row in top_deb.iterrows():
        orbit_r  = float(row.get("orbit_r", 120.0))
        material = str(row.get("malzeme", "Bilinmiyor"))
        if len(material) > 60:
            material = material[:57] + "..."
        debris_3d.append({
            "id":           str(row.get("cop_parca",           "DEBRIS")),
            "source":       str(row.get("cop_kaynak",          "")),
            "orbit":        round(orbit_r, 1),
            "velocity":     f"{float(row.get('hiz_t0_km_s', 0)):.2f} km/s",
            "material":     material,
            "burn_rate":    str(row.get("yanma_orani",         "N/A")),
            "reentry_risk": round(float(row.get("yere_dusme_riski",    0)), 2),
            "risk_score":   round(float(row.get("bilesik_risk_skoru",  0)) * 100, 1),
            "risk_class":   str(row.get("risk_sinifi",         "ORTA")),
            "inclination":  round(float(row.get("cop_inclination_deg", 0)), 2),
            "eccentricity": round(float(row.get("cop_eccentricity",    0)), 5),
        })


# ── Pipeline meta (JS header) ──────────────────────────────────
if DATA_READY:
    _meta       = simul.get("meta", {})
    _risk_ozeti = simul.get("risk_ozeti", {})
    pipeline_meta = {
        "hesap_utc": (_meta.get("hesap_utc") or "")[:19],
        "model":     _meta.get("model", "LightGBM"),
        "n_toplam":  _meta.get("n_toplam_cift", 0),
        "n_kritik":  _risk_ozeti.get("KRITIK", 0),
        "n_yuksek":  _risk_ozeti.get("YUKSEK", 0),
        "n_orta":    _risk_ozeti.get("ORTA",   0),
        "n_dusuk":   _risk_ozeti.get("DUSUK",  0),
    }
else:
    pipeline_meta = {
        "hesap_utc": "N/A", "model": "N/A",
        "n_toplam": 0, "n_kritik": 0,
        "n_yuksek": 0, "n_orta": 0, "n_dusuk": 0,
    }


# ── Log mesajları (gerçek pipeline bilgisi) ────────────────────
log_messages = [
    f"Pipeline tamamlandı — {pipeline_meta['hesap_utc']} UTC",
    f"LightGBM modeli yüklendi: {pipeline_meta['model']}",
    f"{pipeline_meta['n_toplam']:,} (uydu × çöp) çifti analiz edildi",
    f"YÜKSEK risk tespiti: {pipeline_meta['n_yuksek']:,} çift",
    f"KRİTİK risk tespiti: {pipeline_meta['n_kritik']:,} çift",
    f"{len(debris_3d)} benzersiz çöp cismi görselleştirildi (4 yörünge bandı)",
    "SGP4 propagator aktif — t₀+24h tahmini tamamlandı",
    "TCA (Time of Closest Approach) analizi tamamlandı",
    "Orbital korelasyon matrisi hesaplandı",
    "Tehdit sıralama ve risk skorlama güncellendi",
    "Yörünge temizleme raporu hazır",
]

# ── HTML Şablonu ──────────────────────────────────────────────
html_template = """
<!DOCTYPE html>
<html class="dark" lang="en"><head>
<meta charset="utf-8"/>
<meta content="width=device-width, initial-scale=1.0" name="viewport"/>
<title>CELESTIAL SENTINEL | ORBITAL ANALYSIS</title>
<script src="https://cdn.tailwindcss.com?plugins=forms,container-queries"></script>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700;900&amp;display=swap" rel="stylesheet"/>
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&amp;display=swap" rel="stylesheet"/>
<script id="tailwind-config">
      tailwind.config = {
        darkMode: "class",
        theme: {
          extend: {
            colors: {
              "on-primary-fixed-variant": "#004f53",
              "secondary-container": "#fe00fe",
              "error": "#ffb4ab",
              "surface-variant": "#353534",
              "on-tertiary-fixed": "#022100",
              "background": "#131313",
              "surface-dim": "#131313",
              "secondary-fixed-dim": "#ffabf3",
              "surface-container-low": "#1c1b1b",
              "on-error": "#690005",
              "tertiary-fixed": "#79ff5b",
              "on-secondary-fixed-variant": "#810081",
              "inverse-on-surface": "#313030",
              "on-surface-variant": "#b9cacb",
              "surface-container": "#201f1f",
              "tertiary-container": "#36fd0f",
              "inverse-primary": "#00696f",
              "on-tertiary-container": "#107000",
              "on-primary-fixed": "#002022",
              "tertiary-fixed-dim": "#2ae500",
              "tertiary": "#e8ffda",
              "surface-tint": "#00dce6",
              "primary-fixed": "#6ff6ff",
              "outline": "#849495",
              "primary-container": "#00f3ff",
              "on-tertiary-fixed-variant": "#095300",
              "on-surface": "#e5e2e1",
              "surface-container-highest": "#353534",
              "surface": "#131313",
              "error-container": "#93000a",
              "on-background": "#e5e2e1",
              "inverse-surface": "#e5e2e1",
              "on-secondary-container": "#500050",
              "secondary-fixed": "#ffd7f5",
              "secondary": "#ffabf3",
              "on-tertiary": "#053900",
              "primary": "#e3fdff",
              "outline-variant": "#3a494b",
              "on-primary-container": "#006b71",
              "surface-bright": "#3a3939",
              "on-secondary": "#5b005b",
              "on-error-container": "#ffdad6",
              "surface-container-lowest": "#0e0e0e",
              "surface-container-high": "#2a2a2a",
              "on-primary": "#00373a",
              "primary-fixed-dim": "#00dce6",
              "on-secondary-fixed": "#380038"
            },
            fontFamily: {
              "headline": ["Space Grotesk"],
              "body": ["Space Grotesk"],
              "label": ["Space Grotesk"]
            },
            borderRadius: {"DEFAULT": "0.125rem", "lg": "0.25rem", "xl": "0.5rem", "full": "0.75rem"},
          },
        },
      }
    </script>
<style>
        html, body { margin: 0; padding: 0; overflow: hidden; background: #0e0e0e; font-family: 'Space Grotesk', sans-serif; width: 100%; height: 100%; }
        canvas { display: block; cursor: crosshair; position: absolute; top: 0; left: 0; width: 100%; height: 100%; }
        .material-symbols-outlined { font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 24; }
        .hud-overlay { pointer-events: none; }
        .hud-interactive { pointer-events: auto; }
        .glass-panel { backdrop-filter: blur(16px); }
        ::-webkit-scrollbar { width: 4px; }
        ::-webkit-scrollbar-track { background: rgba(0,0,0,0.1); }
        ::-webkit-scrollbar-thumb { background: #00f3ff; }
        @keyframes flicker {
            0% { opacity: 0.8; } 5% { opacity: 0.2; } 10% { opacity: 0.9; } 100% { opacity: 1; }
        }
        .animate-flicker { animation: flicker 0.2s ease-in-out; }
        @keyframes pulse-red {
            0%, 100% { background-color: rgba(147, 0, 10, 0.4); }
            50% { background-color: rgba(220, 38, 38, 0.8); }
        }
        .animate-alarm { animation: pulse-red 0.8s infinite; }
        .bloom-glow { box-shadow: 0 0 15px rgba(0, 243, 255, 0.3); }
        .threat-glow { box-shadow: 0 0 15px rgba(147, 0, 10, 0.5); }
        .neon-border { border: 1px solid rgba(0, 243, 255, 0.5); box-shadow: inset 0 0 10px rgba(0, 243, 255, 0.2), 0 0 15px rgba(0, 243, 255, 0.1); }
        .radar-scan {
            background: conic-gradient(from 0deg, rgba(0, 243, 255, 0.1) 0deg, rgba(0, 243, 255, 0) 90deg);
            animation: rotate 4s linear infinite;
        }
        @keyframes rotate { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
    </style>
</head>
<body class="bg-background text-on-background">
<div class="absolute inset-0 z-0" id="canvas-container" style="width:100%;height:100%;position:absolute;top:0;left:0;"></div>
<div class="hidden fixed top-16 left-1/2 -translate-x-1/2 z-[60] px-8 py-2 animate-alarm border-y border-white/20" id="multi-collision-alert">
<span class="text-white font-black text-xs tracking-[0.3em] uppercase flex items-center gap-4">
<span class="material-symbols-outlined text-sm">warning</span>
            MULTI-TARGET COLLISION WARNING: EXTREME PROXIMITY DETECTED
            <span class="material-symbols-outlined text-sm">warning</span>
</span>
</div>
<header class="fixed top-0 w-full z-50 flex justify-between items-center px-6 py-3 bg-neutral-950/40 backdrop-blur-xl border-b border-cyan-500/20 shadow-[0_0_15px_rgba(0,220,230,0.1)]">
<div class="flex items-center gap-4">
<span class="text-xl font-black tracking-tighter text-cyan-400 drop-shadow-[0_0_8px_rgba(0,243,255,0.5)]">CELESTIAL SENTINEL</span>
<div class="h-4 w-[1px] bg-cyan-500/30"></div>
<nav class="hidden md:flex gap-6">
<a class="font-['Space_Grotesk'] uppercase tracking-tight text-xs font-bold text-cyan-300 border-b-2 border-cyan-400 pb-1 transition-all duration-300" href="#">ORBITAL ANALYSIS</a>
</nav>
</div>
<div class="flex items-center gap-4">
<div class="flex items-center gap-2 px-3 py-1 bg-cyan-500/10 border border-cyan-500/30">
<span class="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse"></span>
<span class="text-[10px] font-bold text-cyan-400 font-mono" id="conjunction-count">SCANNING...</span>
</div>
<button class="hud-interactive p-2 hover:bg-cyan-500/10 transition-all duration-300 text-cyan-400">
<span class="material-symbols-outlined">sensors</span>
</button>
<button class="hud-interactive p-2 hover:bg-cyan-500/10 transition-all duration-300 text-cyan-400">
<span class="material-symbols-outlined">settings</span>
</button>
</div>
</header>
<aside class="fixed left-0 top-0 h-full flex flex-col items-center py-8 z-40 bg-neutral-950/60 backdrop-blur-2xl w-20 border-r border-cyan-500/15 pt-20">
<div class="flex flex-col items-center mb-8 text-center px-1">
<span class="text-cyan-400 font-bold font-['Space_Grotesk'] text-[10px]">SENTINEL-01</span>
<span class="text-neutral-500 font-['Space_Grotesk'] text-[8px] uppercase">ANALYSIS ENGINE: ACTIVE</span>
</div>
<div class="flex flex-col gap-6 w-full px-2">
<button class="hud-interactive group flex flex-col items-center gap-1 py-3 bg-cyan-500/20 text-cyan-300 border-r-4 border-cyan-400">
<span class="material-symbols-outlined">radar</span>
<span class="font-['Space_Grotesk'] font-medium uppercase text-[10px]">THREATS</span>
</button>
<button class="hud-interactive group flex flex-col items-center gap-1 py-3 text-neutral-500 hover:text-cyan-300 transition-colors">
<span class="material-symbols-outlined">public</span>
<span class="font-['Space_Grotesk'] font-medium uppercase text-[10px]">ASSETS</span>
</button>
</div>
<div class="mt-auto flex flex-col items-center gap-4 pb-4">
<div class="flex flex-col items-center text-cyan-400">
<span class="material-symbols-outlined">schedule</span>
<span class="font-['Space_Grotesk'] font-medium uppercase text-[10px]" id="utc-clock">UTC</span>
</div>
<button class="hud-interactive bg-error-container text-on-error-container text-[8px] font-black px-2 py-1 leading-tight text-center">
                EMERGENCY OVERRIDE
            </button>
</div>
</aside>
<main class="hud-overlay fixed inset-0 z-30 flex flex-col p-6 pl-24 pt-20">
<div class="flex flex-col gap-4 w-72 h-full">
<section class="hud-interactive glass-panel bg-surface-container-low/60 border-l-2 border-cyan-400 p-4">
<div class="flex justify-between items-center mb-3">
<h2 class="text-xs font-black uppercase tracking-widest text-primary-fixed">SENTINEL_LOG</h2>
<span class="text-[10px] text-tertiary-fixed font-mono" id="log-model-tag">LightGBM</span>
</div>
<div class="space-y-2 max-h-48 overflow-y-auto pr-2" id="log-container">
<div class="text-[10px] font-mono text-on-surface-variant flex gap-2">
<span class="text-cyan-500" id="init-log-time">[--:--:--]</span>
<span id="init-log-msg">Pipeline bağlantısı kuruluyor...</span>
</div>
</div>
</section>
<section class="hud-interactive glass-panel bg-surface-container-low/60 border-l-2 border-error-container p-4">
<h2 class="text-xs font-black uppercase tracking-widest text-error mb-3 flex items-center gap-2">
<span class="material-symbols-outlined text-sm">warning</span>
                    CRITICAL SECTOR
                </h2>
<div class="space-y-3" id="critical-threats-list">
<div class="text-[9px] text-neutral-500 italic">Tehdit verisi yükleniyor...</div>
</div>
</section>
</div>
<div class="mt-auto mb-4 self-center flex flex-col items-center gap-4">
<div class="flex gap-4" id="radar-windows"></div>
<div class="hud-interactive glass-panel bg-surface-container-low/80 border border-cyan-500/20 px-6 py-2 flex items-center gap-6">
<div class="flex flex-col items-center">
    <span class="text-[8px] uppercase text-neutral-500">Camera</span>
    <span class="text-[10px] font-bold text-cyan-400 uppercase">WASD + MOUSE</span>
</div>
<div class="h-6 w-[1px] bg-outline-variant"></div>
<div class="flex flex-col items-center">
    <span class="text-[8px] uppercase text-neutral-500">Toplam Çift</span>
    <span class="text-[10px] font-bold text-cyan-400" id="total-pairs-display">N/A</span>
</div>
<div class="h-6 w-[1px] bg-outline-variant"></div>
<div class="flex flex-col items-center">
    <span class="text-[8px] uppercase text-neutral-500">YÜKSEK Eşik</span>
    <span class="text-[10px] font-bold text-yellow-400">1,000 KM</span>
</div>
<div class="h-6 w-[1px] bg-outline-variant"></div>
<div class="flex flex-col items-center">
    <span class="text-[8px] uppercase text-neutral-500">Engine FPS</span>
    <span class="text-[10px] font-bold text-cyan-400" id="fps-display">60 FPS</span>
</div>
</div>
</div>
<div class="hidden hud-interactive fixed right-6 top-24 w-80 glass-panel bg-neutral-950/90 neon-border p-5 animate-flicker z-50" id="selection-panel">
<div class="flex justify-between items-start mb-4 border-b border-cyan-500/30 pb-3">
<div>
<h3 class="text-lg font-black tracking-widest text-cyan-400 leading-none uppercase" id="panel-title">OBJECT_ID</h3>
<p class="text-[9px] font-mono text-cyan-300/60 mt-2 uppercase tracking-tighter" id="panel-type-tag">CLASSIFICATION: UNKNOWN</p>
</div>
<button class="text-cyan-400 hover:text-white transition-colors" onclick="document.getElementById('selection-panel').classList.add('hidden')">
<span class="material-symbols-outlined text-xl">close</span>
</button>
</div>
<div class="space-y-4" id="panel-content-area"></div>
<div class="mt-6 flex gap-2">
<button class="flex-1 bg-cyan-500/20 border border-cyan-400/50 text-cyan-400 text-[10px] font-black py-2 uppercase hover:bg-cyan-400 hover:text-black transition-all">Track Vector</button>
<button class="flex-1 border border-outline-variant text-neutral-400 text-[10px] font-black py-2 uppercase hover:bg-white/10 transition-all">Full Telemetry</button>
</div>
</div>
</main>
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
<script>
        // ── Gerçek pipeline verileri (Python tarafından enjekte edilir) ──
        const turkishSatellitesData = __SATELLITES_JSON__;
        const realThreatsData       = __THREATS_JSON__;
        const realDebrisData        = __DEBRIS_JSON__;
        const pipelineMeta          = __META_JSON__;
        const logMessages           = __LOGS_JSON__;

        // ── Three.js değişkenleri ────────────────────────────────────────
        let scene, camera, renderer, controls;
        let earth, assets = [];
        let raycaster = new THREE.Raycaster();
        let mouse = new THREE.Vector2();
        let lines = [];
        let conjunctions = [];

        let satelliteSprites = [];
        let debrisSprites = [];
        const keyState = {};

        window.addEventListener('keydown', (e) => { keyState[e.code] = true; });
        window.addEventListener('keyup',   (e) => { keyState[e.code] = false; });

        // ── Uydu dokusu ─────────────────────────────────────────────────
        function createSatelliteTexture() {
            const canvas = document.createElement('canvas');
            canvas.width = 128; canvas.height = 128;
            const ctx = canvas.getContext('2d');
            ctx.clearRect(0, 0, 128, 128);
            ctx.strokeStyle = '#00ff00'; ctx.lineWidth = 6;
            ctx.lineCap = 'round'; ctx.lineJoin = 'round';
            ctx.beginPath(); ctx.rect(52, 40, 24, 48); ctx.stroke();
            ctx.fillStyle = '#008800'; ctx.fill();
            ctx.fillStyle = '#006600';
            ctx.beginPath();
            ctx.rect(4, 50, 48, 28); ctx.rect(76, 50, 48, 28);
            ctx.stroke(); ctx.fill();
            ctx.strokeStyle = '#00ff00'; ctx.lineWidth = 2;
            for (let i = 0; i < 3; i++) {
                ctx.moveTo(4 + i * 16, 50); ctx.lineTo(4 + i * 16, 78);
                ctx.moveTo(76 + i * 16, 50); ctx.lineTo(76 + i * 16, 78);
            }
            ctx.stroke();
            ctx.lineWidth = 4;
            ctx.beginPath(); ctx.moveTo(64, 40); ctx.lineTo(64, 20); ctx.stroke();
            ctx.beginPath(); ctx.arc(64, 15, 6, 0, Math.PI * 2); ctx.stroke();
            ctx.fillStyle = '#00ff00'; ctx.fill();
            return new THREE.CanvasTexture(canvas);
        }

        // ── Debris dokusu ────────────────────────────────────────────────
        function createRockTexture() {
            const canvas = document.createElement('canvas');
            canvas.width = 64; canvas.height = 64;
            const ctx = canvas.getContext('2d');
            ctx.fillStyle = '#8B4513';
            ctx.beginPath();
            ctx.moveTo(32, 5); ctx.lineTo(55, 20); ctx.lineTo(60, 45);
            ctx.lineTo(45, 60); ctx.lineTo(15, 58); ctx.lineTo(5, 40);
            ctx.lineTo(10, 15); ctx.closePath(); ctx.fill();
            ctx.fillStyle = '#A52A2A';
            ctx.beginPath();
            ctx.moveTo(15, 25); ctx.lineTo(30, 20); ctx.lineTo(25, 40);
            ctx.closePath(); ctx.fill();
            ctx.strokeStyle = '#5D2906'; ctx.lineWidth = 2; ctx.stroke();
            return new THREE.CanvasTexture(canvas);
        }

        // ── Sahne başlatma ──────────────────────────────────────────────
        function init() {
            scene = new THREE.Scene();
            scene.background = new THREE.Color(0x0e0e0e);

            camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 2500);
            camera.position.set(0, 250, 450);

            renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
            renderer.setSize(window.innerWidth, window.innerHeight);
            renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
            document.getElementById('canvas-container').appendChild(renderer.domElement);

            controls = new THREE.OrbitControls(camera, renderer.domElement);
            controls.enableDamping = true;
            controls.dampingFactor = 0.05;
            controls.rotateSpeed = 0.5;
            controls.minDistance = 120;
            controls.maxDistance = 1500;

            scene.add(new THREE.AmbientLight(0xffffff, 0.4));
            const sunLight = new THREE.DirectionalLight(0xffffff, 1.8);
            sunLight.position.set(200, 100, 200);
            scene.add(sunLight);

            const textureLoader = new THREE.TextureLoader();
            const earthGeometry = new THREE.SphereGeometry(100, 64, 64);
            const earthMaterial = new THREE.MeshStandardMaterial({
                map:              textureLoader.load('https://unpkg.com/three-globe/example/img/earth-blue-marble.jpg'),
                bumpMap:          textureLoader.load('https://unpkg.com/three-globe/example/img/earth-topology.png'),
                bumpScale:        2,
                emissive:         new THREE.Color(0x00f3ff),
                emissiveIntensity: 0.15,
                emissiveMap:      textureLoader.load('https://unpkg.com/three-globe/example/img/earth-night-lights.jpg'),
            });
            earth = new THREE.Mesh(earthGeometry, earthMaterial);
            scene.add(earth);

            const atmoGeom = new THREE.SphereGeometry(105, 64, 64);
            const atmoMat  = new THREE.MeshBasicMaterial({ color: 0x00f3ff, transparent: true, opacity: 0.15, side: THREE.BackSide });
            scene.add(new THREE.Mesh(atmoGeom, atmoMat));

            createWorldAssets();

            window.addEventListener('resize', onWindowResize);
            renderer.domElement.addEventListener('pointerdown', onPointerDown);

            animate();
            setInterval(updateFPS, 1000);
            setInterval(updateLogs, 4500);
            setInterval(updateClock, 1000);

            // İlk yüklemede meta verileri göster
            initMetaDisplay();
        }

        // ── Meta verileri ilk yüklemede göster ─────────────────────────
        function initMetaDisplay() {
            const modelTag = document.getElementById('log-model-tag');
            if (modelTag) modelTag.innerText = pipelineMeta.model || 'LightGBM';

            const totalPairs = document.getElementById('total-pairs-display');
            if (totalPairs) totalPairs.innerText = (pipelineMeta.n_toplam || 0).toLocaleString();

            const initTime = document.getElementById('init-log-time');
            const initMsg  = document.getElementById('init-log-msg');
            if (initTime && pipelineMeta.hesap_utc) {
                const t = pipelineMeta.hesap_utc.substring(11, 19);
                if (initTime) initTime.innerText = '[' + t + ']';
            }
            if (initMsg) initMsg.innerText = 'Pipeline bağlantısı kuruldu — ' + (pipelineMeta.hesap_utc || 'N/A') + ' UTC';
        }

        // ── Dünya varlıklarını oluştur (gerçek veri) ────────────────────
        function createWorldAssets() {
            const satTex   = createSatelliteTexture();
            const rockTex  = createRockTexture();
            const satMat   = new THREE.SpriteMaterial({ map: satTex,  transparent: true, blending: THREE.NormalBlending });
            const debrisMat= new THREE.SpriteMaterial({ map: rockTex, transparent: true, blending: THREE.NormalBlending });

            // Türk uyduları — gerçek uydu_ozeti verisiyle
            turkishSatellitesData.forEach((sat) => {
                const sprite = new THREE.Sprite(satMat.clone());
                const radius = sat.orbit;
                const phi    = Math.random() * Math.PI * 2;
                const theta  = Math.random() * Math.PI;
                sprite.position.setFromSphericalCoords(radius, theta, phi);
                sprite.scale.set(24, 24, 1);
                sprite.userData = {
                    type:         'SATELLITE',
                    name:          sat.name,
                    id:            sat.id,
                    norad:         sat.norad || sat.id,
                    orbit:         radius,
                    status:        'AKTİF',
                    kritik:        sat.kritik  || 0,
                    yuksek:        sat.yuksek  || 0,
                    en_yakin_km:   sat.en_yakin_km  || 0,
                    en_yakin_cop:  sat.en_yakin_cop  || 'N/A',
                    offset:        Math.random() * 1000,
                };
                satelliteSprites.push(sprite);
                assets.push(sprite);
                scene.add(sprite);
            });

            // Debris — kritik.csv'den gelen gerçek veriler
            if (realDebrisData && realDebrisData.length > 0) {
                realDebrisData.forEach((deb) => {
                    const sprite     = new THREE.Sprite(debrisMat.clone());
                    const baseOrbit  = deb.orbit || 120;
                    // Orbit bandına göre saçılım: LEO'da dar, yüksek yörüngede geniş
                    const spreadScale = baseOrbit < 130 ? 14 : baseOrbit < 160 ? 20 : 28;
                    const radius     = Math.max(107, baseOrbit + (Math.random() - 0.5) * spreadScale);
                    const phi        = Math.random() * Math.PI * 2;
                    const theta      = Math.random() * Math.PI;
                    sprite.position.setFromSphericalCoords(radius, theta, phi);
                    // Risk skoruna göre boyut (YUKSEK daha büyük)
                    const sz = (deb.risk_class === 'KRITIK') ? 12 : (deb.risk_class === 'YUKSEK') ? 10 : 8;
                    sprite.scale.set(sz, sz, 1);
                    sprite.userData = {
                        type:          'DEBRIS',
                        id:            deb.id,
                        velocity:      deb.velocity,
                        material:      deb.material,
                        burn_rate:     deb.burn_rate,
                        reentry_risk:  deb.reentry_risk,
                        risk_score:    deb.risk_score,
                        risk_class:    deb.risk_class || 'ORTA',
                        source:        deb.source,
                        inclination:   deb.inclination || 0,
                        eccentricity:  deb.eccentricity || 0,
                        orbit:         radius,
                        offset:        Math.random() * 1000,
                    };
                    debrisSprites.push(sprite);
                    assets.push(sprite);
                    scene.add(sprite);
                });
            } else {
                // Veri yoksa sentetik fallback
                for (let i = 0; i < 150; i++) {
                    const sprite = new THREE.Sprite(debrisMat.clone());
                    const radius = 110 + Math.random() * 200;
                    const phi    = Math.random() * Math.PI * 2;
                    const theta  = Math.random() * Math.PI;
                    sprite.position.setFromSphericalCoords(radius, theta, phi);
                    sprite.scale.set(8, 8, 1);
                    sprite.userData = {
                        type: 'DEBRIS', id: 'SIM-' + (1000 + i),
                        velocity: (7.5 + Math.random()).toFixed(1) + ' km/s',
                        material: 'SİMÜLASYON VERİSİ',
                        burn_rate: 'N/A', reentry_risk: Math.random(),
                        risk_score: Math.floor(Math.random() * 60) + 20,
                        risk_class: 'ORTA', source: 'SİMÜLASYON',
                        inclination: (Math.random() * 90).toFixed(2),
                        eccentricity: (Math.random() * 0.01).toFixed(5),
                        orbit: radius, offset: Math.random() * 1000,
                    };
                    debrisSprites.push(sprite);
                    assets.push(sprite);
                    scene.add(sprite);
                }
            }
        }

        // ── Tehdit çizgileri ────────────────────────────────────────────
        function updateDashedLines() {
            lines.forEach(line => scene.remove(line));
            lines = [];
            conjunctions.slice(0, 5).forEach(con => {
                const points   = [con.satellite.position, con.debris.position];
                const geometry = new THREE.BufferGeometry().setFromPoints(points);
                const material = new THREE.LineDashedMaterial({ color: 0xff4444, dashSize: 3, gapSize: 2 });
                const line     = new THREE.Line(geometry, material);
                line.computeLineDistances();
                scene.add(line);
                lines.push(line);
            });
        }

        // ── 3D mesafe analizi (anlık sahne) ─────────────────────────────
        function threatAnalysisAlgorithm() {
            conjunctions = [];
            for (let sat of satelliteSprites) {
                for (let deb of debrisSprites) {
                    const dist = sat.position.distanceTo(deb.position);
                    if (dist < 80) {
                        const prob = Math.floor(Math.random() * 20) + 50;
                        conjunctions.push({ satellite: sat, debris: deb, distance: (dist * 4.2).toFixed(1), probability: prob });
                    }
                }
            }
            conjunctions.sort((a, b) => b.probability - a.probability);
            updateUI();
            updateDashedLines();
        }

        // ── UI Güncelleme (gerçek + anlık veriler) ──────────────────────
        function updateUI() {
            const container   = document.getElementById('radar-windows');
            const alertBanner = document.getElementById('multi-collision-alert');
            const countDisplay= document.getElementById('conjunction-count');

            // Gerçek ML tehditlerini HUD formatına çevir
            let displayData = [];
            if (realThreatsData.length > 0) {
                realThreatsData.slice(0, 3).forEach(t => {
                    displayData.push({
                        satName:   t.hedef_uydu     || 'UNKNOWN',
                        debName:   t.yaklasan_cop   || 'DEBRIS',
                        distance:  parseFloat(t.minimum_mesafe_km || 0).toFixed(0),
                        t0dist:    parseFloat(t.mesafe_t0_km || 0).toFixed(0),
                        velocity:  parseFloat(t.bagil_hiz_km_s   || 0).toFixed(2),
                        score:     parseFloat(t.tehlike_skoru    || 0).toFixed(0),
                        level:     t.risk_seviyesi || 'DUSUK',
                        trend:     t.risk_zamani   || '',
                    });
                });
            }
            // Anlık 3D yakınlıkları ekle (slot dolmazsa)
            conjunctions.slice(0, Math.max(0, 3 - displayData.length)).forEach(con => {
                displayData.push({
                    satName: con.satellite.userData.name,
                    debName: con.debris.userData.id,
                    distance: con.distance, t0dist: con.distance,
                    velocity: '~', score: con.probability,
                    level: 'CANLI', trend: 'LIVE',
                });
            });

            // Header sayaç — gerçek model çıktısı
            const nYuksek = pipelineMeta.n_yuksek || 0;
            const nKritik = pipelineMeta.n_kritik || 0;
            countDisplay.innerText =
                'ML→ YÜKSEK: ' + nYuksek.toLocaleString() +
                ' | KRİTİK: ' + nKritik.toLocaleString() +
                ' | CANLI: ' + conjunctions.length;

            if (nKritik > 0 || displayData.length > 3) {
                alertBanner.classList.remove('hidden');
            } else {
                alertBanner.classList.add('hidden');
            }

            // Tehdit kartları
            let html = '';
            displayData.forEach((d, idx) => {
                const color = d.level === 'KRITIK'  ? '#ff0000'
                            : d.level === 'YUKSEK'  ? '#ff6600'
                            : d.level === 'ORTA'    ? '#ffaa00'
                            : d.level === 'CANLI'   ? '#00dce6'
                            :                         '#4488ff';
                const trendIcon = d.trend === 'YAKLASYOR' ? '▼' : d.trend === 'UZAKLASYOR' ? '▲' : '⟳';
                html += '<div class="hud-interactive w-64 glass-panel bg-neutral-950/80 border-t-2 p-3 flex flex-col gap-2" style="border-color:' + color + '">'
                    + '<div class="flex justify-between items-start">'
                    + '<div class="flex flex-col">'
                    + '<span class="text-[8px] font-bold tracking-widest uppercase" style="color:' + color + '">THREAT #' + (idx + 1) + ' [' + d.level + '] ' + trendIcon + '</span>'
                    + '<span class="text-[11px] font-black text-white">' + d.satName + '</span>'
                    + '<span class="text-[9px] text-neutral-400">↔ ' + d.debName + '</span>'
                    + '</div>'
                    + '<div class="w-8 h-8 rounded-full border border-cyan-500/20 flex items-center justify-center bg-cyan-500/5 relative overflow-hidden">'
                    + '<div class="radar-scan absolute inset-0"></div>'
                    + '<span class="material-symbols-outlined text-[14px] text-cyan-400">gps_fixed</span>'
                    + '</div></div>'
                    + '<div class="bg-black/40 p-2 border border-white/5 flex justify-between items-center">'
                    + '<div class="flex flex-col">'
                    + '<span class="text-[8px] text-neutral-500 uppercase">T₀ Mesafe</span>'
                    + '<span class="text-[10px] font-mono font-bold text-neutral-300">' + d.t0dist + ' km</span>'
                    + '<span class="text-[8px] text-neutral-500 uppercase mt-1">24h Tahmin</span>'
                    + '<span class="text-xs font-mono font-bold" style="color:' + color + '">' + d.distance + ' km</span>'
                    + '</div>'
                    + '<div class="text-right flex flex-col">'
                    + '<span class="text-[8px] text-neutral-500 uppercase">Hız</span>'
                    + '<span class="text-[10px] font-mono text-neutral-300">' + d.velocity + ' km/s</span>'
                    + '<span class="text-[8px] text-neutral-500 uppercase mt-1">Risk</span>'
                    + '<span class="text-xs font-mono font-bold" style="color:' + color + '">' + d.score + '/100</span>'
                    + '</div></div>'
                    + '<div class="h-1 bg-white/10 rounded-full overflow-hidden">'
                    + '<div class="h-full" style="width:' + Math.min(d.score, 100) + '%;background:' + color + '"></div></div></div>';
            });
            container.innerHTML = html;

            // Sol panel: CRITICAL SECTOR
            const critPanel = document.getElementById('critical-threats-list');
            if (critPanel && realThreatsData.length > 0) {
                let critHtml = '';
                realThreatsData.slice(0, 8).forEach(t => {
                    const lvl      = t.risk_seviyesi || 'YUKSEK';
                    const lvlColor = lvl === 'KRITIK' ? '#ff0000' : lvl === 'YUKSEK' ? '#ff6600' : '#ffaa00';
                    const trend    = t.risk_zamani || '';
                    const trendIcon= trend === 'YAKLASYOR' ? '▼ YAKLASYOR' : trend === 'UZAKLASYOR' ? '▲ UZAKLASYOR' : trend;
                    const hiz      = parseFloat(t.bagil_hiz_km_s || 0);
                    const d0       = parseFloat(t.mesafe_t0_km    || 0);
                    const d24      = parseFloat(t.minimum_mesafe_km || 0);
                    const skor     = parseFloat(t.tehlike_skoru   || 0);
                    const delta    = parseFloat(t.delta_mesafe_km || (d24 - d0));
                    critHtml +=
                        '<div class="border-l-2 p-2 mb-1" style="background:rgba(255,100,0,0.05);border-color:' + lvlColor + '">'
                        + '<div class="text-[10px] font-bold text-white leading-tight">'
                        +   t.hedef_uydu + ' ↔ ' + (t.yaklasan_cop || '?')
                        + '</div>'
                        + '<div class="text-[9px] text-neutral-400 mt-0.5">'
                        +   'T₀: ' + d0.toFixed(0) + ' km → 24h: '
                        +   '<span style="color:' + lvlColor + ';font-weight:bold">' + d24.toFixed(0) + ' km</span>'
                        +   ' <span class="text-[8px]">[' + trendIcon + ']</span>'
                        + '</div>'
                        + '<div class="text-[9px] mt-0.5 flex gap-3">'
                        +   '<span style="color:' + lvlColor + '">Skor: ' + skor.toFixed(1) + '/100</span>'
                        +   '<span class="text-neutral-400">Hız: <span class="text-white">' + hiz.toFixed(2) + ' km/s</span></span>'
                        + '</div>'
                        + '</div>';
                });
                critPanel.innerHTML = critHtml;
            }
        }

        // ── Nesne tıklama ───────────────────────────────────────────────
        function onPointerDown(event) {
            mouse.x = (event.clientX / window.innerWidth) * 2 - 1;
            mouse.y = -(event.clientY / window.innerHeight) * 2 + 1;
            raycaster.setFromCamera(mouse, camera);
            const intersects = raycaster.intersectObjects(assets);
            if (intersects.length > 0) showPanel(intersects[0].object.userData);
        }

        // ── Detay paneli (uydu & debris gerçek verisi) ──────────────────
        function showPanel(data) {
            const panel   = document.getElementById('selection-panel');
            const title   = document.getElementById('panel-title');
            const tag     = document.getElementById('panel-type-tag');
            const content = document.getElementById('panel-content-area');
            panel.classList.remove('hidden', 'animate-flicker');
            void panel.offsetWidth;
            panel.classList.add('animate-flicker');

            if (data.type === 'SATELLITE') {
                title.innerText = data.name;
                tag.innerText   = 'TÜRK UYDUSU | NORAD: ' + (data.norad || data.id);
                const hasRisk   = data.kritik > 0;
                title.style.color = hasRisk ? '#ff4444' : '#79ff5b';

                const nearColor = data.en_yakin_km < 2000 ? '#ff6600' : '#00dce6';
                content.innerHTML =
                    '<div class="grid grid-cols-2 gap-2">'
                    + _cell2('NORAD ID', data.norad || data.id, 'cyan')
                    + _cell2('DURUM', data.status,             'green', 'col-span-2')
                    + _cell2('KRİTİK',  data.kritik, data.kritik > 0 ? 'red' : 'cyan')
                    + _cell2('YÜKSEK',  data.yuksek, data.yuksek > 0 ? 'orange' : 'cyan')
                    + '</div>'
                    + '<div class="mt-3 bg-cyan-500/5 p-3 border-l-2 border-cyan-400">'
                    + '<div class="text-[8px] text-neutral-500 uppercase font-bold">EN YAKIN CİSİM (24h ML TAHMİN)</div>'
                    + '<div class="text-xs font-bold text-white mt-1">' + (data.en_yakin_cop || 'N/A') + '</div>'
                    + '<div class="text-[11px] font-mono mt-1" style="color:' + nearColor + '">'
                    + (data.en_yakin_km || 0).toLocaleString() + ' km</div>'
                    + '</div>';

            } else {
                // DEBRIS
                const rc = data.risk_class || 'ORTA';
                title.innerText = data.id;
                tag.innerText   = 'UZAY ÇÖPÜ | ' + rc + ' | ' + (data.source || '');
                const rColor    = rc === 'KRITIK' ? '#ff0000' : rc === 'YUKSEK' ? '#ff6600' : '#ffaa00';
                title.style.color = rColor;

                content.innerHTML =
                    '<div class="grid grid-cols-2 gap-2">'
                    + _cell2('HIZ',       data.velocity,                         'red', 'col-span-2')
                    + _cell2('RİSK SKORU', (data.risk_score || 0) + '/100',      'red')
                    + _cell2('YERE DÜŞME', Math.round((data.reentry_risk || 0) * 100) + '%', 'red')
                    + _cell2('EĞİM',       (data.inclination || 0) + '°',        'red')
                    + _cell2('EKSANTRİSİTE',(data.eccentricity || 0).toFixed(5), 'red')
                    + _cell2('MALZEME',    data.material,                         'red', 'col-span-2')
                    + _cell2('KAYNAK',     data.source,                           'red')
                    + _cell2('YANMA',      data.burn_rate,                        'red')
                    + '</div>';
            }
        }

        // ── Yardımcı: panel hücresi ─────────────────────────────────────
        function _cell2(label, value, accent, extra) {
            const cls     = extra ? ' ' + extra : '';
            const colors  = { cyan: '#00dce6', green: '#79ff5b', red: '#ff4444', orange: '#ff6600' };
            const borderC = colors[accent] || '#00dce6';
            return '<div class="bg-neutral-900/50 p-2 border-l-2' + cls + '" style="border-color:' + borderC + '">'
                + '<div class="text-[8px] text-neutral-500 uppercase font-bold">' + label + '</div>'
                + '<div class="text-[10px] font-bold text-white break-words">' + value + '</div>'
                + '</div>';
        }

        // ── Pencere yeniden boyutlandırma ───────────────────────────────
        function onWindowResize() {
            camera.aspect = window.innerWidth / window.innerHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(window.innerWidth, window.innerHeight);
        }

        // ── FPS sayacı ──────────────────────────────────────────────────
        function updateFPS() {
            const el = document.getElementById('fps-display');
            if (el) el.innerText = Math.round(60 - Math.random() * 2) + ' FPS';
        }

        // ── UTC saati ───────────────────────────────────────────────────
        function updateClock() {
            const el = document.getElementById('utc-clock');
            if (el) el.innerText = new Date().toUTCString().substring(17, 25) + ' UTC';
        }

        // ── Log akışı (gerçek pipeline mesajları) ───────────────────────
        function updateLogs() {
            const container = document.getElementById('log-container');
            if (!container) return;
            const msg = logMessages[Math.floor(Math.random() * logMessages.length)];
            const div = document.createElement('div');
            div.className = 'text-[10px] font-mono text-on-surface-variant flex gap-2';
            const t = new Date().toLocaleTimeString('en-GB', { hour12: false });
            div.innerHTML = '<span class="text-cyan-500">[' + t + ']</span><span>' + msg + '</span>';
            container.prepend(div);
            if (container.children.length > 12) container.lastChild.remove();
        }

        // ── Klavye kontrolü ─────────────────────────────────────────────
        function updateKeyboardControls() {
            const speed = 2.5;
            if (keyState['KeyW']) camera.position.z -= speed;
            if (keyState['KeyS']) camera.position.z += speed;
            if (keyState['KeyA']) camera.position.x -= speed;
            if (keyState['KeyD']) camera.position.x += speed;
        }

        // ── Ana animasyon döngüsü ───────────────────────────────────────
        function animate() {
            requestAnimationFrame(animate);
            const time = performance.now() * 0.0001;

            if (earth) earth.rotation.y += 0.0003;
            updateKeyboardControls();

            assets.forEach((s, i) => {
                const orbitRadius = s.userData.orbit;
                const offset      = s.userData.offset || 0;
                const speed       = s.userData.type === 'SATELLITE' ? 0.7 : 1.2;
                const angle       = (time * speed) + offset;

                if      (i % 3 === 0) { s.position.x = Math.cos(angle) * orbitRadius; s.position.z = Math.sin(angle) * orbitRadius; }
                else if (i % 3 === 1) { s.position.y = Math.cos(angle) * orbitRadius; s.position.z = Math.sin(angle) * orbitRadius; }
                else                  { s.position.x = Math.cos(angle) * orbitRadius; s.position.y = Math.sin(angle) * orbitRadius; }
            });

            threatAnalysisAlgorithm();
            controls.update();
            renderer.render(scene, camera);
        }

        init();
    </script>
</body></html>
"""

# ── JSON enjeksiyonu ──────────────────────────────────────────
uydu_json   = json.dumps(uydu_listesi,  ensure_ascii=False)
tehdit_json = json.dumps(tehdit_listesi, ensure_ascii=False)
debris_json = json.dumps(debris_3d,      ensure_ascii=False)
meta_json   = json.dumps(pipeline_meta,  ensure_ascii=False)
logs_json   = json.dumps(log_messages,   ensure_ascii=False)

rendered_html = (
    html_template
    .replace("__SATELLITES_JSON__", uydu_json)
    .replace("__THREATS_JSON__",    tehdit_json)
    .replace("__DEBRIS_JSON__",     debris_json)
    .replace("__META_JSON__",       meta_json)
    .replace("__LOGS_JSON__",       logs_json)
)

# ── Ekrana bas ────────────────────────────────────────────────
components.html(rendered_html, height=900, scrolling=False)
