# 🎵 Multi-Platform Music Promo Repurposer (TikTok → IG Trial Reels, FB Reels & YouTube Shorts)

Automatically cross-post your TikTok videos (without watermarks, in high-fidelity H.264 + AAC audio) to **Instagram Trial Reels**, **Facebook Page Reels** (with separate analytics), and **YouTube Shorts**—100% self-hosted with zero monthly SaaS fees.

---

## ✨ What This Tool Does
* **Checks your TikTok profile every 15 minutes** (configurable) for new uploads posted in the last 24 hours.
* **Downloads the highest-bitrate H.264 video + AAC audio** (`yt-dlp` + `ffmpeg`) with zero watermarks.
* **Skips pinned videos and photo carousels** automatically and tracks posted video IDs so it never double-posts.
* **Publishes simultaneously to:**
  * **Instagram Trial Reels** (tests your video with non-followers first, with automatic graduation to followers based on performance).
  * **Facebook Page Reels** (uploaded directly to your artist Page so Facebook and Instagram views stay separated in your analytics).
  * **YouTube Shorts** (with your TikTok caption automatically mapped to the title and description).

---

## 📋 What You Need Before Installing

1. **A Server (Choose One):**
   * **Cloud VPS (~$4–$5/month):** An Ubuntu 24.04 or Debian 12 server from **Hetzner**, **Netcup**, or **DigitalOcean** (1–2 GB RAM is plenty).
   * **Home Server ($0/month):** An old PC, Mac Mini, or Raspberry Pi running Ubuntu/Debian Linux (with ports `80` and `443` forwarded to it).
2. **A Subdomain:** e.g., `promo.yourdomain.com` (Meta and Google require a real `https://` address for API integrations).
3. **Free Meta & Google API Credentials:** Follow Steps 1 & 2 below to generate them before running the installer.

---

## Step 1: Get Your Meta (Instagram & Facebook) IDs & Permanent Token

> **Important:** Your Instagram account must be set to a **Public Creator or Business** account (with at least 200 followers for Instagram Trial Reels) and linked to a **Facebook Page** (*Instagram App → Edit Profile → Page → Connect or Create*).

### 1. Create a Free Meta App
1. Go to the [Meta App Dashboard](https://developers.facebook.com/apps) and click **Create App**.
2. Choose **Other** → **Business** (or create a free Business Portfolio when prompted—**you do not need to complete Business Verification**).
3. Go to **App Settings → Basic** in the left sidebar and copy your **App ID** and **App Secret** (click *Show*).

### 2. Generate Your Token in Graph API Explorer
1. Open the [Meta Graph API Explorer](https://developers.facebook.com/tools/explorer/).
2. Select your new app in the **Meta App** dropdown on the right.
3. Under **Permissions**, add all **5** of these permissions:
   * `pages_show_list`
   * `pages_read_engagement`
   * `pages_manage_posts`
   * `instagram_basic`
   * `instagram_content_publish`
4. Click **Generate Access Token**. In the login popup, click **Edit settings** and make sure **both your artist Facebook Page and your Instagram account** are checked.
5. Copy the generated short-lived token.

### 3. Convert to a Permanent (Non-Expiring) Page Token & Get Your IDs
1. Click the small blue **`i` icon** to the left of the token box in Graph API Explorer → click **Open in Access Token Tool** → click **Extend Access Token** at the bottom to get your **60-day User Token**.
2. Open a new browser tab and paste this URL (replacing `YOUR_60_DAY_TOKEN`):
   ```text
   https://graph.facebook.com/v21.0/me/accounts?fields=name,access_token,instagram_business_account&access_token=YOUR_60_DAY_TOKEN
   ```
3. From the JSON response shown in your browser, save these **3 values** for your artist Page:
   * **`META_PAGE_TOKEN`:** The `"access_token"` string inside your artist Page block (this Page Token does not expire).
   * **`FB_PAGE_ID`:** The outer `"id"` number of your Facebook Page.
   * **`IG_BUSINESS_ID`:** The `"id"` number nested inside `"instagram_business_account"` (starts with `178414...`).

---

## Step 2: Get Your YouTube API Credentials

1. Go to the [Google Cloud Console](https://console.cloud.google.com/) and create a new project (e.g., `Music Promo`).
2. Search for **YouTube Data API v3** in the top search bar and click **Enable**.
3. Go to **APIs & Services → OAuth consent screen**:
   * Choose **External**, fill in an app name and your email, and save.
   * Under **Test users**, add your own Google/YouTube email address so you can log in without publishing the app.
4. Go to **APIs & Services → Credentials → Create Credentials → OAuth client ID**:
   * Select **Web application**.
   * Under **Authorized redirect URIs**, add:
     ```text
     https://YOUR_SUBDOMAIN/rest/oauth2-credential/callback
     ```
     *(Replace `YOUR_SUBDOMAIN` with the domain you plan to use, e.g. `promo.yourdomain.com`.)*
   * Copy your **Client ID** and **Client Secret**.

---

## Step 3: Point Your Domain to Your Server

1. Log into your domain registrar's DNS settings (e.g., Cloudflare, Namecheap, Porkbun).
2. Create an **`A` record**:
   * **Name / Host:** `promo` (or your chosen subdomain)
   * **Value / IPv4:** Your server's public IP address
   * **Proxy status (if using Cloudflare):** Set to **DNS Only (Grey Cloud)** initially so Caddy can issue your free SSL certificate automatically.

---

## Step 4: Run the 1-Command Installer

1. Connect to your server via SSH:
   ```bash
   ssh root@YOUR_SERVER_IP
   ```
2. Run the automated installer:
   ```bash
   curl -sSL https://raw.githubusercontent.com/Mikkofficial/music-promo-repurposer/main/install.sh | bash
   ```
3. Follow the on-screen prompts and paste in:
   * Your subdomain (`promo.yourdomain.com`)
   * Your TikTok username (without `@`)
   * Your `IG_BUSINESS_ID`, `FB_PAGE_ID`, and `META_PAGE_TOKEN`

The installer will automatically install Docker (if missing), build the custom container with `n8n`, `yt-dlp`, and `ffmpeg`, set up HTTPS, and import the workflow.

---

## Step 5: Connect YouTube & Activate

1. Open `https://YOUR_SUBDOMAIN` in your browser and create your local n8n admin login.
2. Open the pre-loaded **Multi-Platform TikTok Repurposer** workflow.
3. Click the **YouTube Shorts** node at the top right:
   * Click **Create New Credential** under *YouTube OAuth2 API*.
   * Paste your Google **Client ID** and **Client Secret**, click **Sign in with Google**, and grant access to your channel.
   * *(Optional)* Change **Privacy Status** from `private` to `public` once you finish testing.
4. Click **Save**, run a manual test with **Execute Workflow** to verify your latest TikTok posts cleanly, and toggle the **Active** switch at the top right to **ON**.

---

## 💡 FAQ & Tips

* **What if I pin videos to my TikTok profile?** The workflow scans the top 8 videos (`--playlist-end 8`) and only downloads videos uploaded in the last 24 hours (`--dateafter now-1day`), so older pinned videos are always ignored.
* **What happens to TikTok photo carousels?** Slideshows are safely skipped without breaking the workflow or blocking newer videos underneath them.
* **What if I post 3 TikToks back-to-back?** n8n processes 1 video per 15-minute run (`--max-downloads 1`), automatically queuing and publishing all 3 over the next 45 minutes.
* **Updating `yt-dlp` later:** If TikTok ever updates its site and downloads stop working, SSH into your server and run:
  ```bash
  docker compose restart
  ```
