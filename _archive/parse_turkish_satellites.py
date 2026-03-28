"""
Türk Uydularını TLE dosyasından parse edip CSV'ye kaydeden script.
Türksat (3A, 4A, 4B, 5A, 5B, 6A), Göktürk (1, 2), İMECE ve küp uyduları (ASELSAT vb.) arar.
"""

import csv
import re


def parse_tle_file(filepath):
    """TLE dosyasını okuyup uydu isimlerini ve NORAD ID'lerini çıkarır."""
    satellites = []

    with open(filepath, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f.readlines() if line.strip()]

    # TLE formatı: İsim satırı, ardından Line 1 ve Line 2
    i = 0
    while i < len(lines):
        line = lines[i]

        # Line 1 ile başlamayan satır = uydu ismi
        if not line.startswith("1 ") and not line.startswith("2 "):
            sat_name = line.strip()

            # Sonraki iki satır TLE Line 1 ve Line 2 olmalı
            if i + 1 < len(lines) and lines[i + 1].startswith("1 "):
                tle_line1 = lines[i + 1]
                tle_line2 = lines[i + 2] if i + 2 < len(lines) else ""

                # NORAD ID: Line 1'in 3-7. karakterleri (veya boşluğa kadar 2. alan)
                parts = tle_line1.split()
                norad_id = parts[1].rstrip("U") if len(parts) > 1 else "N/A"

                # Uluslararası tanımlayıcı (International Designator)
                intl_designator = parts[2] if len(parts) > 2 else "N/A"

                satellites.append({
                    "name": sat_name,
                    "norad_id": norad_id,
                    "intl_designator": intl_designator,
                    "tle_line1": tle_line1,
                    "tle_line2": tle_line2,
                })

                i += 3  # İsim + 2 TLE satırı atla
                continue

        i += 1

    return satellites


