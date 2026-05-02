"""
Eğitilmiş regresyon modeli + tahmin şeması (sütun sırası) tek pakette saklanır.
Eski yalnızca LGBMRegressor içeren .pkl dosyaları geriye dönük uyumludur;
tahmin tarafı `ml_step03_report.json` içindeki `feature_columns` ile tamamlanır.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import joblib

ARTIFACT_SCHEMA_VERSION = 1


def save_training_artifact(
    path: Path,
    model: Any,
    feature_columns: list[str],
    target: str,
) -> None:
    payload = {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "model": model,
        "feature_columns": list(feature_columns),
        "target": target,
    }
    joblib.dump(payload, path)


def load_predictor(
    model_path: Path,
    report_path: Path | None = None,
) -> tuple[Any, list[str]]:
    """(model, feature_columns) döndürür; sütun sırası tahmin için zorunludur."""
    raw = joblib.load(model_path)
    if isinstance(raw, dict) and "model" in raw and "feature_columns" in raw:
        return raw["model"], list(raw["feature_columns"])
    if report_path and report_path.exists():
        with open(report_path, encoding="utf-8") as f:
            report = json.load(f)
        cols = report.get("feature_columns")
        if isinstance(cols, list) and cols:
            return raw, cols
    # Eski tek nesne .pkl: LightGBM feature adları
    booster_names: list[str] | None = None
    try:
        if hasattr(raw, "booster_") and raw.booster_ is not None:
            booster_names = list(raw.booster_.feature_name())
    except Exception:
        booster_names = None
    if booster_names:
        return raw, booster_names
    print(
        "HATA: Model paketi tanınmadı; ml_step03_report.json (feature_columns) gerekli.",
        file=sys.stderr,
    )
    sys.exit(1)
