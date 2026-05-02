# Yörünge Muhafızı — Uzay Çöpü Takip ve Risk Tahmin Sistemi

---

## Neden Bu Problemi Seçtik?

Uzay, artık yalnızca birkaç ülkenin tekelinde olan bir alan değil. İletişimden navigasyona, tarımsal izlemeden erken uyarı sistemlerine kadar pek çok kritik altyapı, yörüngede dönen uyduların kesintisiz çalışmasına bağlı. Türkiye de bu tablonun içinde: TÜRKSAT serisi ticari iletişimi taşırken, GÖKTÜRK ve BİLSAT uydular savunma ile bilimsel gözlem görevleri üstleniyor.

Ancak yörüngedeki trafik her geçen yıl daha da kalabalıklaşıyor. Bugün Dünya'nın etrafında 27.000'den fazla takip edilebilir nesne var; bunların büyük çoğunluğu artık işlevini yitirmiş uydu gövdeleri, roket kademeleri ve çarpışma artıkları. Bu nesneler saatte 28.000 km'yi aşan hızlarda hareket ettiğinden, santimetre büyüklüğündeki bir parça bile aktif bir uyduyu kalıcı olarak devre dışı bırakabilir.

Ham veri zaten erişilebilir durumda — Space-Track.org üzerinden herkese açık. Asıl eksiklik burada başlıyor: bu veriden **"hangi nesne, hangi Türk uydusuna, ne zaman ve ne kadar yaklaşacak?"** sorusunu otomatik olarak yanıtlayan, açık kaynaklı, sürdürülebilir bir araç bulunmuyor. Mevcut uluslararası sistemler küresel tabloyu sunuyor ancak belirli bir ülkenin uydu filosunu merkeze alarak risk değerlendirmesi yapmıyor. Bu boşluk, projenin çıkış noktası oldu.

---

## Projenin Yaptığı

**Yörünge Muhafızı**, 9 Türk uydusu ile yaklaşık 17.400 uzay çöpü nesnesini sistematik biçimde karşılaştıran, her kombinasyon için 24 saatlik mesafe tahmini üreten ve bu tahmini eyleme dönüştürülebilir bir risk puanına çeviren uçtan uca bir makine öğrenmesi platformudur.

Sistemin merkezindeki soru son derece basit ama yanıtı teknik olarak zorlu:

> *"Bu çöp nesnesi, bu Türk uydusuna önümüzdeki 24 saat içinde tehlikeli ölçüde yaklaşacak mı?"*

Bu soruyu yanıtlamak için fizik ile makine öğrenmesi iki farklı katmanda bir araya getirildi. Fizik katmanı gerçeği üretiyor; makine öğrenmesi bu gerçeği çok daha hızlı ve ölçeklenebilir biçimde genelleştiriyor.

---

## Sistem Nasıl Çalışıyor?

### Veri Katmanı

Sistemin tüm girdileri açık ve doğrulanabilir kaynaklardan geliyor.

