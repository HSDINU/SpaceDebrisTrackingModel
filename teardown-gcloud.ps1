# ============================================================
#  Yörünge Muhafızı — Google Cloud Kapatma Scripti
#  Cloud Run servisini ve Artifact Registry deposunu siler.
# ============================================================

$PROJECT_ID   = ""              # boşsa gcloud config'den alır
$REGION       = "us-central1"
$SERVICE_NAME = "yorunge-muhafizi"
$REPO_NAME    = "yorunge-repo"

if (-not $PROJECT_ID) {
    $PROJECT_ID = gcloud config get-value project 2>$null
}

Write-Host ""
Write-Host "=== Google Cloud kaynakları siliniyor ===" -ForegroundColor Yellow
Write-Host "Project : $PROJECT_ID" -ForegroundColor Gray
Write-Host "Service : $SERVICE_NAME" -ForegroundColor Gray
Write-Host ""

$confirm = Read-Host "Emin misin? Cloud Run servisi ve image deposu silinecek (e/h)"
if ($confirm -ne "e") {
    Write-Host "İptal edildi." -ForegroundColor Gray
    exit 0
}

# Cloud Run servisini sil
Write-Host "Cloud Run servisi siliniyor..." -ForegroundColor Cyan
gcloud run services delete $SERVICE_NAME --region=$REGION --quiet

# Artifact Registry deposunu sil
Write-Host "Artifact Registry deposu siliniyor..." -ForegroundColor Cyan
gcloud artifacts repositories delete $REPO_NAME --location=$REGION --quiet

Write-Host ""
Write-Host "Silme tamamlandı." -ForegroundColor Green
Write-Host "Kalan kaynakları kontrol et: https://console.cloud.google.com" -ForegroundColor Cyan
