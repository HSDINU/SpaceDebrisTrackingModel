"""Gürültü ve Outlier Analizi — tüm veri kaynakları."""
import numpy as np
import glob
import pandas as pd


def parse_dat(fp):
    data = []
    with open(fp) as f:
        for line in f:
            vals = line.strip().split()
            if len(vals) == 7:
                try:
                    data.append([float(v) for v in vals])
                except ValueError:
                    pass
    return np.array(data) if data else np.empty((0, 7))


# ═══════════════════════════════════════════
# 1) AÇISAL DEĞER İHLALLERİ (>360 derece)
# ═══════════════════════════════════════════
print("=" * 60)
print("1) AÇISAL DEĞER İHLALLERİ (>360 derece)")
print("=" * 60)

for label, pattern in [("DEB_TRAIN", "deb_train/*.dat"), ("DEB_TEST", "deb_test/*.dat")]:
    files = sorted(glob.glob(pattern))
    for fp in files:
        d = parse_dat(fp)
        if d.shape[0] == 0:
            continue
        raan, argp, M = d[:, 4], d[:, 5], d[:, 6]
        problems = []
        if np.any(raan > 360):
            problems.append(f"RAAN>360: {np.sum(raan > 360)} (max={raan.max():.2f})")
        if np.any(argp > 360):
            problems.append(f"ArgP>360: {np.sum(argp > 360)} (max={argp.max():.2f})")
        if np.any(M > 360):
            problems.append(f"M>360: {np.sum(M > 360)} (max={M.max():.2f})")
        if problems:
            print(f"  {fp}: {' | '.join(problems)}")


# ═══════════════════════════════════════════
# 2) ZAMAN SERİSİ SIÇRAMALARI
# ═══════════════════════════════════════════
print()
print("=" * 60)
print("2) ZAMAN SERİSİ SIÇRAMALARI")
print("=" * 60)

jump_summary = {"a_big": 0, "e_big": 0, "i_big": 0}
for fp in sorted(glob.glob("deb_train/*.dat") + glob.glob("deb_test/*.dat")):
    d = parse_dat(fp)
    if d.shape[0] < 3:
        continue
    a, e, inc = d[:, 1], d[:, 2], d[:, 3]
    for i in range(1, len(a)):
        pct_a = abs(a[i] - a[i - 1]) / a[i - 1] * 100
        if pct_a > 0.5:
            jump_summary["a_big"] += 1
            if jump_summary["a_big"] <= 5:
                print(f"  SMA jump {fp} t={d[i, 0]:.0f}: {a[i-1]:.1f} -> {a[i]:.1f} ({pct_a:.2f}%)")
        if abs(e[i] - e[i - 1]) > 0.3:
            jump_summary["e_big"] += 1
            if jump_summary["e_big"] <= 5:
                print(f"  ECC jump {fp} t={d[i, 0]:.0f}: {e[i-1]:.4f} -> {e[i]:.4f}")
        if abs(inc[i] - inc[i - 1]) > 10:
            jump_summary["i_big"] += 1
            if jump_summary["i_big"] <= 5:
                print(f"  INC jump {fp} t={d[i, 0]:.0f}: {inc[i-1]:.2f} -> {inc[i]:.2f}")

print(f"\nToplam SMA >0.5% sıçrama: {jump_summary['a_big']}")
print(f"Toplam ECC >0.3 sıçrama: {jump_summary['e_big']}")
print(f"Toplam INC >10° sıçrama: {jump_summary['i_big']}")


# ═══════════════════════════════════════════
# 3) COP_VERİLERİ ENRICHED GÜRÜLTÜ
# ═══════════════════════════════════════════
print()
print("=" * 60)
print("3) cop_verileri_enriched.csv GÜRÜLTÜ ANALİZİ")
print("=" * 60)

df = pd.read_csv("data/processed/cop_verileri_enriched.csv", encoding="utf-8-sig")
print(f"Toplam satır: {len(df):,}")

check_cols = [
    "inclination_deg", "eccentricity", "semi_major_axis_km",
    "perigee_alt_km", "apogee_alt_km", "bstar_drag",
    "raan_deg", "arg_perigee_deg", "mean_anomaly_deg",
    "mean_motion_rev_day", "period_hours",
]

