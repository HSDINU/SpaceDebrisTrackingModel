"""
.dat Dosyalarını Parse Eden ve Analiz Eden Script
==================================================
Bu script, SpaceDebrisTrackingModel projesindeki 3 klasördeki .dat dosyalarını okur:
  - sat/         : Uydu (satellite) yörünge elemanları (elesat*.dat)
  - deb_train/   : Uzay enkazı eğitim verileri (eledebtrain*.dat)
  - deb_test/    : Uzay enkazı test verileri (eledebnewfd*.dat)

Veri formatı (7 sütun, sabit genişlikli):
  Sütun 1: Zaman (gün cinsinden, epoch'tan farkı — negatif = geçmiş, pozitif = gelecek)
  Sütun 2: Yarı büyük eksen (a) — km cinsinden
  Sütun 3: Eksantrisite (e) — boyutsuz (0 = dairesel, 1 = parabolik)
  Sütun 4: Eğim (i) — derece cinsinden (yörünge düzlemi ile ekvator arası açı)
  Sütun 5: Yükselen düğüm boylamı (Ω, RAAN) — derece cinsinden
  Sütun 6: Periapsis argümanı (ω) — derece cinsinden
  Sütun 7: Ortalama anomali (M) — derece cinsinden

Bu 6 parametre (a, e, i, Ω, ω, M) "Keplerian Orbital Elements" olarak bilinir
ve bir cismin uzaydaki yörüngesini tam olarak tanımlar.
"""

import os
import csv
import glob
import numpy as np
from pathlib import Path


# ─── Sütun tanımları ───
COLUMN_NAMES = [
    "Zaman (gün)",
    "Yarı Büyük Eksen a (km)",
    "Eksantrisite e",
    "Eğim i (derece)",
    "RAAN Ω (derece)",
    "Periapsis Argümanı ω (derece)",
    "Ortalama Anomali M (derece)",
]

COLUMN_NAMES_EN = [
    "time_days",
    "semi_major_axis_km",
    "eccentricity",
    "inclination_deg",
    "raan_deg",
    "arg_perigee_deg",
    "mean_anomaly_deg",
]