**[Space-Track.org](https://www.space-track.org)** — ABD Uzay Kuvvetleri'nin kamuya açık TLE (Two-Line Element) kataloğu, her uzay nesnesinin yörünge parametrelerini iki satırlık standart formatta sunuyor: eğim açısı, eksantriklik, yükselen düğüm boylamı, perijee argümanı, ortalama hareket ve ortalama anomali. Bu katalogdan alınan ~17.400 çöp nesnesinin verisi `cop_verileri.json` dosyasına aktarıldı.

**Türk uydu TLE'leri** — TÜRKSAT 3A, 4A, 4B, 5A, 5B; GÖKTÜRK-1, GÖKTÜRK-2; BİLSAT-1 ve Ayspacraft-1. Bu dokuz uyduya ait güncel TLE verileri kamuya açık kaynaklardan derlendi ve `turk_uydulari.json` dosyasında tutuldu.

İsteğe bağlı olarak **[ESA DISCOS API](https://discosweb.esac.esa.int)** üzerinden nesne kütlesi, malzeme ve çarpışma geçmişi bilgileri de zenginleştirmeye dahil edilebiliyor.

### ML Pipeline — 6 Adımda Uçtan Uca

Pipeline, tek bir komutla (`python main.py --all`) tetikleniyor ve tüm adımları sırayla yürütüyor.

**Adım 0 — Veri Zenginleştirme**
Ham JSON formatındaki TLE verisi, yörünge anlık görüntüsü (`tum_uzay_copleri.csv`) ile birleştirilerek her nesneye hesaplanmış yörünge parametreleri ekleniyor: yarı-büyük eksen, perijee ve apojee yükseklikleri, orbital periyot. Bu aşama ham veriyi anlamlı bir fiziksel tabloya dönüştürüyor.

**Adım 1 — İstatistiki Temizleme**
IQR (Çeyrekler Arası Aralık) tabanlı aykırı değer tespiti uygulanıyor. Geçersiz TLE formatları ve çift kayıtlar eleniyor. Temizleme öncesi ve sonrası kayıt sayıları bir rapor dosyasına yazılıyor.

**Adım 2 — SGP4 Fizik Motoru**
Bu adım sistemin kalbi. Her (Türk uydusu, çöp nesnesi) çifti için SGP4 algoritması üç farklı zaman noktasında çalıştırılıyor:

- **t₀ (şu an):** Her iki nesnenin ECI (Earth-Centered Inertial) koordinat sistemindeki konumu ve göreli hızı
- **t₀ + 24 saat:** Aynı hesaplama bir gün ileriye taşınıyor — bu nokta modelin öğreneceği gerçek değeri oluşturuyor
- **TCA (Time of Closest Approach):** 10 dakikalık adımlarla yapılan tarama ile 24 saatlik penceredeki en yakın geçiş anı ve mesafesi tespit ediliyor

Sentetik veri üretilmiyor, fiziksel varsayım yapılmıyor — her satır gerçek SGP4 propagasyonundan çıkıyor. Bu adım sonunda ~156.000 satırlık bir karşılaşma tablosu elde ediliyor.

**Adım 3 — Feature Engineering**
Modelin girdi matrisi 22 özellikten oluşuyor. Anlık mesafe ve hız, TCA mesafesi ve süresi, yörünge eğimi, eksantriklik, yarı-büyük eksen, perijee/apojee yükseklikleri ve Türk uydusuna göre irtifa farkı bu özellikler arasında yer alıyor.

**Adım 4 — LightGBM Model Eğitimi**
Problem bir regresyon görevi: t₀ anındaki fiziksel parametrelerden yola çıkarak t₀+24 saatteki mesafeyi tahmin et.

Model olarak LightGBM Regressor tercih edildi — gradient boosting, histogram tabanlı karar ağaçları, 500 ağaç, learning rate 0.05. Eğitim %80/%20 oranında train/test bölünmesiyle ve 5-fold çapraz doğrulamayla gerçekleştirildi. Karşılaştırma için naive persistence baseline (t₀ mesafesinin değişmeyeceğini varsayan en basit öngörü) kullanıldı.

| Metrik | Naive Baseline | LightGBM |
|--------|---------------|----------|
| R² | ~0.000 | **0.981** |
| CV R² (5-fold) | — | 0.981 ± 0.001 |

R² = 0.981, modelin 24 saatlik mesafe tahminlerinin gerçek değerlerle %98,1 oranında örtüştüğünü gösteriyor. Naive baseline sıfır civarında kalıyor çünkü yörüngeler dinamik — t₀ mesafesi t₂₄ mesafesini anlamlı biçimde öngöremiyor. LightGBM ise yörünge mekaniğinin örüntülerini öğrenerek bu boşluğu kapatıyor.

**Adım 5 — Risk Tahmini ve Sınıflandırma**
Eğitilmiş model tüm 156.000 çifti saniyeler içinde puanlandırıyor. Tahmin edilen 24 saatlik mesafeye göre her çift dört kategoriye ayrılıyor:

| Seviye | Eşik | Öneri |
|--------|------|-------|
| **KRİTİK** | < 1.000 km | Acil operatör bildirimi |
| **YÜKSEK** | 1.000 – 5.000 km | Yakın izleme |
| **ORTA** | 5.000 – 20.000 km | Rutin takip |
| **DÜŞÜK** | > 20.000 km | Mevcut durumda risk yok |

Çıktılar üç dosyaya yazılıyor: tüm çiftlerin listesi (156k satır), yalnızca kritik ve yüksek riskli çiftler (2.259 satır) ve dashboard için optimize edilmiş özet JSON.

### Dashboard

`app.py`, Streamlit altyapısı üzerine kurulu ancak görselleştirme için Three.js / WebGL kullanan bir web arayüzü. Yani Python backend, tarayıcıda gerçek zamanlı 3D render.

Açıldığında Dünya'nın üzerinde iki renk grubu görünüyor: Türk uyduları mavi noktalar olarak, çöp nesneleri ise risk seviyesine göre kırmızı ya da turuncu. Hepsi gerçek yörünge parametrelerine göre konumlandırılmış. Herhangi bir nesneye tıklandığında yörünge elemanları, tahmin edilen mesafe ve risk skoru görüntüleniyor. Sol sidebar model metriklerini ve uydu bazlı tehdit özetini sunuyor; HUD panelleri kritik tehditleri öne çıkarıyor.

---

## Çalışma Ortamı ve Deployment

Proje yerel ortamda Python 3.11 ile çalışıyor; bağımlılıkların tamamı `requirements.txt` içinde tanımlı ve standart `pip install` ile kurulabiliyor.

Üretim ortamı için Docker ile konteynerize edildi. Multi-stage build yapısı sayesinde geliştirme bağımlılıkları nihai imaja dahil olmuyor; `python:3.11-slim` tabanlı, sağlık kontrolü ve volume mount içeren bir imaj elde edildi.

Cloud deployment için Google Cloud seçildi. `deploy-gcloud.ps1` scripti Artifact Registry'ye push, Cloud Run üzerinde deploy (us-central1, 2 GB RAM, 1 vCPU) ve public URL atamasını tek seferde gerçekleştiriyor. Bunun yanında Google Kubernetes Engine üzerinde bir cluster instance'ı da kuruldu; container orchestration GKE aracılığıyla yönetiliyor. Sistem şu an HTTPS üzerinden erişilebilir durumda.

---

## Projenin Özgün Yönleri

**Türkiye perspektifi:** Küresel izleme sistemleri genel tabloyu sunuyor; belirli bir ülkenin uydu filosuna odaklanarak operasyonel risk değerlendirmesi yapan açık kaynaklı bir araç literatürde oldukça nadir. Bu sistem, Türk uydularını odak noktasına alarak operatörlere doğrudan eyleme dönüştürülebilir bilgi üretiyor.

**Fizik + ML hibrit tasarımı:** Makine öğrenmesi burada fizik hesabının yerini almıyor — onu hızlandırıyor ve ölçeklendiriyor. SGP4 hem eğitim verisini üretiyor hem de ground truth sağlıyor; LightGBM bu gerçek fizikten öğrenerek yeni tahminler üretiyor. İki katmanın rolü birbirine karışmıyor.

**Yeniden üretilebilirlik:** Tüm bileşenler açık kaynak, her adım belgelenmiş. `python main.py --all` tek komutu ham TLE verisinden başlayıp eğitilmiş modele ve risk tahminlerine ulaşan tüm pipeline'ı sıfırdan yeniden üretiyor. Kodu gören herkes aynı sonuçlara ulaşabilir.

---

**Kullanılan açık kaynak kaynaklar:** [Space-Track.org](https://www.space-track.org) · [ESA DISCOS API](https://discosweb.esac.esa.int) · [sgp4](https://pypi.org/project/sgp4/) (MIT) · [LightGBM](https://lightgbm.readthedocs.io) (MIT) · [Three.js](https://threejs.org) (MIT) · [Streamlit](https://streamlit.io) (Apache 2.0)

**Kaynak kod:** [github.com/SpaceDebrisTrackingModel](https://github.com) · **Canlı demo:** Google Cloud Run
