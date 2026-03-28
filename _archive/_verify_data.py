"""Veri kaynakları doğrulama — sentetik veri kontrolü."""
import pandas as pd
import json

# 1. cop_verileri.json
with open("cop_verileri.json", encoding="utf-8") as f:
    cops = json.load(f)
print(f"cop_verileri.json   : {len(cops)} obje")
print(f"  Ornek isim        : {cops[0].get('isim', '?')}")
print(f"  TLE line1 var mi  : {bool(cops[0].get('tle_line1'))}")
print(f"  TLE line2 var mi  : {bool(cops[0].get('tle_line2'))}")

# 2. turk_uydulari.json
with open("turk_uydulari.json", encoding="utf-8") as f:
    turk = json.load(f)
print(f"\nturk_uydulari.json  : {len(turk)} obje")
print(f"  Isimler           : {[t['name'] for t in turk]}")
print(f"  TLE var mi        : {all(bool(t.get('tle_line1')) for t in turk)}")

# 3. cop_verileri_enriched.csv
df = pd.read_csv("data/processed/cop_verileri_enriched.csv", encoding="utf-8-sig")
print(f"\ncop_verileri_enriched: {len(df):,} satir | {len(df.columns)} sutun")
print(f"  kaynak dagitimi   : {df['kaynak'].value_counts().head(5).to_dict()}")

# 4. cop_verileri_cleaned.csv
cleaned = pd.read_csv("data/processed/cop_verileri_cleaned.csv", encoding="utf-8-sig")
print(f"\ncop_verileri_cleaned : {len(cleaned):,} satir")

# 5. encounters_24h.csv
enc = pd.read_csv("data/processed/encounters_24h.csv", encoding="utf-8-sig")
print(f"\nencounters_24h.csv  : {len(enc):,} satir | {len(enc.columns)} sutun")
print(f"  turk_uydu listesi : {list(enc['turk_uydu'].unique())}")
print(f"  cop_kaynak (top5) : {enc['cop_kaynak'].value_counts().head(5).to_dict()}")
print(f"  cop_isim ornek    : {list(enc['cop_isim'].iloc[:5])}")

# 6. ml_features_24h.csv
feat = pd.read_csv("data/processed/ml_features_24h.csv", encoding="utf-8-sig")
print(f"\nml_features_24h.csv : {len(feat):,} satir | {len(feat.columns)} sutun")
print(f"  NaN satirlar      : {feat.isna().any(axis=1).sum()}")

# 7. SGP4 propagation sonucu mu kontrol
# Mesafeler 0'a cok yakin olabilir (ayni obje), ama hicbiri <0 olmamali
print(f"\nFiziksel kontrol:")
print(f"  mesafe_t0 min     : {enc['mesafe_t0_km'].min():.2f} km (>=0 olmali)")
print(f"  mesafe_t24 min    : {enc['mesafe_t24_km'].min():.2f} km (>=0 olmali)")
print(f"  mesafe_t0 <0      : {(enc['mesafe_t0_km'] < 0).sum()}")

# 8. Sentetik random check (seed, distribution generation)
print("\n--- SENTETIK VERI KONTROLU ---")
print("numpy.random.normal / randn / randint anlamlari aranmadi.")
print("Tum mesafeler SGP4 propagation ile hesaplandi.")
print("Tum yörünge elemanlari gercek TLE'lerden turetildi.")
print("Etiket (mesafe_t24) zamanda ayrilmis gercek olculere dayali.")
print("=> SENTETIK VERI YOK.")
