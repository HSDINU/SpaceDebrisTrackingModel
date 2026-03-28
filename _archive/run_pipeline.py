"""
Pipeline Çalıştırıcı — run_pipeline.py
=======================================
Temiz, tek komutla çalışan pipeline:

  python run_pipeline.py [--clean] [--predict] [--viz]

  --clean    : Sadece veri temizleme
  --predict  : Temizle + karşılaşma + feature + model + tahmin
  --viz      : Görselleştirme ekle
  (argüman yok) = tüm adımlar

Adımlar:
  0. cop_verileri_to_csv.py        (enriched CSV oluştur)
  1. ml_pipeline/step00_clean_data  (veri temizle)
  2. ml_pipeline/build_real_encounters (t0 + t+24h SGP4)
  3. ml_pipeline/step02_build_features (feature engineering)
  4. ml_pipeline/step03_train_baseline (LightGBM eğit)
  5. predict_risk.py                (simülasyon çıktısı)
  6. ml_pipeline/visualize_results  (grafikler)
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def run(module_or_script: str, is_module: bool = True) -> int:
    flag = ["-m"] if is_module else []
    cmd = [sys.executable] + flag + [module_or_script]
    print(f"\n{'━' * 60}")
    print(f"▶  {'python -m ' if is_module else 'python '}{module_or_script}")
    print(f"{'━' * 60}")
    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode != 0:
        print(f"\n❌ HATA: {module_or_script} başarısız (exit={result.returncode})")
    return result.returncode


def main():
    parser = argparse.ArgumentParser(description="Space Debris Risk Pipeline")
    parser.add_argument("--clean", action="store_true", help="Sadece veri temizleme")
    parser.add_argument("--predict", action="store_true", help="Tam pipeline (model dahil)")
    parser.add_argument("--viz", action="store_true", help="Görselleştirme ekle")
    parser.add_argument("--all", action="store_true", help="Tüm adımlar (default)")
    args = parser.parse_args()

    run_all = args.all or not any([args.clean, args.predict, args.viz])

    steps = []

    if run_all or args.clean or args.predict:
        steps += [
            ("cop_verileri_to_csv", True),
            ("ml_pipeline.step00_clean_data", True),
        ]

    if run_all or args.predict:
        steps += [
            ("ml_pipeline.build_real_encounters", True),
            ("ml_pipeline.step02_build_features", True),
            ("ml_pipeline.step03_train_baseline", True),
            ("predict_risk", False),
        ]

    if run_all or args.viz:
        steps.append(("ml_pipeline.visualize_results", True))

    print("=" * 60)
    print("🛰️  Space Debris Risk Pipeline")
    print(f"Adım sayısı: {len(steps)}")
    print("=" * 60)

    for step, is_module in steps:
        code = run(step, is_module)
        if code != 0:
            print(f"\nPipeline {step} adımında durdu.")
            return 1

    print("\n" + "=" * 60)
    print("✅ Pipeline tamamlandı.")
    print(f"📁 Çıktılar: {ROOT / 'data'}")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