def parse_single_dat(filepath):
    """Tek bir .dat dosyasını parse eder ve numpy array döner."""
    data = []
    with open(filepath, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            values = line.split()
            if len(values) == 7:
                try:
                    row = [float(v) for v in values]
                    data.append(row)
                except ValueError:
                    continue
    return np.array(data) if data else np.empty((0, 7))


def parse_all_dat_in_folder(folder_path):
    """Bir klasördeki tüm .dat dosyalarını parse eder."""
    all_data = {}
    dat_files = sorted(glob.glob(os.path.join(folder_path, "*.dat")))

    for filepath in dat_files:
        filename = os.path.basename(filepath)
        data = parse_single_dat(filepath)
        all_data[filename] = data

    return all_data


def compute_derived_params(a_km, e):
    """Türetilmiş yörünge parametrelerini hesaplar."""
    R_EARTH = 6371.0  # km

    # Periapsis ve apoapsis mesafeleri
    r_periapsis = a_km * (1 - e)
    r_apoapsis = a_km * (1 + e)

    # İrtifa (yüzeyden)
    alt_periapsis = r_periapsis - R_EARTH
    alt_apoapsis = r_apoapsis - R_EARTH

    # Yörünge periyodu (Kepler 3. yasası)
    MU = 398600.4418  # km^3/s^2 (Yer çekim parametresi)
    period_sec = 2 * np.pi * np.sqrt(a_km**3 / MU)
    period_hours = period_sec / 3600.0

    return {
        "periapsis_alt_km": alt_periapsis,
        "apoapsis_alt_km": alt_apoapsis,
        "period_hours": period_hours,
    }


def analyze_dataset(name, all_data):
    """Bir veri setinin istatistiksel analizini yapar."""
    print(f"\n{'='*70}")
    print(f"📂 {name}")
    print(f"{'='*70}")

    total_files = len(all_data)
    total_rows = sum(d.shape[0] for d in all_data.values())
    rows_per_file = [d.shape[0] for d in all_data.values()]

    print(f"   Dosya sayısı       : {total_files}")
    print(f"   Toplam veri noktası: {total_rows}")
    print(f"   Dosya başına satır : min={min(rows_per_file)}, "
          f"max={max(rows_per_file)}, ort={np.mean(rows_per_file):.1f}")

    # Tüm verileri birleştir
    if total_rows == 0:
        print("   ⚠️  Veri bulunamadı!")
        return None

    combined = np.vstack([d for d in all_data.values() if d.shape[0] > 0])

    print(f"\n   {'Parametre':<35} {'Min':>12} {'Max':>12} {'Ortalama':>12} {'Std':>12}")
    print(f"   {'-'*83}")

    stats = {}
    for i, col_name in enumerate(COLUMN_NAMES):
        col = combined[:, i]
        col_min = np.min(col)
        col_max = np.max(col)
        col_mean = np.mean(col)
        col_std = np.std(col)
        print(f"   {col_name:<35} {col_min:>12.4f} {col_max:>12.4f} {col_mean:>12.4f} {col_std:>12.4f}")
        stats[COLUMN_NAMES_EN[i]] = {
            "min": col_min, "max": col_max, "mean": col_mean, "std": col_std
        }

    # Türetilmiş parametreler
    a_mean = stats["semi_major_axis_km"]["mean"]
    e_mean = stats["eccentricity"]["mean"]
    derived = compute_derived_params(a_mean, e_mean)

    print(f"\n   📊 Türetilmiş Parametreler (ortalama değerlerden):")
    print(f"      Periapsis irtifası  : {derived['periapsis_alt_km']:.1f} km")
    print(f"      Apoapsis irtifası   : {derived['apoapsis_alt_km']:.1f} km")
    print(f"      Yörünge periyodu    : {derived['period_hours']:.2f} saat")

    # Yörünge tipi tahmini
    if derived['period_hours'] > 23.0 and derived['period_hours'] < 25.0:
        orbit_type = "GEO (Jeosenkron)"
    elif derived['period_hours'] > 11.5 and derived['period_hours'] < 12.5:
        orbit_type = "MEO (Orta Yörünge)"
    elif derived['apoapsis_alt_km'] < 2000:
        orbit_type = "LEO (Alçak Yörünge)"
    elif e_mean > 0.5:
        orbit_type = "HEO (Yüksek Eliptik)"
    else:
        orbit_type = "Diğer / Geçiş Yörüngesi"

    print(f"      Tahmini yörünge tipi: {orbit_type}")

    # Eksantrisite dağılımı
    ecc = combined[:, 2]
    print(f"\n   📈 Eksantrisite Dağılımı:")
    print(f"      e < 0.01 (dairesel)      : {np.sum(ecc < 0.01):>6d} ({100*np.mean(ecc < 0.01):>5.1f}%)")
    print(f"      0.01 ≤ e < 0.1            : {np.sum((ecc >= 0.01) & (ecc < 0.1)):>6d} ({100*np.mean((ecc >= 0.01) & (ecc < 0.1)):>5.1f}%)")
    print(f"      0.1 ≤ e < 0.3             : {np.sum((ecc >= 0.1) & (ecc < 0.3)):>6d} ({100*np.mean((ecc >= 0.1) & (ecc < 0.3)):>5.1f}%)")
    print(f"      0.3 ≤ e < 0.5             : {np.sum((ecc >= 0.3) & (ecc < 0.5)):>6d} ({100*np.mean((ecc >= 0.3) & (ecc < 0.5)):>5.1f}%)")
    print(f"      e ≥ 0.5 (yüksek eliptik)  : {np.sum(ecc >= 0.5):>6d} ({100*np.mean(ecc >= 0.5):>5.1f}%)")

    # Eğim dağılımı
    inc = combined[:, 3]
    print(f"\n   📐 Eğim Dağılımı:")
    print(f"      i < 5° (ekvatoryal)       : {np.sum(inc < 5):>6d} ({100*np.mean(inc < 5):>5.1f}%)")
    print(f"      5° ≤ i < 30°              : {np.sum((inc >= 5) & (inc < 30)):>6d} ({100*np.mean((inc >= 5) & (inc < 30)):>5.1f}%)")
    print(f"      30° ≤ i < 60°             : {np.sum((inc >= 30) & (inc < 60)):>6d} ({100*np.mean((inc >= 30) & (inc < 60)):>5.1f}%)")
    print(f"      60° ≤ i < 90°             : {np.sum((inc >= 60) & (inc < 90)):>6d} ({100*np.mean((inc >= 60) & (inc < 90)):>5.1f}%)")
    print(f"      i ≥ 90° (retrograde)      : {np.sum(inc >= 90):>6d} ({100*np.mean(inc >= 90):>5.1f}%)")

    return stats, combined


def save_combined_csv(all_data, dataset_name, output_dir):
    """Tüm verileri tek bir CSV dosyasına kaydeder."""
    output_path = os.path.join(output_dir, f"{dataset_name}_combined.csv")
    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["Dosya Adı"] + COLUMN_NAMES_EN)
        for filename, data in sorted(all_data.items()):
            for row in data:
                writer.writerow([filename] + [f"{v:.6f}" for v in row])
    print(f"   💾 CSV kaydedildi: {output_path}")
    return output_path


