import os, sys, json, time, shutil, threading, subprocess, re
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
import tkinter as tk
from tkinter import ttk, filedialog
import requests, yt_dlp
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

APP_DIR = Path.home() / "MusicPromoRepurposer"
APP_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_FILE = APP_DIR / "config.json"
ARCHIVE_FILE = APP_DIR / "tiktok_history.txt"
YT_TOKEN_FILE = APP_DIR / "youtube_token.json"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

INTERVALS = {
    "Every 5 minutes": 300,
    "Every 15 minutes": 900,
    "Every 30 minutes": 1800,
    "Every 60 minutes": 3600,
    "Every 2 hours": 7200,
    "Every 6 hours": 21600,
}
STRATEGIES = {
    "Auto-Share to Followers": "SS_PERFORMANCE",
    "Manual Approval Only": "MANUAL",
}

def get_bin(name):
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
    ext = ".exe" if os.name == "nt" else ""
    if (base / f"{name}{ext}").exists():
        return str(base / f"{name}{ext}")
    if name == "ffmpeg":
        try:
            import imageio_ffmpeg
            return imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            pass
    return shutil.which(name) or name

class QuietHandler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(APP_DIR), **kw)
    def log_message(self, *a):
        pass

class RepurposerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Music Promo Repurposer")
        self.root.geometry("620x680")
        self.root.configure(bg="#121216")
        self.running = False
        self.cfg = self.load_cfg()
        self.setup_style()
        self.build_ui()

    def setup_style(self):
        s = ttk.Style()
        s.theme_use("clam")
        s.configure("TFrame", background="#121216")
        s.configure("TLabel", background="#121216", foreground="#e4e4e7", font=("Helvetica", 11))
        s.configure("Header.TLabel", font=("Helvetica", 16, "bold"), foreground="#ffffff")
        s.configure("TEntry", fieldbackground="#1e1e24", foreground="#ffffff", insertcolor="#ffffff")
        s.configure("TCombobox", fieldbackground="#1e1e24", background="#27272a", foreground="#ffffff")
        s.configure("Accent.TButton", background="#6366f1", foreground="#ffffff", font=("Helvetica", 11, "bold"), padding=6)
        s.map("Accent.TButton", background=[("active", "#4f46e5"), ("disabled", "#3f3f46")])
        s.configure("Dark.TButton", background="#27272a", foreground="#ffffff", font=("Helvetica", 11), padding=6)
        s.map("Dark.TButton", background=[("active", "#3f3f46")])

    def load_cfg(self):
        if CONFIG_FILE.exists():
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        return {
            "tiktok_user": "",
            "ig_id": "",
            "fb_id": "",
            "meta_token": "",
            "yt_secret": "",
            "cookies_path": "",
            "yt_privacy": "public",
            "trial_strategy": "Auto-Share to Followers",
            "interval": "Every 15 minutes",
        }

    def save_cfg(self):
        for k, v in self.vars.items():
            self.cfg[k] = v.get().strip()
        CONFIG_FILE.write_text(json.dumps(self.cfg, indent=2), encoding="utf-8")

    def build_ui(self):
        f = ttk.Frame(self.root, padding=18)
        f.pack(fill="both", expand=True)
        ttk.Label(f, text="Music Promo Repurposer (1080p HD)", style="Header.TLabel").pack(anchor="w", pady=(0, 12))

        keys = ["tiktok_user", "ig_id", "fb_id", "meta_token", "yt_secret", "cookies_path", "yt_privacy", "trial_strategy", "interval"]
        self.vars = {k: tk.StringVar(value=self.cfg.get(k, "")) for k in keys}

        fields = [
            ("TikTok Username (without @):", "tiktok_user", False),
            ("Instagram Business ID:", "ig_id", False),
            ("Facebook Page ID:", "fb_id", False),
            ("Permanent Meta Page Token:", "meta_token", True),
        ]
        for label, key, secret in fields:
            ttk.Label(f, text=label).pack(anchor="w", pady=(4, 1))
            ttk.Entry(f, textvariable=self.vars[key], show="*" if secret else "").pack(fill="x", pady=(0, 4))

        file_fields = [
            ("Google OAuth JSON (client_secret.json):", "yt_secret", "Select Google JSON"),
            ("Optional TikTok cookies.txt (for 1080p):", "cookies_path", "Select cookies.txt"),
        ]
        for label, key, title in file_fields:
            ttk.Label(f, text=label).pack(anchor="w", pady=(4, 1))
            row = ttk.Frame(f)
            row.pack(fill="x", pady=(0, 4))
            ttk.Entry(row, textvariable=self.vars[key]).pack(side="left", fill="x", expand=True, padx=(0, 6))
            ttk.Button(row, text="Browse", style="Dark.TButton", command=lambda k=key, t=title: self.pick_file(k, t)).pack(side="right")

        drop_row = ttk.Frame(f)
        drop_row.pack(fill="x", pady=8)
        drops = [
            ("YouTube Privacy:", "yt_privacy", ["public", "unlisted", "private"]),
            ("Trial Reel Strategy:", "trial_strategy", list(STRATEGIES.keys())),
            ("Check Interval:", "interval", list(INTERVALS.keys())),
        ]
        for idx, (lbl, key, opts) in enumerate(drops):
            col = ttk.Frame(drop_row)
            col.pack(side="left", fill="x", expand=True, padx=(0 if idx == 0 else 6, 0))
            ttk.Label(col, text=lbl).pack(anchor="w")
            ttk.Combobox(col, textvariable=self.vars[key], values=opts, state="readonly").pack(fill="x")

        btn_row = ttk.Frame(f)
        btn_row.pack(fill="x", pady=10)
        self.start_btn = ttk.Button(btn_row, text="Start Background Sync", style="Accent.TButton", command=self.toggle_sync)
        self.start_btn.pack(side="left", expand=True, fill="x", padx=(0, 6))
        ttk.Button(btn_row, text="Run Now (Test)", style="Dark.TButton", command=self.run_once_thread).pack(side="right", expand=True, fill="x")

        self.log_box = tk.Text(f, height=11, bg="#18181b", fg="#a1a1aa", font=("Menlo", 10), relief="flat", padx=8, pady=8)
        self.log_box.pack(fill="both", expand=True, pady=(4, 0))
        self.log("Ready. Configure your keys and click 'Run Now (Test)' or 'Start Background Sync'.")

    def pick_file(self, key, title):
        p = filedialog.askopenfilename(title=title)
        if p:
            self.vars[key].set(p)

    def log(self, msg):
        ts = time.strftime("%H:%M:%S")
        self.root.after(0, lambda: (self.log_box.insert("end", f"[{ts}] {msg}\n"), self.log_box.see("end")))

    def toggle_sync(self):
        self.save_cfg()
        if not self.running:
            self.running = True
            self.start_btn.config(text="Stop Background Sync")
            threading.Thread(target=self.loop_worker, daemon=True).start()
        else:
            self.running = False
            self.start_btn.config(text="Start Background Sync")
            self.log("Background sync stopped.")

    def loop_worker(self):
        while self.running:
            self.process_pipeline()
            wait_s = INTERVALS.get(self.vars["interval"].get(), 900)
            for _ in range(wait_s):
                if not self.running:
                    return
                time.sleep(1)

    def run_once_thread(self):
        self.save_cfg()
        threading.Thread(target=self.process_pipeline, daemon=True).start()

    def get_yt_service(self):
        creds = None
        if YT_TOKEN_FILE.exists():
            creds = Credentials.from_authorized_user_file(str(YT_TOKEN_FILE), SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(self.cfg["yt_secret"], SCOPES)
                creds = flow.run_local_server(port=0)
            YT_TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
        return build("youtube", "v3", credentials=creds)

    def process_pipeline(self):
        user = self.cfg.get("tiktok_user", "").lstrip("@")
        if not user:
            self.log("Error: Please enter your TikTok username.")
            return
        raw_mp4 = APP_DIR / "raw_tiktok.mp4"
        final_mp4 = APP_DIR / "latest_tiktok.mp4"
        for p in [raw_mp4, final_mp4]:
            if p.exists():
                p.unlink()

        self.log(f"Checking @{user} for new TikToks...")
        ydl_opts = {
            "outtmpl": str(APP_DIR / "raw_tiktok.%(ext)s"),
            "format": "best[height>=1080]/best[ext=mp4]/best",
            "playlistend": 8,
            "max_downloads": 1,
            "download_archive": str(ARCHIVE_FILE),
            "match_filter": yt_dlp.utils.match_filter_func("vcodec != none"),
            "quiet": True,
            "no_warnings": True,
        }
        if self.cfg.get("cookies_path") and Path(self.cfg["cookies_path"]).exists():
            ydl_opts["cookiefile"] = self.cfg["cookies_path"]

        info_data = {}
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                res = ydl.extract_info(f"https://www.tiktok.com/@{user}", download=True)
                entries = res.get("entries", [res]) if res else []
                for e in entries:
                    if e and raw_mp4.exists():
                        info_data = e
                        break
        except yt_dlp.utils.MaxDownloadsReached:
            pass
        except Exception as e:
            self.log(f"TikTok check error: {e}")
            return

        if not raw_mp4.exists():
            self.log("No new videos found.")
            return

        ffmpeg = get_bin("ffmpeg")
        self.log("Converting to 1080p H.264 + 256k AAC...")
        cmd = [
            ffmpeg, "-y", "-i", str(raw_mp4),
            "-c:v", "libx264", "-crf", "17", "-preset", "veryfast", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart", str(final_mp4)
        ]
        if subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode != 0:
            shutil.copy(raw_mp4, final_mp4)
        raw_mp4.unlink(missing_ok=True)

        caption = info_data.get("description") or "New Music!"
        title = (info_data.get("title") or caption)[:95]

        if self.cfg.get("yt_secret"):
            try:
                self.log("Uploading to YouTube Shorts...")
                yt = self.get_yt_service()
                body = {
                    "snippet": {"title": title, "description": caption, "categoryId": "10"},
                    "status": {"privacyStatus": self.cfg.get("yt_privacy", "public"), "selfDeclaredMadeForKids": False},
                }
                yt.videos().insert(
                    part="snippet,status",
                    body=body,
                    media_body=MediaFileUpload(str(final_mp4), chunksize=-1, resumable=True),
                ).execute()
                self.log("YouTube Shorts uploaded!")
            except Exception as e:
                self.log(f"YouTube error: {e}")

        token = self.cfg.get("meta_token")
        ig_id = self.cfg.get("ig_id")
        fb_id = self.cfg.get("fb_id")
        if token and (ig_id or fb_id):
            httpd = HTTPServer(("127.0.0.1", 0), QuietHandler)
            port = httpd.server_address[1]
            threading.Thread(target=httpd.serve_forever, daemon=True).start()
            cf = subprocess.Popen(
                [get_bin("cloudflared"), "tunnel", "--url", f"http://127.0.0.1:{port}"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            tunnel_url = None
            for _ in range(30):
                line = cf.stdout.readline()
                m = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", line)
                if m:
                    tunnel_url = f"{m.group(0)}/latest_tiktok.mp4"
                    break
            if tunnel_url:
                if ig_id:
                    try:
                        self.log("Creating Instagram Trial Reel...")
                        strat = STRATEGIES.get(self.cfg.get("trial_strategy"), "SS_PERFORMANCE")
                        r = requests.post(
                            f"https://graph.facebook.com/v21.0/{ig_id}/media",
                            json={
                                "media_type": "REELS",
                                "video_url": tunnel_url,
                                "caption": caption,
                                "trial_params": {"graduation_strategy": strat},
                                "access_token": token,
                            },
                        ).json()
                        cid = r.get("id")
                        if cid:
                            time.sleep(60)
                            requests.post(
                                f"https://graph.facebook.com/v21.0/{ig_id}/media_publish",
                                params={"creation_id": cid, "access_token": token},
                            )
                            self.log("Instagram Trial Reel published!")
                    except Exception as e:
                        self.log(f"Instagram error: {e}")
                if fb_id:
                    try:
                        self.log("Publishing to Facebook Page...")
                        requests.post(
                            f"https://graph-video.facebook.com/v21.0/{fb_id}/videos",
                            params={"file_url": tunnel_url, "description": caption, "access_token": token},
                        )
                        self.log("Facebook Page Reel published!")
                    except Exception as e:
                        self.log(f"Facebook error: {e}")
                time.sleep(15)
            cf.terminate()
            httpd.shutdown()
        self.log("Cycle complete!")

if __name__ == "__main__":
    root = tk.Tk()
    RepurposerApp(root)
    root.mainloop()
