"""
Model Çıktıları Görselleştirme
==============================
1. QQ Plot   — Rezidüellerin normallik testi
2. Distribution Shift — Train vs Test dağılımı
3. Predicted vs Actual
4. Risk sınıfı dağılımı (uydu bazlı)
5. Feature importance

Çalıştırma:
  python ml_pipeline/visualize_results.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import joblib
import matplotlib
matplotlib.use("Agg")  # GUI olmadan kaydet
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.model_selection import train_test_split

ROOT = Path(__file__).resolve().parent.parent
FEAT_PATH = ROOT / "data" / "processed" / "ml_features_24h.csv"
ENC_PATH = ROOT / "data" / "processed" / "encounters_24h.csv"
MODEL_PATH = ROOT / "lightgbm_risk_modeli.pkl"
OUT_DIR = ROOT / "data" / "output" / "plots"
OUT_DIR.mkdir(parents=True, exist_ok=True)

TARGET = "mesafe_t24_km"
STRING_COLS = {"turk_uydu", "hiz_t24_km_s", "delta_mesafe_km", "cop_isim", "cop_kaynak", TARGET}

PLT_STYLE = {
    "figure.facecolor": "#0d1117",
    "axes.facecolor": "#161b22",
    "axes.edgecolor": "#30363d",
    "axes.labelcolor": "#e6edf3",
    "text.color": "#e6edf3",
    "xtick.color": "#8b949e",
    "ytick.color": "#8b949e",
    "grid.color": "#21262d",
    "grid.linewidth": 0.6,
    "font.family": "DejaVu Sans",
}
plt.rcParams.update(PLT_STYLE)

ACCENT   = "#58a6ff"   # mavi
ACCENT2  = "#f78166"   # kırmızı
ACCENT3  = "#3fb950"   # yeşil
ACCENT4  = "#d2a8ff"   # mor
WARN     = "#ffa657"   # turuncu


def load_data():
    df = pd.read_csv(FEAT_PATH, encoding="utf-8-sig")
    enc = pd.read_csv(ENC_PATH, encoding="utf-8-sig")
    feature_cols = [c for c in df.columns if c not in STRING_COLS]
    X = df[feature_cols].astype(float)
    y = df[TARGET].astype(float)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    model = joblib.load(MODEL_PATH)
    y_pred = model.predict(X_test)
    residuals = y_test.values - y_pred
    turk_uydu_test = enc["turk_uydu"].iloc[X_test.index].values if "turk_uydu" in enc.columns else None
    return X_train, X_test, y_train, y_test, y_pred, residuals, model, feature_cols, turk_uydu_test


# ═══════════════════════════════════════════════════════
# 1. QQ Plot + Rezidüel Dağılımı
# ═══════════════════════════════════════════════════════
def plot_qq_residuals(residuals: np.ndarray):
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle("QQ Plot & Rezidüel Dağılımı — 24h Mesafe Tahmin Hatası",
                 color="#e6edf3", fontsize=14, fontweight="bold", y=1.02)

    # QQ Plot
    ax = axes[0]
    sample = np.random.RandomState(42).choice(residuals, min(5000, len(residuals)), replace=False)
    (osm, osr), (slope, intercept, r) = stats.probplot(sample, dist="norm")
    ax.scatter(osm, osr, color=ACCENT, s=4, alpha=0.5, label="Rezidüeller")
    fit_line = np.array([osm[0], osm[-1]]) * slope + intercept
    ax.plot([osm[0], osm[-1]], fit_line, color=ACCENT2, linewidth=2, label=f"Normal fit (r={r:.4f})")
    ax.axhline(0, color="#30363d", linewidth=0.5)

    # Sapma bölgelerini vurgula
    tail_mask = (osm < -3) | (osm > 3)
    ax.scatter(osm[tail_mask], osr[tail_mask], color=WARN, s=12, zorder=5, label="Kuyruk sapmaları")

    ax.set_xlabel("Teorik Normal Quantile'lar")
    ax.set_ylabel("Gözlemlenen Rezidüeller (km)")
    ax.set_title("QQ Plot (Normal Karşılaştırması)", color="#e6edf3", pad=8)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    # Yorumlama kutusu
    _, sw_p = stats.shapiro(sample)
    skew = float(stats.skew(residuals))
    kurt = float(stats.kurtosis(residuals))
    bbox = dict(boxstyle="round,pad=0.4", facecolor="#1c2128", edgecolor="#30363d")
    interp = (
        f"Shapiro-Wilk p = {sw_p:.2e}\n"
        f"Çarpıklık (skew) = {skew:.3f}\n"
        f"Basıklık (kurt)  = {kurt:.3f}\n\n"
        "Non-normal → kalın kuyruklar\n(kaçınma manevraları gibi\nuç olaylar normal dağılımı\nbozuyor)"
    )
    ax.text(0.04, 0.97, interp, transform=ax.transAxes, fontsize=8,
            verticalalignment="top", bbox=bbox, color="#8b949e")

    # Rezidüel histogram
    ax = axes[1]
    clip = np.percentile(np.abs(residuals), 99)
    r_clipped = residuals[np.abs(residuals) <= clip]
    n_bins = 80
    ax.hist(r_clipped, bins=n_bins, color=ACCENT, alpha=0.75, density=True,
            label=f"Rezidüeller (99. pct: ±{clip:.0f} km)")

    # Normal fit overlay
    mu, sigma = residuals.mean(), residuals.std()
    x_norm = np.linspace(r_clipped.min(), r_clipped.max(), 300)
    ax.plot(x_norm, stats.norm.pdf(x_norm, mu, sigma), color=ACCENT2, linewidth=2,
            label=f"Normal(μ={mu:.0f}, σ={sigma:.0f})")

    ax.axvline(0, color=ACCENT3, linewidth=1.5, linestyle="--", label="Sıfır hata")
    ax.axvline(mu, color=WARN, linewidth=1.5, linestyle=":", label=f"Ortalama={mu:.0f} km")

    # ±2σ bölge
    ax.axvspan(-2*sigma, 2*sigma, alpha=0.08, color=ACCENT3, label=f"±2σ = ±{2*sigma:.0f} km")

    ax.set_xlabel("Rezidüel (km) — Gerçek − Tahmin")
    ax.set_ylabel("Yoğunluk")
    ax.set_title("Rezidüel Dağılımı (Normal ile Kıyaslama)", color="#e6edf3", pad=8)
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    out = OUT_DIR / "01_qq_residuals.png"
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()
    print(f"  ✅ {out.name}")
    return out


# ═══════════════════════════════════════════════════════
# 2. Distribution Shift — Train vs Test
# ═══════════════════════════════════════════════════════
def plot_distribution_shift(X_train: pd.DataFrame, X_test: pd.DataFrame,
                             y_train: pd.Series, y_test: pd.Series):
    key_features = [
        "mesafe_t0_km", "hiz_t0_km_s",
        "cop_inclination_deg", "cop_eccentricity",
        "perigee_diff_km", "sma_diff_km",
    ]
    key_features = [f for f in key_features if f in X_train.columns]

    fig, axes = plt.subplots(3, 3, figsize=(18, 14))
    fig.suptitle("Distribution Shift — Eğitim vs Test Seti",
                 color="#e6edf3", fontsize=14, fontweight="bold")

    plot_cols = key_features + [TARGET]
    for i, col in enumerate(plot_cols[:9]):
        ax = axes[i // 3][i % 3]
        if col == TARGET:
            train_data = y_train.values
            test_data = y_test.values
        else:
            train_data = X_train[col].values
            test_data = X_test[col].values

        # Ortak clip (aşırı uçları gösterme)
        p1, p99 = np.percentile(np.concatenate([train_data, test_data]), [1, 99])
        train_c = train_data[(train_data >= p1) & (train_data <= p99)]
        test_c = test_data[(test_data >= p1) & (test_data <= p99)]

        bins = np.linspace(p1, p99, 50)
        ax.hist(train_c, bins=bins, density=True, alpha=0.6, color=ACCENT,
                label=f"Train (n={len(X_train):,})")
        ax.hist(test_c, bins=bins, density=True, alpha=0.6, color=ACCENT2,
                label=f"Test (n={len(X_test):,})")

        # KS test
        ks_stat, ks_p = stats.ks_2samp(train_data, test_data)
        shift_label = "✅ Stabil" if ks_p > 0.05 else "⚠️ Drift"
        color_label = ACCENT3 if ks_p > 0.05 else WARN

        ax.set_title(col, color="#e6edf3", fontsize=9, pad=4)
        ax.text(0.98, 0.97, f"KS={ks_stat:.3f}\n{shift_label}",
                transform=ax.transAxes, ha="right", va="top",
                fontsize=8, color=color_label,
                bbox=dict(boxstyle="round,pad=0.3", facecolor="#1c2128", edgecolor="#30363d"))
        ax.legend(fontsize=7, loc="upper left")
        ax.grid(True, alpha=0.3)

    # Boş hücreleri gizle
    for j in range(len(plot_cols), 9):
        axes[j // 3][j % 3].set_visible(False)

    plt.tight_layout()
    out = OUT_DIR / "02_distribution_shift.png"
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()
    print(f"  ✅ {out.name}")
    return out


# ═══════════════════════════════════════════════════════
# 3. Predicted vs Actual
# ═══════════════════════════════════════════════════════
def plot_predicted_vs_actual(y_test: pd.Series, y_pred: np.ndarray):
    fig, axes = plt.subplots(1, 2, figsize=(16, 7))
    fig.suptitle("Predicted vs Actual — 24h Mesafe Tahmini",
                 color="#e6edf3", fontsize=14, fontweight="bold")

    # Scatter
    ax = axes[0]
    # Yoğunluk rengi için 2D histogram kullan
    from matplotlib.colors import LogNorm
    h, xedges, yedges = np.histogram2d(y_test.values, y_pred, bins=100)
    # Her noktayı yoğunluğuna göre renklendir
    xidx = np.clip(np.searchsorted(xedges, y_test.values) - 1, 0, h.shape[0]-1)
    yidx = np.clip(np.searchsorted(yedges, y_pred) - 1, 0, h.shape[1]-1)
    density = h[xidx, yidx]

    sc = ax.scatter(y_test.values, y_pred, c=density, cmap="plasma",
                    s=2, alpha=0.4, norm=LogNorm())
    plt.colorbar(sc, ax=ax, label="Nokta Yoğunluğu (log)")

    # Perfect prediction line
    max_val = min(y_test.max(), y_pred.max(), 80_000)
    ax.plot([0, max_val], [0, max_val], color=ACCENT3, linewidth=2,
            linestyle="--", label="Mükemmel Tahmin")

    # ±20% band
    ax.fill_between([0, max_val], [0, max_val*0.8], [0, max_val*1.2],
                    alpha=0.1, color=ACCENT3, label="±20% Band")

    from sklearn.metrics import r2_score, mean_squared_error
    r2 = r2_score(y_test, y_pred)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    ax.text(0.04, 0.97, f"R² = {r2:.6f}\nRMSE = {rmse:.0f} km",
            transform=ax.transAxes, va="top", fontsize=10, color=ACCENT3,
            bbox=dict(boxstyle="round,pad=0.4", facecolor="#1c2128", edgecolor="#30363d"))

    ax.set_xlabel("Gerçek Mesafe t+24h (km)")
    ax.set_ylabel("Tahmin Edilen Mesafe t+24h (km)")
    ax.set_title("Predicted vs Actual (renk = yoğunluk)", color="#e6edf3", pad=8)
    ax.set_xlim(0, max_val)
    ax.set_ylim(0, max_val)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    # Hata segmenti analizi
    ax = axes[1]
    bins = [0, 1000, 5000, 15000, 30000, 60000, 200000]
    bin_labels = ["<1k", "1k-5k", "5k-15k", "15k-30k", "30k-60k", ">60k"]
    bin_idx = np.digitize(y_test.values, bins) - 1
    bin_idx = np.clip(bin_idx, 0, len(bin_labels) - 1)

    rmse_per_bin = []
    mape_per_bin = []
    cnt_per_bin = []
    for b in range(len(bin_labels)):
        mask = bin_idx == b
        cnt_per_bin.append(mask.sum())
        if mask.sum() > 0:
            rmse_per_bin.append(np.sqrt(mean_squared_error(y_test.values[mask], y_pred[mask])))
            mape_per_bin.append(np.mean(np.abs((y_test.values[mask] - y_pred[mask]) /
                                               np.maximum(y_test.values[mask], 1)) * 100))
        else:
            rmse_per_bin.append(0)
            mape_per_bin.append(0)

    x = np.arange(len(bin_labels))
    w = 0.35
    bars1 = ax.bar(x - w/2, rmse_per_bin, w, color=ACCENT, alpha=0.8, label="RMSE (km)")
    ax2 = ax.twinx()
    bars2 = ax2.bar(x + w/2, mape_per_bin, w, color=ACCENT2, alpha=0.8, label="MAPE (%)")

    ax.set_xticks(x)
    ax.set_xticklabels(bin_labels)
    ax.set_xlabel("Gerçek Mesafe Aralığı")
    ax.set_ylabel("RMSE (km)", color=ACCENT)
    ax2.set_ylabel("MAPE (%)", color=ACCENT2)
    ax.set_title("Mesafe Aralığına Göre Hata Dağılımı", color="#e6edf3", pad=8)
    ax2.yaxis.label.set_color(ACCENT2)
    ax2.tick_params(axis="y", colors=ACCENT2)

    # Örnek sayısı etiketleri
    for b, (bar, n) in enumerate(zip(bars1, cnt_per_bin)):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 50,
                f"n={n:,}", ha="center", va="bottom", fontsize=7, color="#8b949e")

    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labels1 + labels2, fontsize=9)
    ax.grid(True, alpha=0.3)
    ax2.set_facecolor("none")

    plt.tight_layout()
    out = OUT_DIR / "03_predicted_vs_actual.png"
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()
    print(f"  ✅ {out.name}")
    return out


# ═══════════════════════════════════════════════════════
# 4. Feature Importance
# ═══════════════════════════════════════════════════════
def plot_feature_importance(model, feature_cols: list[str]):
    fig, ax = plt.subplots(figsize=(12, 8))
    fig.suptitle("LightGBM Feature Importance (Gain)",
                 color="#e6edf3", fontsize=14, fontweight="bold")

    imp = model.feature_importances_
    imp_df = pd.DataFrame({"feature": feature_cols, "importance": imp})
    imp_df = imp_df.sort_values("importance", ascending=True).tail(20)

    total = imp_df["importance"].sum()
    colors = [ACCENT if v > total * 0.05 else ACCENT4 for v in imp_df["importance"]]

    bars = ax.barh(imp_df["feature"], imp_df["importance"], color=colors, alpha=0.85)

    for bar, val in zip(bars, imp_df["importance"]):
        pct = val / total * 100
        ax.text(bar.get_width() + total * 0.001, bar.get_y() + bar.get_height()/2,
                f"{pct:.1f}%", va="center", fontsize=8, color="#8b949e")

    ax.set_xlabel("Importance Score (Gain)")
    ax.set_title("En Önemli 20 Feature", color="#8b949e", fontsize=11, pad=6)
    ax.grid(True, alpha=0.3, axis="x")

    # Legend
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor=ACCENT, label=">5% katkı — kritik feature"),
        Patch(facecolor=ACCENT4, label="<5% katkı — düşük öncelik"),
    ]
    ax.legend(handles=legend_elements, fontsize=9)

    plt.tight_layout()
    out = OUT_DIR / "04_feature_importance.png"
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()
    print(f"  ✅ {out.name}")
    return out


# ═══════════════════════════════════════════════════════
# 5. Risk sınıfı — uydu bazlı
# ═══════════════════════════════════════════════════════
def plot_risk_by_satellite():
    risk_csv = ROOT / "data" / "output" / "risk_tahmin_tum.csv"
    if not risk_csv.exists():
        print("  ⚠️  risk_tahmin_tum.csv bulunamadı — önce predict_risk.py çalıştırın")
        return

    df = pd.read_csv(risk_csv, encoding="utf-8-sig")
    satellites = sorted(df["turk_uydu"].unique())
    risk_levels = ["KRITIK", "YUKSEK", "ORTA", "DUSUK"]
    colors_risk = {"KRITIK": ACCENT2, "YUKSEK": WARN, "ORTA": ACCENT4, "DUSUK": ACCENT3}

    fig, axes = plt.subplots(1, 2, figsize=(18, 8))
    fig.suptitle("Uydu Bazlı Risk Dağılımı — Model Çıktısı (t+24h)",
                 color="#e6edf3", fontsize=14, fontweight="bold")

    # Stacked bar chart
    ax = axes[0]
    risk_counts = {}
    for lv in risk_levels:
        risk_counts[lv] = [
            (df[df["turk_uydu"] == s]["risk_sinifi"] == lv).sum()
            for s in satellites
        ]

    bottom = np.zeros(len(satellites))
    for lv in risk_levels:
        ax.bar(satellites, risk_counts[lv], bottom=bottom,
               color=colors_risk[lv], alpha=0.85, label=lv)
        bottom += np.array(risk_counts[lv])

    ax.set_xlabel("Türk Uyduları")
    ax.set_ylabel("Çöp Çifti Sayısı")
    ax.set_title("Risk Seviyesi Dağılımı (Uydu Bazlı)", color="#e6edf3", pad=8)
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3, axis="y")
    plt.setp(ax.get_xticklabels(), rotation=20, ha="right", fontsize=9)

    # En yakın 10 tehdit (box plot per satellite)
    ax = axes[1]
    data_for_box = []
    labels_for_box = []
    for s in satellites:
        sat_df = df[df["turk_uydu"] == s]
        # Sadece YUKSEK ve ORTA
        close = sat_df[sat_df["tahmin_t24_km"] < 20_000]["tahmin_t24_km"].values
        if len(close) > 0:
            data_for_box.append(close)
            labels_for_box.append(s)

    bp = ax.boxplot(data_for_box, patch_artist=True, vert=True,
                    medianprops=dict(color=ACCENT3, linewidth=2))
    for patch in bp["boxes"]:
        patch.set_facecolor(ACCENT)
        patch.set_alpha(0.5)
    for element in ["whiskers", "caps", "fliers"]:
        for item in bp[element]:
            item.set_color("#30363d")

    ax.axhline(5_000, color=WARN, linewidth=1.5, linestyle="--", label="5,000 km eşiği")
    ax.axhline(1_000, color=ACCENT2, linewidth=1.5, linestyle="--", label="1,000 km (KRİTİK)")
    ax.set_xticks(range(1, len(labels_for_box) + 1))
    ax.set_xticklabels(labels_for_box, rotation=20, ha="right", fontsize=9)
    ax.set_ylabel("Tahmin Mesafesi t+24h (km)")
    ax.set_title("Yakın Geçiş Dağılımı (<20k km)", color="#e6edf3", pad=8)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3, axis="y")

    plt.tight_layout()
    out = OUT_DIR / "05_risk_by_satellite.png"
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()
    print(f"  ✅ {out.name}")
    return out


# ═══════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════
def main():
    print("=" * 60)
    print("🔬 Model Görselleştirme — QQ + Distribution Shift")
    print("=" * 60)

    if not FEAT_PATH.exists() or not MODEL_PATH.exists():
        print("HATA: Feature CSV veya model dosyası eksik.")
        return 1

    print("\nVeri ve model yükleniyor...")
    X_train, X_test, y_train, y_test, y_pred, residuals, model, feature_cols, _ = load_data()
    print(f"Train: {len(X_train):,} | Test: {len(X_test):,} | Feature: {len(feature_cols)}")

    print(f"\nGrafikler oluşturuluyor → {OUT_DIR}")
    plot_qq_residuals(residuals)
    plot_distribution_shift(X_train, X_test, y_train, y_test)
    plot_predicted_vs_actual(y_test, y_pred)
    plot_feature_importance(model, feature_cols)
    plot_risk_by_satellite()

    print(f"\n{'=' * 60}")
    print(f"Tüm grafikler: {OUT_DIR}")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