def print_sample_data(all_data, dataset_name, n_files=2, n_rows=5):
    """Örnek veri yazdırır."""
    print(f"\n   📋 Örnek Veri ({dataset_name} — ilk {n_files} dosya, {n_rows} satır):")
    count = 0
    for filename, data in sorted(all_data.items()):
        if count >= n_files:
            break
        print(f"\n   [{filename}] ({data.shape[0]} satır)")
        print(f"   {'Zaman':>10} {'a (km)':>12} {'e':>12} {'i (°)':>10} "
              f"{'Ω (°)':>10} {'ω (°)':>10} {'M (°)':>10}")
        print(f"   {'-'*76}")
        for row in data[:n_rows]:
            print(f"   {row[0]:>10.2f} {row[1]:>12.2f} {row[2]:>12.7f} {row[3]:>10.4f} "
                  f"{row[4]:>10.4f} {row[5]:>10.4f} {row[6]:>10.4f}")
        if data.shape[0] > n_rows:
            print(f"   ... ({data.shape[0] - n_rows} satır daha)")
        count += 1


def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))

    print("=" * 70)
    print("🛰️  Space Debris Tracking Model — .dat Dosyası Parser & Analiz")
    print("=" * 70)

    datasets = {
        "sat (Uydu Yörünge Verileri)": os.path.join(base_dir, "sat"),
        "deb_train (Enkaz Eğitim Verileri)": os.path.join(base_dir, "deb_train"),
        "deb_test (Enkaz Test Verileri)": os.path.join(base_dir, "deb_test"),
    }

    all_stats = {}

    for name, folder in datasets.items():
        if not os.path.exists(folder):
            print(f"\n⚠️  Klasör bulunamadı: {folder}")
            continue

        # Parse et
        all_data = parse_all_dat_in_folder(folder)

        # Örnek veri göster
        print_sample_data(all_data, name)

        # İstatistiksel analiz
        result = analyze_dataset(name, all_data)
        if result:
            all_stats[name] = result

        # CSV olarak kaydet
        short_name = name.split(" ")[0]
        save_combined_csv(all_data, short_name, base_dir)

    # ─── Karşılaştırmalı Özet ───
    print(f"\n{'='*70}")
    print("📊 KARŞILAŞTIRMALI ÖZET")
    print(f"{'='*70}")

    print(f"\n{'Parametre':<25}", end="")
    for name in all_stats:
        short = name.split("(")[1].rstrip(")") if "(" in name else name
        print(f" {short:>20}", end="")
    print()
    print("-" * (25 + 20 * len(all_stats)))

    for param in COLUMN_NAMES_EN[1:]:  # Zamanı atla
        label = param.replace("_", " ").title()
        print(f"{label:<25}", end="")
        for name, (stats, _) in all_stats.items():
            print(f" {stats[param]['mean']:>20.4f}", end="")
        print()

    # ─── Yorum ───
    print(f"\n{'='*70}")
    print("📝 YORUM VE ANALİZ")
    print(f"{'='*70}")
    print("""
1. VERİ FORMATI:
   Her .dat dosyası Keplerian yörünge elemanlarını içerir (6 parametre + zaman).
   Bu, bir cismin uzaydaki yörüngesini tam olarak tanımlayan klasik formattır.

2. VERİ SETLERİ:
   • sat/       : 100 dosya — uyduların zaman serileri (her biri ~1097 veri noktası)
                   Düzenli aralıklı (10 günde bir), uzun süreli yörünge izleme.
   • deb_train/ : 100 dosya — uzay enkazı eğitim verileri (1-15 veri noktası/dosya)
                   Seyrek gözlemler, düzensiz zaman aralıkları.
   • deb_test/  : 100 dosya — uzay enkazı test verileri (1-15 veri noktası/dosya)
                   Modelin doğruluğunun test edilmesi için ayrılmış veri.

3. YÖRÜNGE ÖZELLİKLERİ:
   • Uydu verileri: a ≈ 42,258 km → GEO yörüngesi (jeosenkron, ~24 saat periyot)
                    e ≈ 0.10 → hafif eliptik yörünge
   • Enkaz verileri: Çok daha yüksek eksantrisite değişkenliği (0.04 - 0.59)
                     Daha geniş eğim aralığı → kaotik yörüngeler

4. MAKİNE ÖĞRENMESİ PERSPEKTİFİ:
   Bu veri seti, uzay enkazının yörünge tahminini (orbit prediction) öğrenmek
   için tasarlanmış bir train/test yapısıdır:
   • sat/ : Referans uydu yörüngeleri (kararlı, düzenli)
   • deb_train/ : Enkazın seyrek gözlemlerinden yörünge tahmini eğitimi
   • deb_test/ : Tahmin doğruluğunun değerlendirilmesi
""")


if __name__ == "__main__":
    main()
