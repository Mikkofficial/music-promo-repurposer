#!/usr/bin/env bash
set -e

echo "=========================================================="
echo "   Music Promo Repurposer - 1-Click Installer"
echo "   TikTok -> YouTube Shorts, IG Trial Reels & FB Reels"
echo "=========================================================="
echo ""

# Check & install Docker if missing (Linux VPS / Debian / Ubuntu)
if ! command -v docker >/dev/null 2>&1; then
  echo "[1/4] Docker not found. Installing Docker automatically..."
  curl -fsSL https://get.docker.com | sh
  sudo systemctl enable --now docker || true
else
  echo "[1/4] Docker is already installed."
fi

# Clone or update repository if run via curl | bash
INSTALL_DIR="$HOME/music-promo-repurposer"
if [ ! -f "./docker-compose.yml" ]; then
  echo "[2/4] Downloading project files to $INSTALL_DIR..."
  if ! command -v git >/dev/null 2>&1; then
    sudo apt-get update && sudo apt-get install -y git || true
  fi
  rm -rf "$INSTALL_DIR"
  git clone https://github.com/YOUR_GITHUB_USERNAME/music-promo-repurposer.git "$INSTALL_DIR"
  cd "$INSTALL_DIR"
else
  echo "[2/4] Using current directory..."
fi

echo ""
echo "[3/4] Enter your account details (press Enter after each):"
echo "----------------------------------------------------------"
read -rp "1. Your subdomain (e.g. promo.yourdomain.com): " DOMAIN
read -rp "2. Your TikTok username (without @): " TIKTOK_USERNAME
read -rp "3. Your Instagram Business Account ID (178414...): " IG_BUSINESS_ID
read -rp "4. Your Facebook Page ID: " FB_PAGE_ID
read -rp "5. Your Permanent Meta Page Access Token (EAA...): " META_PAGE_TOKEN
read -rp "6. Your Timezone [default: Europe/Berlin]: " TIMEZONE
TIMEZONE=${TIMEZONE:-Europe/Berlin}

cat > .env <<EOF
DOMAIN=${DOMAIN}
TIKTOK_USERNAME=${TIKTOK_USERNAME}
IG_BUSINESS_ID=${IG_BUSINESS_ID}
FB_PAGE_ID=${FB_PAGE_ID}
META_PAGE_TOKEN=${META_PAGE_TOKEN}
TIMEZONE=${TIMEZONE}
EOF

echo ""
echo "[4/4] Building container & starting your automation server..."
if docker compose version >/dev/null 2>&1; then
  sudo docker compose up -d --build
else
  sudo docker-compose up -d --build
fi

echo ""
echo "=========================================================="
echo "   ALL DONE! Your server is live at:"
echo "   https://${DOMAIN}"
echo ""
echo "   Final 2 steps in your browser:"
echo "   1. Open https://${DOMAIN} and create your n8n admin login."
echo "   2. Open the pre-loaded workflow, connect your YouTube"
echo "      account in the YouTube node, and toggle 'Active' ON!"
echo "=========================================================="
