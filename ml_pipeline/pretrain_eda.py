"""
Eğitim öncesi doğrulama — train/test ayrıldıktan sonra, istatistikler yalnızca eğitim kümesi
üzerinden (hedef sızıntısı yok). Test tarafında yalnızca marjinal dağılım karşılaştırması
(KS) kullanılır; test hedefi kullanılmaz.

Çıktı: data/processed/ml_pretrain_eda_report.json

step03_train_baseline tarafından otomatik çağrılır.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats


def _sample_series(s: pd.Series, *, max_n: int, random_state: int) -> pd.Series:
    s = s.dropna()
    if len(s) <= max_n:
        return s
    return s.sample(max_n, random_state=random_state)


def run_eda_after_split(
    X_train: pd.DataFrame,
    X_test: pd.DataFrame,
    y_train: pd.Series,
    feature_cols: list[str],
    split_meta: dict[str, Any],
    out_path: Path,
    *,
    ks_max_n: int = 8000,
    shapiro_max_n: int = 5000,
    random_state: int = 42,
) -> dict[str, Any]:
    """Train-only özet + train/test KS (kovaryat kayması)."""
    cols = [c for c in feature_cols if c in X_train.columns and c in X_test.columns]
    train_miss = {c: float(X_train[c].isna().mean()) for c in cols}
    test_miss = {c: float(X_test[c].isna().mean()) for c in cols}

    train_var = X_train[cols].var(numeric_only=True, skipna=True)
    low_var = [c for c in cols if c in train_var.index and pd.notna(train_var[c]) and float(train_var[c]) <= 1e-12]

    spearman: dict[str, float] = {}
    for c in cols:
        pair = pd.concat([X_train[c], y_train], axis=1).dropna()
        if len(pair) < 10:
            continue
        r, _ = stats.spearmanr(pair.iloc[:, 0], pair.iloc[:, 1])
        if np.isfinite(r):
            spearman[c] = round(float(r), 4)

    ks_results: dict[str, Any] = {}
    for c in cols:
        a = _sample_series(X_train[c], max_n=ks_max_n, random_state=random_state)
        b = _sample_series(X_test[c], max_n=ks_max_n, random_state=random_state + 1)
        if len(a) < 30 or len(b) < 30:
            continue
        stat, pval = stats.ks_2samp(a.values, b.values, method="auto")
        ks_results[c] = {"statistic": round(float(stat), 6), "pvalue": round(float(pval), 8)}

    y_s = _sample_series(y_train, max_n=shapiro_max_n, random_state=random_state)
    shapiro_note = None
    if len(y_s) >= 8:
        # Shapiro üst sınır 5000 örnek
        ys = y_s.values
        if len(ys) > 5000:
            ys = ys[:5000]
        w, p = stats.shapiro(ys)
        shapiro_note = {"W": round(float(w), 6), "pvalue": round(float(p), 8), "n": int(len(ys))}

    report: dict[str, Any] = {
        "split": split_meta,
        "n_train": int(len(X_train)),
        "n_test": int(len(X_test)),
        "n_features": len(cols),
        "train_missing_frac": {k: round(v, 6) for k, v in train_miss.items() if v > 0},
        "test_missing_frac": {k: round(v, 6) for k, v in test_miss.items() if v > 0},
        "near_constant_train_cols": low_var,
        "spearman_with_target_train": dict(sorted(spearman.items(), key=lambda x: abs(x[1]), reverse=True)[:40]),
        "ks_train_vs_test_marginals": ks_results,
        "target_shapiro_train_sample": shapiro_note,
        "notes": [
            "Spearman ve Shapiro yalnızca eğitim kümesinde hesaplanır.",
            "KS testi özellik marjinallerini karşılaştırır; test etiketi kullanılmaz.",
        ],
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n{'─' * 60}")
    print("ÖN-EĞİTİM EDA (train-only + KS marjinaller)")
    print(f"{'─' * 60}")
    print(f"  Rapor: {out_path}")
    if low_var:
        print(f"  UYARI: Train’de ~sabit sütunlar: {low_var[:8]}{'...' if len(low_var) > 8 else ''}")
    high_shift = [(k, v["pvalue"]) for k, v in ks_results.items() if v["pvalue"] < 0.01]
    if high_shift:
        top = sorted(high_shift, key=lambda x: x[1])[:5]
        print(f"  KS p<0.01 (olası dağılım farkı, ilk 5): {top}")
    else:
        print("  KS: p<0.01 ayırt edici marjinal fark (ilk kontrol) yok.")
    return report


def main() -> int:
    """Tek başına: ml_features_24h.csv üzerinde split + EDA (model yok)."""
    from ml_pipeline.training.training_split import TARGET, replicate_training_split

    root = Path(__file__).resolve().parent.parent
    feat_path = root / "data" / "processed" / "ml_features_24h.csv"
    out_path = root / "data" / "processed" / "ml_pretrain_eda_report.json"
    if not feat_path.exists():
        print(f"EKSİK: {feat_path}")
        return 1
    df = pd.read_csv(feat_path, encoding="utf-8-sig")
    exclude = {
        "mesafe_t24_km",
        "turk_uydu",
        "hiz_t24_km_s",
        "delta_mesafe_km",
        "cop_isim",
        "cop_kaynak",
        "cop_norad_id",
    }
    feature_cols = [
        c
        for c in df.columns
        if c not in exclude
        and c != TARGET
        and pd.api.types.is_numeric_dtype(df[c])
    ]
    X = df[feature_cols].astype(float)
    y = df[TARGET].astype(float)
    X_train, X_test, y_train, y_test, meta = replicate_training_split(df, X, y)
    run_eda_after_split(X_train, X_test, y_train, feature_cols, meta, out_path)
    print("(y_test bu scriptte yalnızca boyut için bilinir; metrikte kullanılmaz.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
