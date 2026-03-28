import json

dosya_adi = "turk_uydulari.json"

# 1. Mevcut dosyayı oku
with open(dosya_adi, "r", encoding="utf-8") as f:
    uydular = json.load(f)

# 2. Sadece bu kelimeleri içeren uyduları tutacağız
kabul_edilen_kelimeler = ["TURKSAT", "GOKTURK", "IMECE", "RASAT"]
temiz_uydular = []

print("🧹 Veri temizliği başlıyor...\n")

for uydu in uydular:
    uydu_adi = uydu["name"].upper()

    # Uydunun adında kabul edilen kelimelerden herhangi biri var mı kontrolü
    if any(kelime in uydu_adi for kelime in kabul_edilen_kelimeler):
        temiz_uydular.append(uydu)
    else:
        print(f"🗑️ Yabancı uydu listeden çıkarıldı: {uydu['name']}")

# 3. Temizlenmiş listeyi aynı dosyanın üzerine yaz
with open(dosya_adi, "w", encoding="utf-8") as f:
    json.dump(temiz_uydular, f, ensure_ascii=False, indent=4)

print(f"\n✅ Temizlik tamamlandı! Hedef listemizde tam {len(temiz_uydular)} adet saf Türk uydusu kaldı.")
