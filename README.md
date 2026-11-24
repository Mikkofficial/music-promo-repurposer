# Music Promo Repurposer (Windows Desktop App)

Automatically repost your new TikTok videos (without watermarks, in highest H.264 + AAC quality) to **YouTube Shorts**, **Instagram Trial Reels**, and **Facebook Page Reels** right from your Windows laptop—**no server, no Docker, and no domain name required**.

---

## How It Works
* Runs quietly in your Windows System Tray (next to the clock) and checks your TikTok profile every 15 minutes while your computer is awake.
* Automatically skips photo carousels and remembers posted videos so it never double-posts.
* Uses a temporary 60-second Cloudflare Quick Tunnel behind the scenes whenever a new video is found so Instagram and Facebook can fetch the `.mp4` with zero router setup.

---

## Step 1: Download the App
1. Go to the **Releases** section on the right side of this GitHub page.
2. Download **`MusicPromoRepurposer-Windows.exe`**.
3. Move it to a folder on your PC (e.g., `Documents\MusicPromoRepurposer`) and double-click to open it. *(If Windows SmartScreen shows a blue warning because the app is indie-made, click **More info → Run anyway**.)*

---

## Step 2: Get Your YouTube Login File (`client_secret.json`)
1. Go to the [Google Cloud Console](https://console.cloud.google.com/) and create a **New Project** (e.g., `Music Promo`).
2. Search for **YouTube Data API v3** and click **Enable**.
3. Go to **APIs & Services → OAuth consent screen**:
   * Choose **External**, fill in an app name and your email, and save.
   * Under **Test users**, click **Add Users** and add your YouTube Google email address.
4. Go to **APIs & Services → Credentials → Create Credentials → OAuth client ID**:
   * Application type: **Desktop app** (important!).
   * Click **Create**, then click **Download JSON** and save the file as `client_secret.json`.
5. In the **Music Promo Repurposer** app, click **Browse...** next to *YouTube client_secret.json*, select the file, and click **Connect YouTube** to approve your channel in your browser.

---

## Step 3: Get Your Meta Permanent Page Token & IDs (Instagram + Facebook Reels)
1. **Prepare your accounts:**
   * Switch your Instagram profile to a **Creator** or **Business** account (public, 200+ followers required for Trial Reels) and link it to a **Facebook Page** (*Instagram → Edit Profile → Page*).
2. **Create a free Meta App:**
   * Go to [Meta App Dashboard](https://developers.facebook.com/apps) → **Create App** → choose **Other → Business** (link a free Business Portfolio if prompted; you do **not** need Business Verification).
   * Leave the app in **Development Mode**.
3. **Generate your permanent token:**
   * Open the [Meta Graph API Explorer](https://developers.facebook.com/tools/explorer/), select your app in the top-right dropdown, and add these 5 permissions:
     * `pages_show_list`
     * `pages_read_engagement`
     * `pages_manage_posts`
     * `instagram_basic`
     * `instagram_content_publish`
   * Click **Generate Access Token** and select both your **Facebook Page** and **Instagram Account** in the popup.
   * Click the blue **`i` icon** next to the token → **Open in Access Token Tool** → click **Extend Access Token** at the bottom to get a 60-day user token.
   * Open this URL in your browser (replace `YOUR_60_DAY_TOKEN`):
     ```text
     https://graph.facebook.com/v21.0/me/accounts?fields=name,access_token,instagram_business_account&access_token=YOUR_60_DAY_TOKEN
     ```
   * From the browser output, copy:
     * **`access_token`** under your Facebook Page (this Page Token does not expire)
     * **`id`** under `instagram_business_account` (starts with `178414...`)
     * **`id`** of your Facebook Page

---

## Step 4: Start Auto-Posting!
1. Paste your **TikTok Username**, **Instagram Business ID**, **Facebook Page ID**, and **Meta Permanent Page Token** into the app.
2. Click **Save Settings**, then click **Start Auto-Poster**.
3. Closing the window minimizes the app to your **Windows System Tray** so it keeps working in the background.
