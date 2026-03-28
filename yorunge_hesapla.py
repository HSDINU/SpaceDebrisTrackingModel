import json
from datetime import datetime, timedelta
from sgp4.api import Satrec, jday

# 1. Az önce oluşturduğumuz JSON verisini oku
with open("turk_uydulari.json", "r", encoding="utf-8") as f:
    turk_uydulari = json.load(f)

# 2. Zaman aralığını belirle (Şu andan itibaren 24 saat, 5'er dakikalık adımlar)
# utcnow() kullanıyoruz çünkü uzay hesaplamaları her zaman UTC (Greenwich) saatine göre yapılır.
baslangic_zamani = datetime.utcnow()
zaman_adimlari = [baslangic_zamani + timedelta(minutes=5 * i) for i in range(int(24 * 60 / 5))]

print("Fizik motoru başlatıldı. Yörüngeler hesaplanıyor...\n")

sonuclar = {}

# 3. Her bir uydu için konum (r) ve hız (v) hesapla
for uydu_data in turk_uydulari:
    uydu_adi = uydu_data["name"]
    line1 = uydu_data["tle_line1"]
    line2 = uydu_data["tle_line2"]

    # TLE verisinden SGP4 uydu nesnesi oluştur
    uydu = Satrec.twoline2rv(line1, line2)
    koordinatlar = []

    for zaman in zaman_adimlari:
        # sgp4 kütüphanesi zamanı 'Julian Date' formatında ister
        jd, fr = jday(zaman.year, zaman.month, zaman.day, zaman.hour, zaman.minute, zaman.second)

        # e: hata kodu (0 ise sorun yok), r: pozisyon (x,y,z km), v: hız (vx,vy,vz km/s)
        e, r, v = uydu.sgp4(jd, fr)

        if e == 0:
            koordinatlar.append({
                "zaman": zaman.isoformat(),
                "pozisyon_km": r,
                "hiz_km_s": v
            })

    sonuclar[uydu_adi] = koordinatlar
    print(f"✅ {uydu_adi} için 24 saatlik rota hesaplandı. ({len(koordinatlar)} veri noktası)")

# Çıktının ufak bir kısmını ekrana yazdıralım ki çalıştığını görelim
ornek_uydu = turk_uydulari[0]["name"]
ornek_an = sonuclar[ornek_uydu][0]

print("\n--- ÖRNEK HESAPLAMA ÇIKTISI ---")
print(f"Uydu: {ornek_uydu}")
print(f"Tarih/Saat (UTC): {ornek_an['zaman']}")
print(f"Pozisyon (X, Y, Z) km : {ornek_an['pozisyon_km'][0]:.2f}, {ornek_an['pozisyon_km'][1]:.2f}, {ornek_an['pozisyon_km'][2]:.2f}")
print(f"Hız (Vx, Vy, Vz) km/s : {ornek_an['hiz_km_s'][0]:.2f}, {ornek_an['hiz_km_s'][1]:.2f}, {ornek_an['hiz_km_s'][2]:.2f}")
print("-------------------------------\n")

#Pozisyon (X, Y, Z): Uydunun o anki saniyede Dünya'nın merkezine göre kilometre cinsinden nerede olduğu.
#Hız (Vx, Vy, Vz): Uydunun saniyede kaç kilometre hızla o eksenlerde ilerlediği.