# Music Promo Repurposer — Desktop App (Windows & macOS)

Automatically crosspost every new TikTok you upload to **YouTube Shorts**, **Instagram Trial Reels**, and your **Facebook Page** (with separate analytics)—directly from your Windows PC or Mac. **No servers, no Docker, and no domain names required.**

---

## Step 1: Download & Open the App

1. Go to the **[Releases](../../releases/latest)** page of this repository.
2. Download the file for your computer:
   * **Windows:** `MusicPromoRepurposer-Windows.exe`
   * **macOS (Apple Silicon / M1–M4):** `MusicPromoRepurposer-macOS.dmg`
3. **First-time security prompt (normal for indie apps):**
   * **Windows:** If Microsoft Defender SmartScreen says *"Windows protected your PC"*, click **More info** → **Run anyway**.
   * **macOS:** Drag **MusicPromoRepurposer** into **Applications**. On first launch, **Right-click (or Control-click)** the app in Applications and select **Open** → **Open** (if blocked under *System Settings → Privacy & Security*, click **Open Anyway**).

---

## Step 2: Get Your Meta IDs & Permanent Page Token (Instagram + Facebook)

*Prerequisites:* Your Instagram must be a public **Creator** or **Business** account (200+ followers required by Instagram for Trial Reels) and linked to a **Facebook Page** (*Instagram App → Edit Profile → Page*).

1. Go to [Meta App Dashboard](https://developers.facebook.com/apps) → **Create App** → choose **Other** → **Business** → name it `MusicRepurposer` and create it.
2. Open the [Meta Graph API Explorer](https://developers.facebook.com/tools/explorer/):
   * Select your new app under **Meta App**.
   * Under **Permissions**, add these 5 permissions:
     * `pages_show_list`
     * `pages_read_engagement`
     * `pages_manage_posts`
     * `instagram_basic`
     * `instagram_content_publish`
   * Click **Generate Access Token**, log in, click **Edit settings**, and check **both** your Facebook Page and your Instagram account.
3. **Extend to 60 days:** Click the blue **`i` icon** next to the token box → **Open in Access Token Tool** → click **Extend Access Token** at the bottom and copy the new long token.
4. **Get your IDs & Permanent Page Token:** Paste this URL into your browser (replace `YOUR_60_DAY_TOKEN`):
   ```text
   https://graph.facebook.com/v21.0/me/accounts?fields=name,access_token,instagram_business_account&access_token=YOUR_60_DAY_TOKEN
   ```
   From the JSON response, copy:
   * **`Instagram Business Account ID`:** The `"id"` inside `"instagram_business_account"` (starts with `178414...`).
   * **`Facebook Page ID`:** The outer `"id"` for your artist Page.
   * **`Permanent Meta Page Token`:** The `"access_token"` listed for your artist Page (this Page Token does not expire after 60 days).

---

## Step 3: Set Up YouTube Shorts (1-Time Google Login)

1. Go to [Google Cloud Console](https://console.cloud.google.com/) and create a new project (e.g. `MusicRepurposer`).
2. Search for **YouTube Data API v3** and click **Enable**.
3. Go to **APIs & Services → OAuth consent screen**:
   * Choose **External**, fill in an app name and your email, and save.
   * Under **Test users**, click **Add Users** and add your own Gmail address.
4. Go to **APIs & Services → Credentials → Create Credentials → OAuth client ID**:
   * Choose **Desktop app** and click **Create**.
   * Click **Download JSON** (`client_secret_....json`).
5. Inside the **Music Promo Repurposer** app, click **Browse...**, select that JSON file, and click **Connect YouTube** to approve access in your browser.

---

## Step 4: Test & Run

1. Fill in your **TikTok username**, **Instagram ID**, **Facebook Page ID**, and **Permanent Meta Page Token** in the app.
2. Click **Run Now (Test)** to verify your latest TikTok (from the past 24 hours) uploads cleanly to all selected platforms.
3. Click **Start Auto-Sync (15m)** to keep it checking automatically while your computer is awake. Closing the window minimizes it to your system tray / menu bar.
