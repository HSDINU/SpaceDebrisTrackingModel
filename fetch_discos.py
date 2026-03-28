"""
ESA DISCOS API Test + Veri Çekme
==================================
DISCOS (Database and Information System Characterising Objects in Space)
Her uzay nesnesi için: kütle, malzeme, yüzey alanı, şekil

Çalıştırma:
  python fetch_discos.py --test          # API bağlantısını test et
  python fetch_discos.py --sample 20     # 20 çöp için veri çek
  python fetch_discos.py                 # Tüm çöpler için çek (yavaş)

Çıktı: data/processed/discos_malzeme.csv
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import requests
import pandas as pd

ROOT = Path(__file__).resolve().parent

# ESA DISCOS
DISCOS_TOKEN = "IjUyMDRhOWI4LTNjNjAtNGFiMS05MmUwLTJlZWU1MDFiMDI2YiI.fAS3GvFuvDhaApBii3zacoRsfzM"
BASE_URL = "https://discosweb.esoc.esa.int/api"
HEADERS = {
    "Authorization": f"Bearer {DISCOS_TOKEN}",
    "DiscosWeb-Api-Version": "2",
}

OUT_PATH = ROOT / "data" / "processed" / "discos_malzeme.csv"


def api_get(endpoint: str, params: dict | None = None) -> dict | None:
    """DISCOS API GET isteği."""
    url = f"{BASE_URL}/{endpoint}"
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=15)
        if r.status_code == 200:
            return r.json()
        elif r.status_code == 401:
            print(f"  ❌ 401 Yetkisiz — token geçersiz olabilir")
        elif r.status_code == 404:
            print(f"  ❌ 404 Bulunamadı: {url}")
        else:
            print(f"  ❌ HTTP {r.status_code}: {r.text[:200]}")
        return None
    except requests.RequestException as e:
        print(f"  ❌ Bağlantı hatası: {e}")
        return None


def test_connection():
    """API bağlantısı ve token doğrula."""
    print("=== ESA DISCOS API Bağlantı Testi ===\n")

    # Endpoint: objects (ilk 3 nesne)
    print("1. /objects endpoint testi...")
    result = api_get("objects", params={"page[size]": 3})
    if result is None:
        print("   BAŞARISIZ")
        return False

    print(f"   ✅ Bağlandı!")
    data = result.get("data", [])
    print(f"   Toplam nesne (API'de): {result.get('meta', {}).get('total', '?')}")
    print(f"\n   İlk 3 nesne:")
    for obj in data:
        attrs = obj.get("attributes", {})
        print(f"     • {attrs.get('name', '?'):<30} "
              f"NORAD={attrs.get('satno', '?'):<8} "
              f"kütle={attrs.get('mass', '?')} kg")
    print(f"\n   Kullanılabilir field'lar: {list(data[0]['attributes'].keys()) if data else 'YOK'}")
    return True


def norad_ids_from_json() -> list[int]:
    """cop_verileri.json'dan NORAD ID'leri çıkar."""
    with open(ROOT / "cop_verileri.json", encoding="utf-8") as f:
        cops = json.load(f)
    ids = []
    for c in cops:
        tle1 = c.get("tle_line1", "")
        if tle1 and len(tle1) > 7:
            try:
                ids.append((int(tle1[2:7].strip()), c.get("isim", ""), c.get("kaynak", "")))
            except ValueError:
                pass
    return ids


def fetch_object_by_norad(norad_id: int) -> dict | None:
    """Tek NORAD ID için DISCOS nesnesi çek."""
    result = api_get("objects", params={
        "filter": f"eq(satno,{norad_id})",
        "page[size]": 1,
    })
    if result and result.get("data"):
        return result["data"][0]
    return None


def fetch_sample(n: int = 20):
    """İlk n çöp için DISCOS verisi çek ve göster."""
    print(f"\n=== DISCOS'tan {n} Örnek Çöp Verisi ===")
    ids = norad_ids_from_json()[:n]

    rows = []
    for norad, isim, kaynak in ids:
        obj = fetch_object_by_norad(norad)
        if obj:
            attrs = obj.get("attributes", {})
            rows.append({
                "norad_id": norad,
                "isim": isim,
                "kaynak": kaynak,
                "d_isim": attrs.get("name", ""),
                "d_cospar": attrs.get("cosparId", ""),
                "d_kitle_kg": attrs.get("mass", None),
                "d_sekil": attrs.get("shape", ""),
                "d_xsect_avg_m2": attrs.get("xSectAvg", None),
                "d_xsect_max_m2": attrs.get("xSectMax", None),
                "d_yukseklik_m": attrs.get("height", None),
                "d_genislik_m": attrs.get("width", None),
                "d_turu": attrs.get("objectClass", ""),
            })
            found = "✅"
        else:
            rows.append({"norad_id": norad, "isim": isim, "kaynak": kaynak})
            found = "❌"

        print(f"  {found} NORAD {norad:<7} {isim:<28} "
              f"kütle={rows[-1].get('d_kitle_kg', '?')} kg "
              f"tür={rows[-1].get('d_turu', '?')}")
        time.sleep(0.1)  # Rate limiting

    df = pd.DataFrame(rows)
    print(f"\n  Bulunan: {df['d_kitle_kg'].notna().sum()}/{n}")
    print(f"  Kütle dolu:   {df['d_kitle_kg'].notna().sum()}")
    print(f"  Şekil dolu:   {df['d_sekil'].notna().sum()}")
    print(f"\n  Kütle dağılımı (bulunanlar):")
    dolu = df[df["d_kitle_kg"].notna()]
    if len(dolu) > 0:
        print(f"    Min: {dolu['d_kitle_kg'].min()} kg")
        print(f"    Max: {dolu['d_kitle_kg'].max()} kg")
        print(f"    Ort: {dolu['d_kitle_kg'].mean():.1f} kg")
    return df


def compute_reentry_risk(kitle_kg: float | None, xsect_m2: float | None) -> float:
    """
    Fizik tabanlı yere düşme riski skoru.
    Balistik katsayı (BC) = kütle / (Cd × kesit_alanı)
    BC yüksek → atmosferde çok az frenlenir → yere ulaşma olasılığı artar

    Normalleştirilmiş 0–1 skoru döner.
    """
    if kitle_kg is None:
        return 0.40  # varsayılan

    # Ağırlık eşiği: >300 kg nesneler %70+ olasılıkla hayatta kalır
    if xsect_m2 is not None and xsect_m2 > 0:
        # Balistik katsayı proxy (Cd≈2.2 kabul)
        bc = kitle_kg / (2.2 * xsect_m2)
        # BC < 10: tamamen yanar | BC > 80: yere ulaşır
        if bc < 10:
            return 0.10
        elif bc < 30:
            return 0.30
        elif bc < 60:
            return 0.55
        elif bc < 100:
            return 0.80
        else:
            return 0.95
    else:
        # Sadece kütle:
        if kitle_kg < 10:
            return 0.05
        elif kitle_kg < 50:
            return 0.20
        elif kitle_kg < 150:
            return 0.40
        elif kitle_kg < 500:
            return 0.65
        else:
            return 0.85


REENTRY_RISK_BY_CLASS: dict[str, float] = {
    # objectClass → yere_dusme_riski_skoru
    # Kaynak: ESA Space Debris Technical Note + IADC guidelines
    "Payload":                         0.45,   # Uydular: değişken, orta varsayılan
    "Payload Fragmentation Debris":    0.35,   # Enkaz: küçük parçalar, büyük çoğunluk yanar
    "Payload Debris":                   0.35,
    "Rocket Body":                      0.90,   # Motor blokları: titanyum/çelik, yüksek hayatta kalma
    "Rocket Fragmentation Debris":      0.60,   # Roket enkazı: orta-yüksek
    "Rocket Debris":                    0.60,
    "Unknown":                          0.40,
    "Other":                            0.40,
}


def fetch_objectclass_lookup(norad_ids: list[int],
                              batch_size: int = 100) -> dict[int, str]:
    """
    NORAD ID listesi için DISCOS'tan objectClass çeker.
    objectClass tüm nesnelerde dolu — en güvenilir field.
    Batch sorgusu ile rate limit'i aşar.
    """
    lookup: dict[int, str] = {}
    total = len(norad_ids)
    print(f"DISCOS objectClass çekiliyor: {total:,} nesne, {total // batch_size + 1} batch...")

    for i in range(0, total, batch_size):
        batch = norad_ids[i:i + batch_size]
        # DISCOS filter: in(satno,id1,id2,...)
        id_list = ",".join(str(x) for x in batch)
        result = api_get("objects", params={
            "filter": f"in(satno,({id_list}))",
            "page[size]": batch_size,
        })
        if result:
            for obj in result.get("data", []):
                attrs = obj.get("attributes", {})
                norad = attrs.get("satno")
                if norad:
                    lookup[norad] = {
                        "objectClass": attrs.get("objectClass", "Unknown"),
                        "mass_kg": attrs.get("mass"),
                        "xSectAvg_m2": attrs.get("xSectAvg"),
                    }
        progress = min(i + batch_size, total)
        print(f"  [{progress:>5}/{total}] {len(lookup):,} eşleşti", end="\r")
        time.sleep(0.2)  # Rate limit

    print(f"\n  Tamamlandı: {len(lookup):,}/{total} eşleşti")
    return lookup


def main():
    parser = argparse.ArgumentParser(description="ESA DISCOS malzeme verisi")
    parser.add_argument("--test",  action="store_true", help="API bağlantısını test et")
    parser.add_argument("--build", action="store_true", help="Tüm çöpler için lookup CSV oluştur")
    args = parser.parse_args()

    if args.test or not args.build:
        ok = test_connection()
        if not ok:
            return 1
        if not args.build:
            print("\n--build ile tam lookup tablosunu oluşturun:")
            print("  python fetch_discos.py --build")
            return 0

    if args.build:
        print("\n=== DISCOS Lookup Tablosu Oluşturuluyor ===")
        ids_info = norad_ids_from_json()
        norad_list = [x[0] for x in ids_info]
        isim_map = {x[0]: (x[1], x[2]) for x in ids_info}

        lookup = fetch_objectclass_lookup(norad_list)

        rows = []
        for norad, (isim, kaynak) in isim_map.items():
            d = lookup.get(norad, {})
            obj_class = d.get("objectClass", "Unknown") if d else "Unknown"
            mass_kg = d.get("mass_kg") if d else None
            xsect = d.get("xSectAvg_m2") if d else None

            # Fizik tabanlı risk: önce BC, yoksa class bazlı
            risk = compute_reentry_risk(mass_kg, xsect)
            if mass_kg is None:
                # Sadece class'a göre
                risk = REENTRY_RISK_BY_CLASS.get(obj_class, 0.40)

            rows.append({
                "norad_id": norad,
                "isim": isim,
                "kaynak": kaynak,
                "discos_objectClass": obj_class,
                "discos_mass_kg": mass_kg,
                "discos_xSectAvg_m2": xsect,
                "discos_yere_dusme_riski": round(risk, 2),
                "discos_veri_var": bool(d),
            })

        df = pd.DataFrame(rows)
        df.to_csv(OUT_PATH, index=False, encoding="utf-8-sig")

        # Özet
        print(f"\n=== SONUÇ ===")
        print(f"Toplam nesne      : {len(df):,}")
        print(f"DISCOS'ta bulunan : {df['discos_veri_var'].sum():,}")
        print(f"Kütle verisi dolu : {df['discos_mass_kg'].notna().sum():,}")
        print(f"\nObjectClass dağılımı:")
        for cls, cnt in df["discos_objectClass"].value_counts().items():
            risk_mean = df[df["discos_objectClass"] == cls]["discos_yere_dusme_riski"].mean()
            print(f"  {cls:<35} {cnt:>5,}  ort.risk={risk_mean:.2f}")
        print(f"\nKaydedildi: {OUT_PATH}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
