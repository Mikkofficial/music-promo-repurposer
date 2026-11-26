#!/usr/bin/env bash
set -e

echo "=========================================="
echo "  Music Promo Repurposer - 1-Click Setup  "
echo "=========================================="

REPO_URL="https://raw.githubusercontent.com/Mikkofficial/music-promo-repurposer/main/server"

mkdir -p ~/music-promo-repurposer
cd ~/music-promo-repurposer

read -p "1. Enter your subdomain (e.g. promo.yourdomain.com): " DOMAIN
read -p "2. Enter your TikTok username (without @): " TIKTOK_USERNAME
read -p "3. Enter your Instagram Business ID (178414...): " IG_BUSINESS_ID
read -p "4. Enter your Facebook Page ID: " FB_PAGE_ID
read -p "5. Enter your Permanent Meta Page Token: " META_PAGE_TOKEN
read -p "6. Optional Auto-Comment (e.g. Spotify/Pre-save link, or press Enter to skip): " AUTO_COMMENT

ENCRYPTION_KEY=$(openssl rand -hex 24)

cat << EOF > .env
DOMAIN=$DOMAIN
TIKTOK_USERNAME=$TIKTOK_USERNAME
IG_BUSINESS_ID=$IG_BUSINESS_ID
FB_PAGE_ID=$FB_PAGE_ID
META_PAGE_TOKEN=$META_PAGE_TOKEN
AUTO_COMMENT=$AUTO_COMMENT
N8N_ENCRYPTION_KEY=$ENCRYPTION_KEY
EOF

echo "Downloading server configuration files..."
curl -sSL "$REPO_URL/Dockerfile" -o Dockerfile
curl -sSL "$REPO_URL/docker-compose.yml" -o docker-compose.yml
curl -sSL "$REPO_URL/workflow.json" -o workflow.json

echo "Building and starting containers..."
docker compose up -d --build

echo ""
echo "Setup complete! Open https://$DOMAIN in your browser to finish connecting YouTube and activate the workflow."
