# Music Promo Repurposer (1-Command Self-Hosted Tool)

Automatically cross-post your new **TikToks** (watermark-free, highest H.264 + AAC fidelity) to **YouTube Shorts**, **Instagram Trial Reels**, and **Facebook Page Reels** with separate analytics — all inside a single lightweight container with **zero monthly SaaS fees**.

---

## Part 1: How to Publish This Package to GitHub (One-Time Setup for You)

You don't need any coding experience—just upload these files through your browser:

1. Create a free account at [github.com](https://github.com) and click **New repository** (name it `music-promo-repurposer` and set it to **Public**).
2. Click **uploading an existing file** and drag all 5 files (`Dockerfile`, `docker-compose.yml`, `install.sh`, `workflow.json`, and `README.md`) into the browser, then click **Commit changes**.
3. Open `install.sh` on GitHub, click the **Pencil (Edit)** icon, replace `YOUR_GITHUB_USERNAME` on line 24 with your actual GitHub username, and click **Commit changes**.

---

## Part 2: How Any Music Artist Installs It (1 Command)

### Before Running the Installer:
1. **Server:** Rent a cheap Linux VPS (~€4.50/month on Hetzner, Netcup, or DigitalOcean running Ubuntu/Debian) or use a home Linux server.
2. **Domain:** Point an `A` record for a subdomain (e.g. `promo.yourdomain.com`) to your server's IP address (free SSL/HTTPS is configured automatically).
3. **Meta Credentials:** Create a Meta Developer App, link your Instagram Creator/Business account (200+ followers required for Trial Reels) to a Facebook Page, and copy your **Instagram Business ID**, **Facebook Page ID**, and **Permanent Page Access Token**.

### Run the 1-Command Installer:
SSH into your server and run:

```bash
curl -sSL https://raw.githubusercontent.com/YOUR_GITHUB_USERNAME/music-promo-repurposer/main/install.sh | bash
```

The installer will automatically:
* Install Docker (if not already installed).
* Build n8n with **`yt-dlp`** and **`ffmpeg`** pre-installed for maximum audio/video quality.
* Configure automatic HTTPS (`https://promo.yourdomain.com`) via Caddy.
* Ask for your TikTok handle and Meta credentials and save them into `.env`.
* Pre-load the entire multi-platform workflow automatically.

### Final 2 Clicks in Your Browser:
1. Open `https://promo.yourdomain.com` and create your n8n admin account.
2. Open the pre-loaded **Music Promo Multi-Platform Repurposer** workflow, double-click the **YouTube Shorts Upload** node to sign in with your Google account, and toggle **Active** to **ON** at the top right!