for col in check_cols:
    if col not in df.columns:
        continue
    s = df[col].dropna()
    q1, q3 = s.quantile([0.25, 0.75])
    iqr = q3 - q1
    low, high = q1 - 3 * iqr, q3 + 3 * iqr
    outliers = ((s < low) | (s > high)).sum()
    negatives = (s < 0).sum()
    print(f"  {col:<25s}  outlier_3IQR={outliers:5d}  neg={negatives:4d}  "
          f"min={s.min():.4f}  max={s.max():.4f}  mean={s.mean():.4f}")


# ═══════════════════════════════════════════
# 4) FİZİKSEL SINIR KONTROLLARI
# ═══════════════════════════════════════════
print()
print("=" * 60)
print("4) FİZİKSEL SINIR KONTROLLARI (cop_verileri_enriched)")
print("=" * 60)

if "eccentricity" in df.columns:
    bad_ecc = ((df["eccentricity"] < 0) | (df["eccentricity"] >= 1)).sum()
    print(f"  Eksantrisite [0,1) dışı: {bad_ecc}")
if "inclination_deg" in df.columns:
    bad_inc = ((df["inclination_deg"] < 0) | (df["inclination_deg"] > 180)).sum()
    print(f"  Eğim [0,180] dışı: {bad_inc}")
if "perigee_alt_km" in df.columns:
    neg_per = (df["perigee_alt_km"] < 0).sum()
    print(f"  Negatif perigee: {neg_per} (re-entry yörüngesi olabilir)")
if "semi_major_axis_km" in df.columns:
    bad_sma = (df["semi_major_axis_km"] < 6371).sum()
    print(f"  SMA < R_Earth: {bad_sma}")
if "period_hours" in df.columns:
    bad_period = (df["period_hours"] < 0.5).sum()
    print(f"  Periyot < 30 dk: {bad_period}")

# Açısal sütunlar [0, 360] kontrolü
for col in ["raan_deg", "arg_perigee_deg", "mean_anomaly_deg"]:
    if col in df.columns:
        bad = ((df[col] < 0) | (df[col] > 360)).sum()
        print(f"  {col} [0,360] dışı: {bad}")


# ═══════════════════════════════════════════
# 5) YAKINLAŞMA VERİSİ GÜRÜLTÜ
# ═══════════════════════════════════════════
print()
print("=" * 60)
print("5) turk_uydu_cop_yakinlasma_ml.csv GÜRÜLTÜ ANALİZİ")
print("=" * 60)

enc = pd.read_csv("data/processed/turk_uydu_cop_yakinlasma_ml.csv",
                   encoding="utf-8-sig")
print(f"Toplam satır: {len(enc):,}")
print(f"NaN satır sayısı: {enc.isna().any(axis=1).sum():,}")

for col in enc.select_dtypes(include=[np.number]).columns:
    s = enc[col].dropna()
    if len(s) == 0:
        continue
    q1, q3 = s.quantile([0.25, 0.75])
    iqr = q3 - q1
    if iqr == 0:
        continue
    low, high = q1 - 3 * iqr, q3 + 3 * iqr
    outliers = ((s < low) | (s > high)).sum()
    if outliers > 0:
        print(f"  {col:<30s}  outlier_3IQR={outliers:6d}  ({100*outliers/len(s):.1f}%)")


# ═══════════════════════════════════════════
# 6) SHAPIRO-WILK NORMALLIK TESTİ (sample)
# ═══════════════════════════════════════════
print()
print("=" * 60)
print("6) SHAPIRO-WILK NORMALLIK TESTİ (enriched, sample=5000)")
print("=" * 60)

from scipy import stats

for col in ["inclination_deg", "eccentricity", "semi_major_axis_km",
            "perigee_alt_km", "bstar_drag"]:
    if col not in df.columns:
        continue
    s = df[col].dropna()
    sample = s.sample(min(5000, len(s)), random_state=42)
    stat, p = stats.shapiro(sample)
    skew = s.skew()
    kurt = s.kurtosis()
    normal = "Normal" if p > 0.05 else "Non-Normal"
    print(f"  {col:<25s}  W={stat:.4f}  p={p:.2e}  skew={skew:.2f}  "
          f"kurt={kurt:.2f}  -> {normal}")
