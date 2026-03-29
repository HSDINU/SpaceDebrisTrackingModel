# ============================================================
#  Yörünge Muhafızı — Azure 1 Günlük Deployment Scripti
#  Maliyet: ~$1.50/gün  |  Kredi: $100
# ============================================================
# Çalıştırmadan önce: az login
# Sonra: .\deploy-azure.ps1
# ============================================================

# ── YAPILANDIRMA (değiştir) ──────────────────────────────────
$RESOURCE_GROUP  = "yorunge-muhafizi-rg"
$LOCATION        = "germanywestcentral"  # Azure for Students izinli bölge
$ACR_NAME        = "yorungemuhafizi"     # küçük harf, benzersiz olmalı
$ACI_NAME        = "yorunge-dashboard"
$IMAGE_NAME      = "yorunge-muhafizi"
$IMAGE_TAG       = "latest"

# Azure ML
$ML_WORKSPACE    = "yorunge-muhafizi-ml"
$STORAGE_ACCOUNT = "yorungemlstorage"    # küçük harf, max 24 karakter, benzersiz

# Subscription ID (az account show ile görebilirsin)
$SUBSCRIPTION_ID = ""   # BURAYA YAPISTIR: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
# ─────────────────────────────────────────────────────────────

Write-Host "=== 1. Azure'a giriş kontrol ediliyor ===" -ForegroundColor Cyan
az account show --output table
if ($LASTEXITCODE -ne 0) {
    Write-Host "Lütfen önce 'az login' komutunu çalıştır" -ForegroundColor Red
    exit 1
}

# Subscription ID otomatik al (boşsa)
if (-not $SUBSCRIPTION_ID) {
    $SUBSCRIPTION_ID = az account show --query id --output tsv
    Write-Host "Subscription ID: $SUBSCRIPTION_ID" -ForegroundColor Gray
}

Write-Host ""
Write-Host "=== 2. Resource Group oluşturuluyor ===" -ForegroundColor Cyan
az group create --name $RESOURCE_GROUP --location $LOCATION --output table

Write-Host ""
Write-Host "=== 3. Azure Machine Learning Workspace oluşturuluyor ===" -ForegroundColor Cyan
# Storage Account (Azure ML için zorunlu)
az storage account create `
    --name $STORAGE_ACCOUNT `
    --resource-group $RESOURCE_GROUP `
    --location $LOCATION `
    --sku Standard_LRS `
    --output table

# Azure ML extension yüklü mü kontrol et
az extension add --name ml --upgrade --only-show-errors 2>$null

# ML Workspace oluştur
az ml workspace create `
    --name $ML_WORKSPACE `
    --resource-group $RESOURCE_GROUP `
    --location $LOCATION `
    --storage-account $STORAGE_ACCOUNT `
    --output table

Write-Host ""
Write-Host "=== 4. Azure Container Registry oluşturuluyor ===" -ForegroundColor Cyan
az acr create `
    --resource-group $RESOURCE_GROUP `
    --name $ACR_NAME `
    --sku Basic `
    --admin-enabled true `
    --output table

Write-Host ""
Write-Host "=== 5. ACR'ye giriş yapılıyor ===" -ForegroundColor Cyan
az acr login --name $ACR_NAME

Write-Host ""
Write-Host "=== 6. Docker image build ediliyor (bu 5-10 dakika sürebilir) ===" -ForegroundColor Cyan
$ACR_LOGIN_SERVER = az acr show --name $ACR_NAME --query loginServer --output tsv
$FULL_IMAGE = "$ACR_LOGIN_SERVER/${IMAGE_NAME}:${IMAGE_TAG}"

docker build -t $FULL_IMAGE .
if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker build başarısız! Docker Desktop açık mı?" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "=== 7. Image ACR'ye push ediliyor ===" -ForegroundColor Cyan
docker push $FULL_IMAGE

Write-Host ""
Write-Host "=== 8. Azure Container Instances'a deploy ediliyor ===" -ForegroundColor Cyan
$ACR_PASSWORD = az acr credential show --name $ACR_NAME --query "passwords[0].value" --output tsv

az container create `
    --resource-group $RESOURCE_GROUP `
    --name $ACI_NAME `
    --image $FULL_IMAGE `
    --registry-login-server $ACR_LOGIN_SERVER `
    --registry-username $ACR_NAME `
    --registry-password $ACR_PASSWORD `
    --cpu 1 `
    --memory 2 `
    --ports 8501 `
    --ip-address Public `
    --dns-name-label "yorunge-muhafizi-demo" `
    --environment-variables `
        STREAMLIT_SERVER_PORT=8501 `
        STREAMLIT_SERVER_ADDRESS=0.0.0.0 `
        STREAMLIT_SERVER_HEADLESS=true `
        STREAMLIT_BROWSER_GATHER_USAGE_STATS=false `
    --output table

Write-Host ""
Write-Host "=== 9. Public URL alınıyor ===" -ForegroundColor Cyan
$FQDN = az container show `
    --resource-group $RESOURCE_GROUP `
    --name $ACI_NAME `
    --query ipAddress.fqdn `
    --output tsv

Write-Host ""
Write-Host "=== 10. Azure ML — Model kaydediliyor ===" -ForegroundColor Cyan
# Azure ML SDK kurulu mu kontrol et
$mlInstalled = pip show azure-ai-ml 2>$null
if (-not $mlInstalled) {
    Write-Host "Azure ML bağımlılıkları kuruluyor…" -ForegroundColor Gray
    pip install -r requirements-azure.txt --quiet
}

# Subscription ID ve Workspace bilgilerini ortam değişkeni olarak ayarla
$env:AZURE_SUBSCRIPTION_ID = $SUBSCRIPTION_ID
$env:AZURE_RESOURCE_GROUP  = $RESOURCE_GROUP
$env:AZURE_ML_WORKSPACE    = $ML_WORKSPACE

python register_model.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "Model kaydı başarısız (deployment devam ediyor)" -ForegroundColor Yellow
} else {
    Write-Host "Model Azure ML Registry'ye kaydedildi" -ForegroundColor Green
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "  YÖRÜNGE MUHAFIZI — DEPLOYMENT TAMAMLANDI!" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host "  Dashboard URL  : http://${FQDN}:8501" -ForegroundColor Yellow
Write-Host "  Azure ML Studio: https://ml.azure.com" -ForegroundColor Yellow
Write-Host "  Workspace      : $ML_WORKSPACE" -ForegroundColor Gray
Write-Host "  Resource Group : $RESOURCE_GROUP" -ForegroundColor Gray
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Kapatmak için: .\teardown-azure.ps1" -ForegroundColor Gray
