"""
Adım 4 — Model karşılaştırması: LightGBM vs XGBoost vs Logistic Regression
============================================================================
Girdi: data/processed/ml_features_step02.csv

Sentetik veri kullanılmaz — yalnızca gerçek veri.

Metrikler: accuracy, macro F1, 5-fold CV
Çıktı: data/processed/ml_step04_report.json + ekrana tablo

Çalıştırma:
  python -m ml_pipeline.step04_model_compare
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
)
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

try:
    import lightgbm as lgb
except ImportError as e:
    raise SystemExit("lightgbm gerekli: pip install lightgbm") from e

try:
    import xgboost as xgb
except ImportError:
    print("XGBoost bulunamadı — kuruluyor...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "xgboost", "-q"])
    import xgboost as xgb

MIN_ROWS = 30
EXCLUDE_COLS = {"risk_sinifi", "turk_uydu_adi", "cop_parca_adi", "cop_kaynak",
                "referans_utc", "turk_norad_id"}


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def main() -> int:
    root = project_root()
    feat_path = root / "data" / "processed" / "ml_features_step02.csv"
    report_path = root / "data" / "processed" / "ml_step04_report.json"

    print("=" * 70)
    print("Adım 4 — LightGBM vs XGBoost vs Logistic Regression")
    print("=" * 70)

    if not feat_path.exists():
        print(f"EKSİK: {feat_path}\nÖnce: python -m ml_pipeline.step02_build_features")
        return 1

    df = pd.read_csv(feat_path, encoding="utf-8-sig")
    if len(df) < MIN_ROWS:
        print(f"HATA: {len(df)} satır — en az {MIN_ROWS} gerekli.")
        return 1

    feature_cols = [c for c in df.columns if c not in EXCLUDE_COLS]
    X = df[feature_cols].astype(float)
    y = df["risk_sinifi"].astype(int)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    print(f"Veri: {len(df):,} satır | Feature: {len(feature_cols)}")
    print(f"Eğitim: {len(X_train):,} | Test: {len(X_test):,}")
    print(f"Feature'lar: {feature_cols}\n")

    # --- Sınıf ağırlıkları ---
    n_classes = y.nunique()
    class_counts = y_train.value_counts().sort_index()
    total = len(y_train)
    class_weight = {}
    for cls in sorted(y_train.unique()):
        freq = class_counts.get(cls, 1)
        class_weight[cls] = total / (n_classes * freq)
    if 2 in class_weight:
        class_weight[2] *= 2.0

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    results: dict[str, dict] = {}

    # ═══════════════════════════════════════════════════════
    # 1) Logistic Regression (taban çizgisi)
    # ═══════════════════════════════════════════════════════
    print("─" * 70)
    print("1️⃣  Logistic Regression (taban çizgisi)")
    print("─" * 70)

    lr = Pipeline([
        ("sc", StandardScaler()),
        ("clf", LogisticRegression(
            max_iter=2000,
            multi_class="multinomial",
            random_state=42,
            class_weight=class_weight,
        )),
    ])

    cv_f1_lr = cross_val_score(lr, X, y, cv=cv, scoring="f1_macro")
    cv_acc_lr = cross_val_score(lr, X, y, cv=cv, scoring="accuracy")

    lr.fit(X_train, y_train)
    pred_lr = lr.predict(X_test)

    results["logistic_regression"] = {
        "accuracy": round(float(accuracy_score(y_test, pred_lr)), 4),
        "f1_macro": round(float(f1_score(y_test, pred_lr, average="macro", zero_division=0)), 4),
        "cv_accuracy": f"{cv_acc_lr.mean():.4f} ± {cv_acc_lr.std():.4f}",
        "cv_f1_macro": f"{cv_f1_lr.mean():.4f} ± {cv_f1_lr.std():.4f}",
    }
    print(f"  CV Accuracy: {cv_acc_lr.mean():.4f} ± {cv_acc_lr.std():.4f}")
    print(f"  CV F1 Macro: {cv_f1_lr.mean():.4f} ± {cv_f1_lr.std():.4f}")
    print(f"  Test Acc: {results['logistic_regression']['accuracy']}")
    print(f"  Test F1:  {results['logistic_regression']['f1_macro']}")
    print(f"\n{classification_report(y_test, pred_lr, digits=4)}")

    # ═══════════════════════════════════════════════════════
    # 2) LightGBM
    # ═══════════════════════════════════════════════════════
    print("─" * 70)
    print("2️⃣  LightGBM")
    print("─" * 70)

    lgbm = lgb.LGBMClassifier(
        n_estimators=300,
        learning_rate=0.05,
        num_leaves=63,
        max_depth=8,
        min_child_samples=20,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        verbose=-1,
        class_weight=class_weight,
    )

    cv_f1_lgb = cross_val_score(lgbm, X, y, cv=cv, scoring="f1_macro")
    cv_acc_lgb = cross_val_score(lgbm, X, y, cv=cv, scoring="accuracy")

    lgbm.fit(X_train, y_train)
    pred_lgb = lgbm.predict(X_test)

    results["lightgbm"] = {
        "accuracy": round(float(accuracy_score(y_test, pred_lgb)), 4),
        "f1_macro": round(float(f1_score(y_test, pred_lgb, average="macro", zero_division=0)), 4),
        "cv_accuracy": f"{cv_acc_lgb.mean():.4f} ± {cv_acc_lgb.std():.4f}",
        "cv_f1_macro": f"{cv_f1_lgb.mean():.4f} ± {cv_f1_lgb.std():.4f}",
    }
    print(f"  CV Accuracy: {cv_acc_lgb.mean():.4f} ± {cv_acc_lgb.std():.4f}")
    print(f"  CV F1 Macro: {cv_f1_lgb.mean():.4f} ± {cv_f1_lgb.std():.4f}")
    print(f"  Test Acc: {results['lightgbm']['accuracy']}")
    print(f"  Test F1:  {results['lightgbm']['f1_macro']}")
    print(f"\n{classification_report(y_test, pred_lgb, digits=4)}")

    # LightGBM modeli kaydet
    joblib.dump(lgbm, root / "lightgbm_risk_modeli.pkl")

    # ═══════════════════════════════════════════════════════
    # 3) XGBoost
    # ═══════════════════════════════════════════════════════
    print("─" * 70)
    print("3️⃣  XGBoost")
    print("─" * 70)

    # XGBoost sample_weight formatı
    sample_weight_map = {cls: total / (n_classes * class_counts.get(cls, 1)) for cls in sorted(y.unique())}
    if 2 in sample_weight_map:
        sample_weight_map[2] *= 2.0
    sw_train = y_train.map(sample_weight_map).to_numpy()

    xgbc = xgb.XGBClassifier(
        n_estimators=300,
        learning_rate=0.05,
        max_depth=8,
        min_child_weight=20,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        verbosity=0,
        eval_metric="mlogloss",
    )

    cv_f1_xgb = cross_val_score(xgbc, X, y, cv=cv, scoring="f1_macro")
    cv_acc_xgb = cross_val_score(xgbc, X, y, cv=cv, scoring="accuracy")

    xgbc.fit(X_train, y_train, sample_weight=sw_train)
    pred_xgb = xgbc.predict(X_test)

    results["xgboost"] = {
        "accuracy": round(float(accuracy_score(y_test, pred_xgb)), 4),
        "f1_macro": round(float(f1_score(y_test, pred_xgb, average="macro", zero_division=0)), 4),
        "cv_accuracy": f"{cv_acc_xgb.mean():.4f} ± {cv_acc_xgb.std():.4f}",
        "cv_f1_macro": f"{cv_f1_xgb.mean():.4f} ± {cv_f1_xgb.std():.4f}",
    }
    print(f"  CV Accuracy: {cv_acc_xgb.mean():.4f} ± {cv_acc_xgb.std():.4f}")
    print(f"  CV F1 Macro: {cv_f1_xgb.mean():.4f} ± {cv_f1_xgb.std():.4f}")
    print(f"  Test Acc: {results['xgboost']['accuracy']}")
    print(f"  Test F1:  {results['xgboost']['f1_macro']}")
    print(f"\n{classification_report(y_test, pred_xgb, digits=4)}")

    # XGBoost modeli kaydet
    joblib.dump(xgbc, root / "xgboost_risk_modeli.pkl")

    # ═══════════════════════════════════════════════════════
    # Karşılaştırma Tablosu
    # ═══════════════════════════════════════════════════════
    print("=" * 70)
    print("📊 KARŞILAŞTIRMA TABLOSU")
    print("=" * 70)
    print(f"\n{'Model':<25} {'Test Acc':>10} {'Test F1':>10} {'CV F1 Macro':>22}")
    print("─" * 70)
    for name, m in results.items():
        print(f"{name:<25} {m['accuracy']:>10.4f} {m['f1_macro']:>10.4f} {m['cv_f1_macro']:>22}")
    print("─" * 70)

    best = max(results, key=lambda k: results[k]["f1_macro"])
    print(f"\n🏆 En iyi model (Test F1 Macro): {best} → {results[best]['f1_macro']:.4f}")

    # --- Confusion Matrix karşılaştırması ---
    print(f"\n{'=' * 70}")
    print("📋 CONFUSION MATRIX KARŞILAŞTIRMASI")
    print(f"{'=' * 70}")
    labels = sorted(y.unique())
    for model_name, preds in [("LogReg", pred_lr), ("LightGBM", pred_lgb), ("XGBoost", pred_xgb)]:
        cm = confusion_matrix(y_test, preds, labels=labels)
        print(f"\n  {model_name}:")
        print(f"  {'':>10}", end="")
        for lbl in labels:
            print(f"{'P_' + str(lbl):>8}", end="")
        print()
        for i, lbl in enumerate(labels):
            print(f"  {'T_' + str(lbl):>10}", end="")
            for j in range(len(labels)):
                print(f"{cm[i][j]:>8}", end="")
            print()

    # --- Rapor kaydet ---
    report = {
        "n_train": int(len(X_train)),
        "n_test": int(len(X_test)),
        "n_features": len(feature_cols),
        "feature_columns": feature_cols,
        "models": results,
        "best_model": best,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\nRapor: {report_path}")
    print("=" * 70)
    print("SONUÇ: Adım 4 tamam.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
