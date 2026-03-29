# ============================================================
#  Yörünge Muhafızı — Azure Kapatma Scripti
#  Tüm kaynakları siler, fatura kesilmez.
# ============================================================

$RESOURCE_GROUP = "yorunge-muhafizi-rg"

Write-Host "=== Azure kaynakları siliniyor ===" -ForegroundColor Yellow
Write-Host "Resource Group: $RESOURCE_GROUP" -ForegroundColor Gray
Write-Host ""

$confirm = Read-Host "Emin misin? Tüm kaynaklar silinecek (e/h)"
if ($confirm -ne "e") {
    Write-Host "İptal edildi." -ForegroundColor Gray
    exit 0
}

az group delete --name $RESOURCE_GROUP --yes --no-wait

Write-Host ""
Write-Host "Silme işlemi başlatıldı (arka planda devam eder)." -ForegroundColor Green
Write-Host "Azure portalından takip edebilirsin: https://portal.azure.com" -ForegroundColor Cyan
