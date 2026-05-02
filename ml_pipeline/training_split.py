"""
step03_train_baseline ile BİREBİR aynı train/test ayrımı.

Değerlendirme scriptleri bu fonksiyonu kullanarak kayıtlı modeli
eğitimdeki test kümesi üzerinde tekrar ölçer.
"""
from __future__ import annotations

from typing import Any

import pandas as pd
from sklearn.model_selection import GroupShuffleSplit, train_test_split

TARGET = "mesafe_t24_km"


def replicate_training_split(
    df: pd.DataFrame,
    X: pd.DataFrame,
    y: pd.Series,
    *,
    test_size: float = 0.2,
    random_state: int = 42,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series, dict[str, Any]]:
    """
    Dönüş: X_train, X_test, y_train, y_test, meta
    meta: split_method, group_column (veya None)
    """
    group_col: str | None = None
    groups: pd.Series | None = None
    if "cop_isim" in df.columns and df["cop_isim"].notna().sum() > max(30, len(df) * 0.5):
        group_col = "cop_isim"
        groups = df["cop_isim"].fillna("__bos__").astype(str)
    elif "turk_uydu" in df.columns:
        group_col = "turk_uydu"
        groups = df["turk_uydu"].astype(str)

    if groups is not None and groups.nunique() >= 5:
        gss = GroupShuffleSplit(n_splits=1, test_size=test_size, random_state=random_state)
        train_idx, test_idx = next(gss.split(X, y, groups))
        X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
        y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]
        split_method = f"group_shuffle:{group_col}"
    else:
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=random_state
        )
        split_method = "random"
        group_col = None

    meta = {"split_method": split_method, "group_column": group_col}
    return X_train, X_test, y_train, y_test, meta
