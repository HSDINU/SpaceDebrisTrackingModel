import pandas as pd
import numpy as np
import lightgbm as lgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
import joblib
import json

# 1. GERÇEK VERİYİ OKU (İMECE vb.)
try:
    with open("ml_egitim_verisi.json", "r", encoding="utf-8") as f:
        gercek_veri = json.load(f)
except FileNotFoundError:
    gercek_veri = []

print(f"Sistemde {len(gercek_veri)} adet gerçek yakınlaşma bulundu.")
print("🧠 LightGBM Modeli için sentetik eğitim verisi üretiliyor...\n")

# 2. SENTETİK VERİ ÜRETİMİ (Modelin öğrenmesi için daha fazla veri üretiyoruz)
np.random.seed(42)
ornek_sayisi = 5000 # Veriyi 5000'e çıkardık ki test için ayıracak payımız olsun

veri = {
    "minimum_mesafe_km": np.random.uniform(0.1, 100.0, ornek_sayisi),
    "bagil_hiz_km_s": np.random.uniform(1.0, 20.0, ornek_sayisi)
}
df = pd.DataFrame(veri)

# 3. KURAL TABANLI ETİKETLEME
def risk_etiketle(row):
    mesafe = row['minimum_mesafe_km']
    hiz = row['bagil_hiz_km_s']
    
    if mesafe < 15.0 and hiz > 7.0:
        return 2 # 🔴 YÜKSEK RİSK
    elif mesafe < 40.0:
        return 1 # 🟡 ORTA RİSK
    else:
        return 0 # 🟢 DÜŞÜK RİSK

df['risk_sinifi'] = df.apply(risk_etiketle, axis=1)

# 4. VERİYİ EĞİTİM VE TEST (DOĞRULAMA) OLARAK İKİYE BÖL (%80 Eğitim, %20 Test)
X = df[['minimum_mesafe_km', 'bagil_hiz_km_s']]
y = df['risk_sinifi']

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

print(f"📊 Veri Bölünmesi: {len(X_train)} Eğitim, {len(X_test)} Test verisi ayrıldı.\n")

# 5. LIGHTGBM MODELİNİ KUR VE EĞİT
# LightGBM, hackathonların kralıdır; çok hızlı öğrenir ve doğruluğu yüksektir.
model = lgb.LGBMClassifier(
    n_estimators=100, 
    learning_rate=0.05, 
    random_state=42,
    verbose=-1 # Gereksiz logları gizler
)
model.fit(X_train, y_train)

# 6. TEST VERİSİ İLE DOĞRULAMA (VALIDATION)
y_pred = model.predict(X_test)
dogruluk = accuracy_score(y_test, y_pred)

print("-" * 40)
print(f"✅ MODEL DOĞRULAMASI (TEST SETİ)")
print("-" * 40)
print(f"Modelin Görülmemiş Verideki Başarısı (Accuracy): %{dogruluk * 100:.2f}\n")

# 7. GERÇEK VERİMİZİ (İMECE) LIGHTGBM'E SORALIM!
if len(gercek_veri) > 0:
    print("-" * 40)
    print("🎯 GERÇEK TESPİT ÜZERİNDE LIGHTGBM TESTİ")
    print("-" * 40)
    for olay in gercek_veri:
        test_df = pd.DataFrame([{
            'minimum_mesafe_km': olay['minimum_mesafe_km'], 
            'bagil_hiz_km_s': olay['bagil_hiz_km_s']
        }])
        tahmin = model.predict(test_df)[0]
        risk_metni = ["🟢 Düşük Risk", "🟡 Orta Risk", "🔴 Yüksek Risk"][tahmin]
        
        print(f"Uydu: {olay['hedef_uydu']} | Çöp: {olay['yaklasan_cop']}")
        print(f"Mesafe: {olay['minimum_mesafe_km']} km | Hız: {olay['bagil_hiz_km_s']} km/s")
        print(f"🤖 LightGBM Kararı: {risk_metni}\n")

# 8. MODELİ KAYDET
joblib.dump(model, 'lightgbm_risk_modeli.pkl')
print("💾 LightGBM beyni 'lightgbm_risk_modeli.pkl' olarak kaydedildi!")