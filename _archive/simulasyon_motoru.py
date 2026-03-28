import json
import math
from datetime import datetime, timedelta
from sgp4.api import Satrec, jday

# --- SIMULASYON AYARLARI ---
ZAMAN_ADIMI_DK = 5
SURE_SAAT = 24
RISK_MESAFESI_KM = 50.0

print("24 Saatlik Erken Uyari Simulasyonu Baslatiliyor...\n")

# 1. VERILERI OKU
with open("turk_uydulari.json", "r", encoding="utf-8") as f:
    hedef_uydular = json.load(f)

with open("cop_verileri.json", "r", encoding="utf-8") as f:
    cop_listesi = json.load(f)

# Demoyu hizli gostermek icin cop sayisini ilk 1000 ile sinirliyoruz.
demo_copleri = cop_listesi[:1000]
print(f"MVP Demosu icin {len(hedef_uydular)} Turk Uydusu, {len(demo_copleri)} uzay copu ile test ediliyor...\n")

zaman_adimlari = [
    datetime.utcnow() + timedelta(minutes=ZAMAN_ADIMI_DK * i)
    for i in range(int(SURE_SAAT * 60 / ZAMAN_ADIMI_DK))
]
tehlikeli_yakinlasmalar = []

# 2. SIMULASYON DONGUSU
for hedef in hedef_uydular:
    hedef_satrec = Satrec.twoline2rv(hedef["tle_line1"], hedef["tle_line2"])

    for cop in demo_copleri:
        cop_satrec = Satrec.twoline2rv(cop["tle_line1"], cop["tle_line2"])

        for zaman in zaman_adimlari:
            jd, fr = jday(zaman.year, zaman.month, zaman.day, zaman.hour, zaman.minute, zaman.second)

            e_hedef, r_hedef, v_hedef = hedef_satrec.sgp4(jd, fr)
            e_cop, r_cop, v_cop = cop_satrec.sgp4(jd, fr)

            if e_hedef == 0 and e_cop == 0:
                mesafe = math.sqrt(
                    (r_hedef[0] - r_cop[0]) ** 2
                    + (r_hedef[1] - r_cop[1]) ** 2
                    + (r_hedef[2] - r_cop[2]) ** 2
                )

                if mesafe < RISK_MESAFESI_KM:
                    bagil_hiz = math.sqrt(
                        (v_hedef[0] - v_cop[0]) ** 2
                        + (v_hedef[1] - v_cop[1]) ** 2
                        + (v_hedef[2] - v_cop[2]) ** 2
                    )

                    tehlike_verisi = {
                        "hedef_uydu": hedef["name"],
                        "yaklasan_cop": cop["isim"],
                        "risk_zamani": zaman.isoformat(),
                        "minimum_mesafe_km": round(mesafe, 2),
                        "bagil_hiz_km_s": round(bagil_hiz, 2),
                    }
                    tehlikeli_yakinlasmalar.append(tehlike_verisi)
                    print(
                        f"ERKEN UYARI: {hedef['name']} <---> {cop['isim']} | "
                        f"Mesafe: {round(mesafe, 2)} km | Hiz: {round(bagil_hiz, 2)} km/s"
                    )

print(f"\nSimulasyon Bitti. 24 saat icinde {len(tehlikeli_yakinlasmalar)} adet potansiyel risk ongoruldu.")

# 3. MAKINE OGRENMESI ICIN VERIYI KAYDET
with open("ml_egitim_verisi.json", "w", encoding="utf-8") as f:
    json.dump(tehlikeli_yakinlasmalar, f, ensure_ascii=False, indent=4)
