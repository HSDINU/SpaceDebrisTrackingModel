"""
Azure ML Model Registration Script
-----------------------------------
Yapar:
  1. Azure ML Workspace'e bağlanır (ya da oluşturur)
  2. ml_step04_report.json'daki tüm metrikleri MLflow ile loglar
  3. lightgbm_risk_modeli.pkl'ı Model Registry'ye kaydeder
  4. Feature importance ve dataset istatistiklerini loglar

Çalıştırmak için:
  pip install -r requirements-azure.txt
  python register_model.py
"""

import json
import os
from pathlib import Path

# ── Azure ML SDK v2 ──────────────────────────────────────────────────────────
from azure.ai.ml import MLClient
from azure.ai.ml.entities import Model, Environment, BuildContext
from azure.ai.ml.constants import AssetTypes
from azure.identity import DefaultAzureCredential, InteractiveBrowserCredential
import mlflow
import mlflow.lightgbm

# ── Yapılandırma (deploy-azure.ps1 ile aynı değerler) ───────────────────────
SUBSCRIPTION_ID = os.getenv("AZURE_SUBSCRIPTION_ID", "")   # env veya doğrudan gir
RESOURCE_GROUP  = os.getenv("AZURE_RESOURCE_GROUP",  "yorunge-muhafizi-rg")
WORKSPACE_NAME  = os.getenv("AZURE_ML_WORKSPACE",    "yorunge-muhafizi-ml")

MODEL_NAME      = "space-debris-risk-lgbm"
MODEL_VERSION   = "1"
EXPERIMENT_NAME = "space-debris-risk-classification"

ROOT = Path(__file__).parent
REPORT_PATH = ROOT / "data" / "processed" / "ml_step04_report.json"
MODEL_PATH  = ROOT / "lightgbm_risk_modeli.pkl"

# ── Renkli çıktı ─────────────────────────────────────────────────────────────
def info(msg):  print(f"\033[36m[INFO]\033[0m  {msg}")
def ok(msg):    print(f"\033[32m[OK]\033[0m    {msg}")
def warn(msg):  print(f"\033[33m[WARN]\033[0m  {msg}")
def err(msg):   print(f"\033[31m[ERR]\033[0m   {msg}")


def get_ml_client() -> MLClient:
    """Azure ML istemcisi oluşturur. Önce DefaultAzureCredential, yoksa browser."""
    if not SUBSCRIPTION_ID:
        err("AZURE_SUBSCRIPTION_ID ortam değişkeni ayarlanmamış!")
        err("  $env:AZURE_SUBSCRIPTION_ID = 'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx'")
        raise SystemExit(1)

    info(f"Subscription  : {SUBSCRIPTION_ID}")
    info(f"Resource Group: {RESOURCE_GROUP}")
    info(f"Workspace     : {WORKSPACE_NAME}")

    try:
        cred = DefaultAzureCredential()
    except Exception:
        warn("DefaultAzureCredential başarısız, tarayıcı girişi deneniyor…")
        cred = InteractiveBrowserCredential()

    return MLClient(
        credential=cred,
        subscription_id=SUBSCRIPTION_ID,
        resource_group_name=RESOURCE_GROUP,
        workspace_name=WORKSPACE_NAME,
    )


def ensure_workspace(client: MLClient):
    """Workspace erişimi doğrular."""
    try:
        ws = client.workspaces.get(WORKSPACE_NAME)
        ok(f"Workspace bulundu: {ws.name}  ({ws.location})")
        return ws
    except Exception as e:
        err(f"Workspace'e erişilemiyor: {e}")
        err("deploy-azure.ps1 ile önce workspace oluşturduğundan emin ol.")
        raise SystemExit(1)


def load_report() -> dict:
    if not REPORT_PATH.exists():
        warn(f"Rapor bulunamadı: {REPORT_PATH}")
        return {}
    with open(REPORT_PATH, encoding="utf-8") as f:
        return json.load(f)


