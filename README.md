# Music Promo Repurposer

Post once to TikTok and automatically share your videos to **YouTube Shorts**, **Instagram Trial Reels**, and your **Facebook Page** — watermark-free, in high-bitrate H.264 + AAC, and with **$0 monthly software fees**.

---

## Pick Your Setup Method

* **Option 1: Desktop App (Windows & macOS) — Easiest ($0):** Runs right on your laptop whenever it is awake. No servers, coding, or domain names required.
* **Option 2: 24/7 Server Setup (Home Server or VPS) — Always On ($0–$5/mo):** Runs continuously in the cloud or on a mini PC.

---

## Part 1: Get Your Free API Keys (Required for Both Options)

You only need to do this once. No business verification or company registration is required.

### A. Meta Page Token & IDs (Instagram Trial Reels + Facebook Page)
1. **Prepare your accounts:**
   * Switch your Instagram profile to a **Creator** or **Business** account (set to **Public**).
   * Connect it to a **Facebook Page** (Instagram App → *Edit Profile → Page → Connect or Create*).
2. **Create a Meta App:**
   * Go to [Meta for Developers](https://developers.facebook.com/apps
) → **My Apps → Create App** → choose **Other → Business** (leave the app in *Development Mode*).
   * Copy your **App ID** and **App Secret** from *App Settings → Basic*.
3. **Generate a 60-Day User Token:**
   * Open the [Meta Graph API Explorer](https://developers.facebook.com/tools/explorer/), select your app on the right, and add these 5 permissions:
     * `instagram_basic`
     * `instagram_content_publish`
     * `pages_show_list`
     * `pages_read_engagement`
     * `pages_manage_posts`
   * Click **Generate Access Token**, approve your Facebook Page and Instagram account in the popup, then click the blue **`i` icon** next to the token → **Open in Access Token Tool → Extend Access Token** to get your 60-day token.
4. **Grab Your Permanent Page Token & IDs:**
   * Open this URL in your browser (replace `YOUR_60_DAY_TOKEN`):
     `https://graph.facebook.com/v21.0/me/accounts?fields=name,access_token,instagram_business_account&access_token=YOUR_60_DAY_TOKEN`
   * Save these three values from the response:
     * **`access_token`** (nested under your Facebook Page name — this Page Token does not expire)
     * **`id`** inside `instagram_business_account` (starts with `178414...` — your **Instagram Business ID**)
     * **`id`** at the bottom of your Page block (your **Facebook Page ID**)

### B. YouTube Shorts Credentials (Google Cloud)
1. Go to [Google Cloud Console](https://console.cloud.google.com/), create a new project, and enable the **YouTube Data API v3**.
2. Go to **APIs & Services → OAuth consent screen**, choose **External**, add your Gmail address under **Test users**, and save.
3. Go to **Credentials → Create Credentials → OAuth client ID**:
   * **For the Desktop App:** Choose **Desktop app** and download the JSON file (`client_secret_...json`).
   * **For the 24/7 Server:** Choose **Web application**, add `https://your-subdomain.com` as an authorized redirect URI, and copy your **Client ID** and **Client Secret**.

---

## Part 2: Setup Guides

### Option 1: Desktop App (Windows & macOS)

1. **Download the App:**
   * Go to **[Latest Releases](https://github.com)** and download **`MusicPromoRepurposer-Windows.exe`** (Windows) or **`MusicPromoRepurposer-macOS.dmg`** (Mac).
2. **First-Time Launch Warning:**
   * **Windows:** If SmartScreen appears, click **More info → Run anyway**.
   * **macOS:** Drag the app to *Applications*, then **Right-click → Open** on first launch (or allow it in *System Settings → Privacy & Security*).
3. **Configure & Start:**
   * Open the app, enter your **TikTok Username** (without `@`), paste your **Instagram Business ID**, **Facebook Page ID**, and **Permanent Meta Page Token**, and select your downloaded Google **`client_secret_...json`** file.
   * Choose your **YouTube Privacy**, **Trial Reel Strategy** (*Auto-Share to Followers* or *Manual Approval Only*), and **Check Interval**.
   * Click **Run Now (Test)** to log into Google once and verify your setup, then click **Start Background Sync**.

---

### Option 2: 24/7 Server Setup (Home Server or Cloud VPS)

1. **Prepare a Server & Subdomain:**
   * Use any Linux home server (Ubuntu/Debian/Raspberry Pi) or rent a ~$5/month cloud VPS (e.g., Hetzner, DigitalOcean, Contabo).
   * Point an **A-record** for a subdomain (e.g., `://yourdomain.com`) to your server's IP address (or use a Cloudflare Tunnel if hosting at home).
2. **Run the 1-Command Installer:**
   * Connect to your server via SSH and run:
     ```bash
     curl -sSL https://githubusercontent.com | bash
     ```
   * Enter your subdomain, TikTok username, Meta IDs, and Permanent Meta Page Token when prompted. Automatic HTTPS is configured out of the box.
3. **Connect YouTube & Activate:**
   * Open `https://your-subdomain.com` in your browser and create your n8n admin login.
   * Open the pre-loaded **Music Promo Repurposer** workflow, open the **YouTube Upload** node, paste your Google **Client ID** and **Client Secret**, and click **Sign in with Google**.
   * Toggle the **Active** switch at the top of n8n to **ON** — your server now checks TikTok every 15 minutes 24/7.
