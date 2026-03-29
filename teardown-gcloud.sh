#!/bin/bash
# ============================================================
#  Yörünge Muhafızı — Google Cloud Kapatma Scripti (Debian/Linux)
# ============================================================

PROJECT_ID=""
REGION="us-central1"
SERVICE_NAME="yorunge-muhafizi"
REPO_NAME="yorunge-repo"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
GRAY='\033[0;37m'
NC='\033[0m'

if [ -z "$PROJECT_ID" ]; then
    PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
fi

echo ""
echo -e "${YELLOW}=== Google Cloud kaynakları siliniyor ===${NC}"
echo -e "${GRAY}Project : $PROJECT_ID${NC}"
echo -e "${GRAY}Service : $SERVICE_NAME${NC}"
echo ""
read -p "Emin misin? Cloud Run servisi ve image deposu silinecek (e/h): " confirm

if [ "$confirm" != "e" ]; then
    echo "İptal edildi."
    exit 0
fi

echo -e "${CYAN}Cloud Run servisi siliniyor...${NC}"
gcloud run services delete "$SERVICE_NAME" --region="$REGION" --quiet

echo -e "${CYAN}Artifact Registry deposu siliniyor...${NC}"
gcloud artifacts repositories delete "$REPO_NAME" --location="$REGION" --quiet

echo ""
echo -e "${GREEN}Silme tamamlandı.${NC}"
echo -e "${CYAN}Kalan kaynakları kontrol et: https://console.cloud.google.com${NC}"
