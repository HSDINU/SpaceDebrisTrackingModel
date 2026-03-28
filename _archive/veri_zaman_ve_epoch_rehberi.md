# Veri hatlarında zaman ve “epoch” ne anlama geliyor?

Projede **aynı kelime (epoch)** farklı kaynaklarda **farklı referansları** işaret edebilir. Karışıklığı önlemek için üç ayrı zaman kavramını ayırın.

---

## 1) TLE (Two-Line Element) içindeki epoch

- **Konum:** TLE satır 1’de, yaklaşık **alan 18–32** (YYDDD.DDDDDDDD biçimi).
- **Anlam:** Bu TLE setinin **hazırlandığı referans an**; SGP4 bu elemanları bu ana göre tanımlar.
- **Kullanım:** `export_turk_debris_encounters_csv.py` / `simulasyon_motoru.py` içinde `Satrec.twoline2rv` + `jday(...)` ile **seçtiğiniz UTC anına** yörünge yayılımı yapılır. Yani simülasyon penceresi **sizin verdiğiniz tarih/saat** ile belirlenir; TLE epoch’u ise elemanların “geçerlilik referansı”dır.

---

## 2) Kepler `.dat` → CSV’deki `time_days`

- **Konum:** `sat_combined.csv` vb. içinde `time_days` sütunu.
- **Anlam (bu projedeki parse tanımı):** İlgili `.dat` dosyasındaki **referans epoch’a göre gün cinsinden sapma** — geçmiş için negatif, gelecek için pozitif olabilir (`parse_dat_files.py` açıklaması).
- **Önemli:** Bu, TLE satırındaki epoch ile **otomatik olarak aynı takvim anı değildir**; farklı veri üreticisi / dosya formatı için “kendi dosyasındaki” epoch’a göredir.
- **Kullanım:** Yörünge elemanlarının **zaman içi evrimi** ve deb_train / deb_test ayrımı için uygundur; TLE tabanlı yakınlaşma tablosu ile **doğrudan birleştirmek** için ortak anahtar (ör. NORAD + tutarlı epoch) gerekir.

---

## 3) SGP4 simülasyon penceresi (yakınlaşma CSV)

- **Konum:** `export_turk_debris_encounters_csv.py` — `t0 = datetime.now(timezone.utc)` ile başlayan 24 saatlik (veya parametreyle değişen) adımlar.
- **Anlam:** Çarpışma/yakınlaşma için **“şu andan itibaren”** veya script çalıştığı an referanslı bir **tahmin penceresi**.
- **Çıktı:** `yakinlasma_zamani_utc` — o penceredeki **yakın geçiş anına** ait UTC zaman damgası.

---

## 4) `tum_uzay_copleri.csv` (anlık konum/hız)

- **Anlam:** Üretildiği boru hatta göre **belirli bir anlık durum** (x,y,z ve hız bileşenleri); Kepler `time_days` serisi veya TLE yayılımı ile **aynı tabloda birleştirilmez** — ortak tanımlayıcı (ör. NORAD + aynı epoch) olmadan birleşik satır anlamlı değil.

---

## Özet tablo

| Kaynak | Zaman bilgisi | Tipik kullanım |
|--------|----------------|----------------|
| TLE epoch | Eleman seti referansı | SGP4 ile istenen UTC’ye yayılım |
| Kepler `time_days` | .dat referansına göre gün | Eleman zaman serisi, EDA, deb train/test |
| Yakınlaşma script’i | UTC penceresi + TCA | Risk / ML özellik tabanı |
| `tum_uzay_copleri` | Anlık snapshot | Dağılım / kaynak grupları EDA |

---

## Rapor / tez metni için kısa cümle

> Bu çalışmada yakınlaşma olayları TLE tabanlı SGP4 ile **belirlenen UTC penceresi** içinde hesaplanmıştır; Kepler eleman dosyalarındaki `time_days` ise **ayrı bir ephemeris kaynağına** ait göreli zamandır ve iki temsil doğrudan aynı epoch üzerinden birleştirilmemiştir.