def find_turkish_satellites(satellites):
    """Türk uydularını filtreler."""

    # Aranacak uydu isimleri (büyük/küçük harf duyarsız)
    turkish_keywords = [
        r"TURKSAT",
        r"GOKTURK",
        r"GÖKTÜRK",
        r"IMECE",
        r"İMECE",
        r"ASELSAT",
        r"RASAT",           # Türk gözlem uydusu
        r"BILSAT",          # TÜBİTAK uydusu
        r"TURKMENSAT",      # Karıştırılmaması için not: Bu Türkmenistan
    ]

    # Bilinen Türk uydu NORAD ID'leri (dosyada bulunmasa bile referans)
    known_turkish = {
        "TURKSAT 3A":   {"norad_id": "33056", "category": "Haberleşme (GEO)", "status": "Dosyada Bulundu"},
        "TURKSAT 4A":   {"norad_id": "39522", "category": "Haberleşme (GEO)", "status": "Dosyada Bulundu"},
        "TURKSAT 4B":   {"norad_id": "40984", "category": "Haberleşme (GEO)", "status": "Dosyada Bulundu"},
        "TURKSAT 5A":   {"norad_id": "47306", "category": "Haberleşme (GEO)", "status": "Dosyada Bulundu"},
        "TURKSAT 5B":   {"norad_id": "50212", "category": "Haberleşme (GEO)", "status": "Dosyada Bulundu"},
        "TURKSAT 6A":   {"norad_id": "60233", "category": "Haberleşme (GEO)", "status": "Dosyada Bulundu"},
        "GOKTURK-1":    {"norad_id": "39030", "category": "Gözlem (LEO)",     "status": "Dosyada Yok (LEO)"},
        "GOKTURK-2":    {"norad_id": "38858", "category": "Gözlem (LEO)",     "status": "Dosyada Yok (LEO)"},
        "IMECE":        {"norad_id": "57308", "category": "Gözlem (LEO)",     "status": "Dosyada Yok (LEO)"},
        "ASELSAT":      {"norad_id": "44108", "category": "Küp Uydu (LEO)",   "status": "Dosyada Yok (LEO)"},
    }

    results = []

    # 1) Dosyada bulunan Türk uydularını ara
    found_names = set()
    for sat in satellites:
        name_upper = sat["name"].upper()
        for keyword in turkish_keywords:
            if re.search(keyword, name_upper, re.IGNORECASE):
                # TURKMENSAT gibi Türkmenistan uydularını hariç tut
                if "TURKMENALEM" in name_upper or "TURKMENSAT" in name_upper:
                    continue

                found_names.add(sat["name"].strip())
                # Kategori belirle
                category = "Haberleşme (GEO)"
                if "GOKTURK" in name_upper or "GÖKTÜRK" in name_upper:
                    category = "Gözlem (LEO)"
                elif "IMECE" in name_upper or "İMECE" in name_upper:
                    category = "Gözlem (LEO)"
                elif "ASELSAT" in name_upper:
                    category = "Küp Uydu (LEO)"

                results.append({
                    "Uydu Adı": sat["name"].strip(),
                    "NORAD ID": sat["norad_id"],
                    "Uluslararası Tanımlayıcı": sat["intl_designator"],
                    "Kategori": category,
                    "Durum": "Dosyada Bulundu",
                    "TLE Line 1": sat["tle_line1"],
                    "TLE Line 2": sat["tle_line2"],
                })
                break

    # 2) Bilinen ama dosyada bulunmayan Türk uydularını ekle
    for name, info in known_turkish.items():
        # Dosyada zaten bulunduysa tekrar ekleme
        already_found = any(name.replace("-", " ") in fn.replace("-", " ").upper() or
                           fn.replace("-", " ").upper() in name.replace("-", " ")
                           for fn in found_names)
        if not already_found and info["status"] == "Dosyada Yok (LEO)":
            results.append({
                "Uydu Adı": name,
                "NORAD ID": info["norad_id"],
                "Uluslararası Tanımlayıcı": "N/A",
                "Kategori": info["category"],
                "Durum": info["status"],
                "TLE Line 1": "N/A",
                "TLE Line 2": "N/A",
            })

    # Sıralama: Önce dosyada bulunanlar, sonra bulunmayanlar; kendi içinde isme göre
    results.sort(key=lambda x: (x["Durum"] != "Dosyada Bulundu", x["Uydu Adı"]))

    return results


def save_to_csv(results, output_path):
    """Sonuçları CSV dosyasına kaydeder."""
    fieldnames = [
        "Uydu Adı",
        "NORAD ID",
        "Uluslararası Tanımlayıcı",
        "Kategori",
        "Durum",
        "TLE Line 1",
        "TLE Line 2",
    ]

    with open(output_path, "w", newline="", encoding="utf-8-sig") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print(f"✅ CSV dosyası kaydedildi: {output_path}")
    print(f"   Toplam {len(results)} uydu kaydedildi.\n")


def main():
    tle_file = "Satellites.txt"
    output_csv = "turkish_satellites.csv"

    print("=" * 60)
    print("🛰️  Türk Uyduları TLE Parser")
    print("=" * 60)

    # TLE dosyasını parse et
    print(f"\n📄 TLE dosyası okunuyor: {tle_file}")
    all_satellites = parse_tle_file(tle_file)
    print(f"   Toplam {len(all_satellites)} uydu bulundu.\n")

    # Türk uydularını filtrele
    print("🔍 Türk uyduları aranıyor...\n")
    turkish_sats = find_turkish_satellites(all_satellites)

    # Sonuçları ekrana yazdır
    print("-" * 60)
    print(f"{'Uydu Adı':<20} {'NORAD ID':<12} {'Kategori':<20} {'Durum'}")
    print("-" * 60)
    for sat in turkish_sats:
        print(f"{sat['Uydu Adı']:<20} {sat['NORAD ID']:<12} {sat['Kategori']:<20} {sat['Durum']}")
    print("-" * 60)

    # CSV'ye kaydet
    print()
    save_to_csv(turkish_sats, output_csv)


if __name__ == "__main__":
    main()
