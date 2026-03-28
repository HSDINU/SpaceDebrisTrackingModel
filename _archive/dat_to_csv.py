"""
Adım 1: .dat → düzenli CSV veri seti
===================================
sat/, deb_train/, deb_test/ içindeki Kepler öğe dosyalarını okur; her nesne için
time_days'e göre sıralar; `data/processed/` altına birleşik CSV yazar.

Sonraki adım (veri temizleme) bu çıktıları girdi olarak kullanmalıdır.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np

from parse_dat_files import COLUMN_NAMES_EN, parse_all_dat_in_folder

# Çıktı dosya adları (kök dizindeki eski *_combined.csv ile aynı isimler, farklı konum)
OUTPUT_NAMES = {
    "sat": "sat_combined.csv",
    "deb_train": "deb_train_combined.csv",
    "deb_test": "deb_test_combined.csv",
}


def sort_by_time_days(all_data: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    """Her dosya için satırları time_days (sütun 0) artan sırada döndürür."""
    out: dict[str, np.ndarray] = {}
    for filename, arr in all_data.items():
        if arr.size == 0:
            out[filename] = arr
            continue
        order = np.argsort(arr[:, 0], kind="mergesort")
        out[filename] = arr[order]
    return out


def write_combined_csv(
    sorted_data: dict[str, np.ndarray],
    dataset_label: str,
    output_path: Path,
) -> tuple[int, int]:
    """
    Birleşik CSV yazar.
    Sütunlar: dataset, source_file, obs_index, + Kepler alanları (İngilizce).
    Dönüş: (dosya sayısı, satır sayısı)
    """
    header = ["dataset", "source_file", "obs_index", *COLUMN_NAMES_EN]
    output_path.parent.mkdir(parents=True, exist_ok=True)

    n_files = 0
    n_rows = 0
    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for source_file, data in sorted(sorted_data.items()):
            if data.shape[0] == 0:
                continue
            n_files += 1
            for obs_index, row in enumerate(data):
                writer.writerow(
                    [dataset_label, source_file, obs_index]
                    + [f"{float(v):.6f}" for v in row]
                )
                n_rows += 1
    return n_files, n_rows


def export_all(
    project_root: Path,
    output_dir: Path,
    verbose: bool = True,
) -> list[Path]:
    """
    Üç klasörü işler; yazılan dosya yollarını döndürür.
    """
    datasets = {
        "sat": project_root / "sat",
        "deb_train": project_root / "deb_train",
        "deb_test": project_root / "deb_test",
    }
    written: list[Path] = []

    for label, folder in datasets.items():
        if not folder.is_dir():
            if verbose:
                print(f"[atlandı] Klasör yok: {folder}")
            continue

        raw = parse_all_dat_in_folder(str(folder))
        sorted_data = sort_by_time_days(raw)
        out_name = OUTPUT_NAMES[label]
        out_path = output_dir / out_name
        n_files, n_rows = write_combined_csv(sorted_data, label, out_path)
        written.append(out_path)
        if verbose:
            print(f"[ok] {out_path}  ({n_files} dosya, {n_rows} satır)")

    return written


def main() -> None:
    parser = argparse.ArgumentParser(description=".dat dosyalarını CSV veri setine aktarır.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="CSV çıktı klasörü (varsayılan: <proje>/data/processed)",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Proje kökü (varsayılan: bu dosyanın bulunduğu dizin)",
    )
    args = parser.parse_args()

    project_root = args.root.resolve() if args.root else Path(__file__).resolve().parent
    output_dir = (
        args.output_dir.resolve()
        if args.output_dir
        else project_root / "data" / "processed"
    )

    print("SpaceDebrisTrackingModel — .dat → CSV")
    print(f"  Kaynak: {project_root}")
    print(f"  Çıktı:  {output_dir}")
    export_all(project_root, output_dir, verbose=True)
    print("Bitti. Sonraki adım: veri temizleme (bu CSV'leri kaynak alın).")


if __name__ == "__main__":
    main()
