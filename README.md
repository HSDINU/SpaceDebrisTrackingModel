# Space Debris Tracking Model

> Türk uydularına 24 saat içinde yaklaşacak uzay çöplerini tespit eden ve risk puanı üreten makine öğrenmesi pipeline'ı.

---

## İçindekiler

- [Genel Bakış](#genel-bakış)
- [Nasıl Çalışır?](#nasıl-çalışır)
- [Proje Yapısı](#proje-yapısı)
- [Kurulum](#kurulum)
- [Kullanım](#kullanım)
- [Veri Kaynakları](#veri-kaynakları)
- [ML Pipeline Adımları](#ml-pipeline-adımları)
- [Çıktılar](#çıktılar)
- [Risk Seviyeleri](#risk-seviyeleri)

---

## Genel Bakış

Bu proje, **~17.400+ uzay çöpü** ile Türk uydularının yörünge bilgilerini karşılaştırarak yaklaşma olaylarını tahmin eder. Her (Türk uydusu, çöp nesnesi) çifti için SGP4 yörünge mekaniği kullanılarak t₀ ve t₀+24h anlarındaki mesafe/hız hesaplanır; ardından bir **LightGBM regresyon modeli** ile 24 saatlik mesafe tahmini yapılır ve kritik yaklaşmalar belirlenir.

---

## Nasıl Çalışır?

```
cop_verileri.json          turk_uydulari.json
       │                          │
       ▼                          │
 [0] Veri Zenginleştirme ◄────────┘
       │
       ▼
 [1] İstatistiki Temizleme
       │
       ▼
 [2] SGP4 Karşılaşma Hesabı (t₀ + t₊₂₄h + TCA)
       │
       ▼
 [3] Feature Engineering
       │
       ▼
 [4] LightGBM Model Eğitimi
       │
       ▼
 [5] Risk Tahmini & Sınıflandırma
       │
       ├──► risk_tahmin_tum.csv
       ├──► risk_tahmin_kritik.csv
       └──► risk_tahmin_simul.json
```

---

## Proje Yapısı

```
SpaceDebrisTrackingModel/
│
├── main.py                        # Pipeline giriş noktası (CLI)
├── predict_risk.py                # Risk tahmin ve sınıflandırma
├── cop_verileri_to_csv.py         # TLE + CSV birleştirme (Adım 0)
├── fetch_discos.py                # ESA DISCOS API bağlantısı (isteğe bağlı)
│
├── ml_pipeline/
│   ├── step00_clean_data.py       # İstatistiki temizleme (Adım 1)
│   ├── build_real_encounters.py   # SGP4 karşılaşma hesabı (Adım 2)
│   ├── step02_build_features.py   # Feature engineering (Adım 3)
│   ├── step03_train_baseline.py   # LightGBM eğitimi (Adım 4)
│   ├── visualize_results.py       # Grafik raporu
│   └── validate_tca.py            # TCA doğrulama
│
├── data/
│   ├── processed/                 # Ara işlenmiş veriler
│   └── output/                    # Nihai tahmin çıktıları ve grafikler
│
├── notebooks/
│   └── eda_kepler_ve_cop_snapshot.ipynb   # Keşifsel veri analizi
│
├── cop_verileri.json              # Uzay çöpü TLE verisi
├── turk_uydulari.json             # Türk uydusu TLE verisi
├── requirements.txt
└── lightgbm_risk_modeli.pkl       # Eğitilmiş model (pipeline çıktısı)
```

---

## Kurulum

**Gereksinimler:** Python 3.10+

```bash
# Repoyu klonla
git clone https://github.com/kullanici/SpaceDebrisTrackingModel.git
cd SpaceDebrisTrackingModel

# Sanal ortam oluştur (önerilen)
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/macOS

# Bağımlılıkları yükle
pip install -r requirements.txt
```

### Bağımlılıklar

| Paket | Kullanım |
|---|---|
| `numpy`, `pandas` | Veri işleme |
| `sgp4` | SGP4 yörünge mekaniği |
| `lightgbm` | ML modeli |
| `scikit-learn` | Train/test split, metrikler |
| `matplotlib` | Görselleştirme |
| `joblib` | Model kayıt/yükleme |

---

## Kullanım

### Hızlı Başlangıç

```bash
# Durum kontrolü (hangi dosyalar mevcut?)
python main.py --status

# Mevcut model ile tahmin güncelle
python main.py

# Modeli yeniden eğit ve tahmin yap
python main.py --train

# Ham veriden baştan oluştur + eğit
python main.py --rebuild

# Sadece tahmin (model mevcut olmalı)
python main.py --predict-only

# Tahmin + görsel rapor
python main.py --viz

# TCA doğrulama çalıştır
python main.py --validate

# Her şeyi çalıştır
python main.py --all
```

### Adım Adım Çalıştırma

Pipeline adımlarını tek tek çalıştırmak istiyorsanız:

```bash
# Adım 0: TLE + CSV zenginleştirme
python cop_verileri_to_csv.py

# Adım 1: Veri temizleme
python -m ml_pipeline.step00_clean_data

# Adım 2: SGP4 karşılaşma hesabı
python -m ml_pipeline.build_real_encounters

# Adım 3: Feature engineering
python -m ml_pipeline.step02_build_features

# Adım 4: Model eğitimi
python -m ml_pipeline.step03_train_baseline

# Adım 5: Risk tahmini
python predict_risk.py

# Görselleştirme (isteğe bağlı)
python -m ml_pipeline.visualize_results

# TCA doğrulama (isteğe bağlı)
python -m ml_pipeline.validate_tca
```

---

## Veri Kaynakları

| Dosya | Açıklama |
|---|---|
| `cop_verileri.json` | Uzay çöpü TLE (Two-Line Element) verisi |
| `turk_uydulari.json` | Türk uydusu TLE verisi |
| `tum_uzay_copleri.csv` | Yörünge anlık görüntüsü (zenginleştirme için) |
| ESA DISCOS API | Nesne malzeme/kütle metadata (isteğe bağlı, `fetch_discos.py`) |

> **Not:** ESA DISCOS API kullanmak için `fetch_discos.py` içindeki token alanını kendi API anahtarınızla doldurun.

---

## ML Pipeline Adımları

### Adım 0 — Veri Zenginleştirme
`cop_verileri.json` içindeki TLE verileri, `tum_uzay_copleri.csv` ile birleştirilerek yörünge parametreleri (eğim, eksantriklik, yarı-büyük eksen vb.) eklenir. Çıktı: `data/processed/cop_verileri_enriched.csv`

### Adım 1 — İstatistiki Temizleme
IQR tabanlı aykırı değer tespiti ve geçersiz TLE filtreleme uygulanır. Temizlik raporu `data/processed/cleaning_report.json` olarak kaydedilir.

### Adım 2 — SGP4 Karşılaşma Hesabı
Her (Türk uydusu, çöp) çifti için:
- **t₀ anı:** Mevcut mesafe ve göreli hız
- **t₀+24h anı:** 24 saat sonraki mesafe ve göreli hız
- **TCA (Time of Closest Approach):** 24h penceredeki minimum mesafe noktası

Çıktı: `data/processed/encounters_24h.csv` (~17k satır)

### Adım 3 — Feature Engineering
Model girdi özellikleri:

| Özellik | Açıklama |
|---|---|
| `mesafe_t0_km` | t₀ anındaki mesafe (km) |
| `hiz_t0_km_s` | t₀ anındaki göreli hız (km/s) |
| `tca_mesafe_km` | TCA anındaki minimum mesafe (km) |
| `delta_mesafe_km` | t₀→t₂₄ mesafe değişimi |
| `egim`, `eksantrisite` | Çöp yörünge elemanları |
| `baslangic_yuks_km` | Türk uydusuna göre irtifa farkı |

Hedef değişken: `mesafe_t24_km` (24 saat sonraki mesafe, km)

### Adım 4 — LightGBM Eğitimi
- **Model:** LightGBM Regressor (gradient boosting)
- **Değerlendirme:** Test RMSE ve R², 5-katlı CV, naive persistence baseline karşılaştırması
- **Çıktı:** `lightgbm_risk_modeli.pkl`, `data/processed/ml_step03_report.json`

---

## Çıktılar

| Dosya | İçerik |
|---|---|
| `data/output/risk_tahmin_tum.csv` | Tüm (uydu, çöp) çiftleri için tahmin |
| `data/output/risk_tahmin_kritik.csv` | Yalnızca kritik ve yüksek riskli çiftler |
| `data/output/risk_tahmin_simul.json` | Dashboard/simülasyon için JSON özeti |
| `data/output/tca_validation.csv` | TCA doğrulama karşılaştırması |
| `data/output/plots/` | Matplotlib görselleştirmeleri |
| `data/processed/ml_step03_report.json` | Model performans metrikleri |

---

## Risk Seviyeleri

Tahmin edilen 24h mesafeye göre her (uydu, çöp) çifti aşağıdaki sınıflara atanır:

| Seviye | Mesafe Eşiği | Açıklama |
|---|---|---|
| **KRİTİK** | < 1.000 km | Acil takip gerektirir |
| **YÜKSEK** | 1.000 – 5.000 km | Yakından izlenmeli |
| **ORTA** | 5.000 – 20.000 km | Rutin takip |
| **DÜŞÜK** | > 20.000 km | Şu an için risk yok |

---

## Lisans

Bu proje araştırma amaçlı geliştirilmiştir.