def log_experiment(client: MLClient, report: dict):
    """MLflow ile deneme metriklerini loglar."""
    tracking_uri = client.workspaces.get(WORKSPACE_NAME).mlflow_tracking_uri
    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(EXPERIMENT_NAME)

    info(f"MLflow tracking URI: {tracking_uri}")

    with mlflow.start_run(run_name="lgbm-final-training"):
        # Dataset boyutları
        mlflow.log_param("n_train",    report.get("n_train",    0))
        mlflow.log_param("n_test",     report.get("n_test",     0))
        mlflow.log_param("n_features", report.get("n_features", 0))
        mlflow.log_param("best_model", report.get("best_model", "lightgbm"))

        # LightGBM metrikleri
        lgbm = report.get("models", {}).get("lightgbm", {})
        mlflow.log_metric("lgbm_accuracy",  lgbm.get("accuracy",  0))
        mlflow.log_metric("lgbm_f1_macro",  lgbm.get("f1_macro",  0))

        cv_acc = lgbm.get("cv_accuracy", "0 ± 0")
        cv_f1  = lgbm.get("cv_f1_macro", "0 ± 0")
        if "±" in cv_acc:
            parts = cv_acc.split("±")
            mlflow.log_metric("lgbm_cv_acc_mean",  float(parts[0].strip()))
            mlflow.log_metric("lgbm_cv_acc_std",   float(parts[1].strip()))
        if "±" in cv_f1:
            parts = cv_f1.split("±")
            mlflow.log_metric("lgbm_cv_f1_mean",   float(parts[0].strip()))
            mlflow.log_metric("lgbm_cv_f1_std",    float(parts[1].strip()))

        # Karşılaştırma: Logistic Regression
        lr = report.get("models", {}).get("logistic_regression", {})
        mlflow.log_metric("lr_accuracy", lr.get("accuracy", 0))
        mlflow.log_metric("lr_f1_macro", lr.get("f1_macro", 0))

        # XGBoost (varsa)
        xgb = report.get("models", {}).get("xgboost", {})
        if xgb:
            mlflow.log_metric("xgb_accuracy", xgb.get("accuracy", 0))
            mlflow.log_metric("xgb_f1_macro", xgb.get("f1_macro", 0))

        # Feature listesini tag olarak kaydet
        features = report.get("feature_columns", [])
        mlflow.set_tag("feature_columns", ", ".join(features))
        mlflow.set_tag("model_type",       "LightGBMClassifier")
        mlflow.set_tag("task",             "multi-class risk classification")
        mlflow.set_tag("classes",          "DÜŞÜK / ORTA / YÜKSEK / KRİTİK")
        mlflow.set_tag("orbital_mechanics","SGP4")

        ok("MLflow metrikleri loglandı")
        run_id = mlflow.active_run().info.run_id
        ok(f"Run ID: {run_id}")


def register_model(client: MLClient):
    """lightgbm_risk_modeli.pkl'ı Azure ML Model Registry'ye kaydeder."""
    if not MODEL_PATH.exists():
        err(f"Model dosyası bulunamadı: {MODEL_PATH}")
        raise SystemExit(1)

    info(f"Model kaydediliyor: {MODEL_NAME} v{MODEL_VERSION}")

    model = Model(
        path=str(MODEL_PATH),
        name=MODEL_NAME,
        version=MODEL_VERSION,
        type=AssetTypes.CUSTOM_MODEL,
        description=(
            "Space Debris Risk Classification — LightGBM\n"
            "Accuracy: 99.68% | F1-macro: 99.37%\n"
            "Classes: DÜŞÜK / ORTA / YÜKSEK / KRİTİK\n"
            "Features: 19 orbital + relative velocity parameters\n"
            "Trained with SGP4 propagated TLE data"
        ),
        tags={
            "framework":      "lightgbm",
            "task":           "classification",
            "accuracy":       "0.9968",
            "f1_macro":       "0.9937",
            "n_classes":      "4",
            "n_features":     "19",
            "orbital_model":  "SGP4",
            "dataset_size":   "156735",
        },
    )

    registered = client.models.create_or_update(model)
    ok(f"Model kaydedildi: {registered.name}  v{registered.version}")
    ok(f"  Asset ID: {registered.id}")
    return registered


def main():
    print()
    print("=" * 55)
    print("  Yörünge Muhafızı — Azure ML Model Registration")
    print("=" * 55)
    print()

    # 1. Bağlantı
    client = get_ml_client()
    ensure_workspace(client)

    # 2. Raporu yükle
    report = load_report()
    if report:
        ok(f"Rapor okundu: {len(report.get('models', {}))} model karşılaştırması")
    else:
        warn("Rapor boş, sadece model kaydedilecek")

    # 3. MLflow experiment logla
    if report:
        info("MLflow deneyi loglanıyor…")
        log_experiment(client, report)

    # 4. Model kaydet
    info("Model Registry'ye kaydediliyor…")
    register_model(client)

    print()
    print("=" * 55)
    print("  TAMAMLANDI!")
    print(f"  Azure ML Studio: https://ml.azure.com")
    print(f"  Workspace: {WORKSPACE_NAME}")
    print(f"  Model: {MODEL_NAME} v{MODEL_VERSION}")
    print(f"  Experiment: {EXPERIMENT_NAME}")
    print("=" * 55)
    print()


if __name__ == "__main__":
    main()
