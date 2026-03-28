"""
Adım 1 — ML girdilerini doğrula
==============================
Projede feature engineering / eğitim öncesi dosya varlığı, şema ve satır sayılarını kontrol eder.

Çalıştırma (proje kökünden):
  python -m ml_pipeline.step01_validate_inputs

Çıkış kodu: tüm zorunlu kontroller geçerse 0, aksi halde 1.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def check_file(path: Path, name: str) -> tuple[bool, str]:
    if not path.exists():
        return False, f"EKSİK: {name} → {path}"
    return True, f"OK: {name} ({path.stat().st_size:,} bayt)"


def main() -> int:
    root = project_root()
    print("=" * 60)
    print("Adım 1 — ML girdi doğrulaması")
    print("PROJECT_ROOT =", root)
    print("=" * 60)

    ok_all = True
    rows: list[tuple[str, bool, str]] = []

    # --- Zorunlu / kritik dosyalar ---
    critical = [
        ("turk_uydulari.json", root / "turk_uydulari.json"),
        ("cop_verileri.json", root / "cop_verileri.json"),
    ]
    for label, p in critical:
        ok, msg = check_file(p, label)
        ok_all = ok_all and ok
        rows.append((label, ok, msg))
        print(msg)

    # --- İşlenmiş Kepler (EDA ile uyumlu) ---
    proc = root / "data" / "processed"
    for fname in ("sat_combined.csv", "deb_train_combined.csv", "deb_test_combined.csv"):
        p = proc / fname
        ok, msg = check_file(p, fname)
        ok_all = ok_all and ok
        rows.append((fname, ok, msg))
        print(msg)
        if ok:
            df = pd.read_csv(p, nrows=0, encoding="utf-8-sig")
            need = {"dataset", "source_file", "obs_index"}.issubset(set(df.columns))
            if not need and "Dosya Adı" in df.columns:
                print(f"  → UYARI: {fname} eski şema (Dosya Adı). data/processed/ tercih edin.")
            elif need:
                print(f"  → Şema: dataset + source_file + obs_index + Kepler sütunları OK")

    # --- Snapshot çöp CSV ---
    tum = root / "tum_uzay_copleri.csv"
    ok, msg = check_file(tum, "tum_uzay_copleri.csv")
    ok_all = ok_all and ok
    rows.append(("tum_uzay_copleri", ok, msg))
    print(msg)
    if ok:
        n = sum(1 for _ in open(tum, encoding="utf-8-sig")) - 1
        print(f"  → Veri satırı (yaklaşık): {n:,}")

    # --- Yakınlaşma ML CSV (üretilmiş olabilir) ---
    enc = proc / "turk_uydu_cop_yakinlasma_ml.csv"
    ok, msg = check_file(enc, "turk_uydu_cop_yakinlasma_ml.csv")
    if not ok:
        print(f"BİLGİ: {msg} (export_turk_debris_encounters_csv.py ile üretin)")
        rows.append(("encounter_csv", False, msg))
    else:
        df = pd.read_csv(enc, encoding="utf-8-sig")
        print(f"OK: encounter CSV satır: {len(df):,}")
        rows.append(("encounter_csv", True, f"{len(df)} satır"))

    # --- ml_egitim_verisi.json ---
    mlj = root / "ml_egitim_verisi.json"
    ok, msg = check_file(mlj, "ml_egitim_verisi.json")
    print(msg)
    if ok:
        with open(mlj, encoding="utf-8") as f:
            data = json.load(f)
        print(f"  → Kayıt sayısı: {len(data)}")

    # --- Özet ---
    print("=" * 60)
    if ok_all:
        print("SONUÇ: Zorunlu dosya kontrolleri GEÇTİ (Kepler processed + TLE JSON + tum_uzay_copleri).")
        print("Sonraki adım: python -m ml_pipeline.step02_build_features")
        return 0
    print("SONUÇ: Bazı zorunlu dosyalar EKSİK veya hata var — yukarıdaki satırları düzeltin.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
