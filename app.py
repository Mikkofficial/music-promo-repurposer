import os
import sys
import json
import time
import glob
import shutil
import threading
import subprocess
import http.server
import socketserver
import re
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

import requests
import yt_dlp
from PIL import Image, ImageDraw
import pystray
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

APP_NAME = "Music Promo Repurposer"
DATA_DIR = Path(os.getenv("APPDATA", Path.home())) / "MusicPromoRepurposer"
DATA_DIR.mkdir(parents=True, exist_ok=True)

CONFIG_FILE = DATA_DIR / "config.json"
HISTORY_FILE = DATA_DIR / "tiktok_history.txt"
YT_TOKEN_FILE = DATA_DIR / "youtube_token.json"
WORK_DIR = DATA_DIR / "tmp"
WORK_DIR.mkdir(parents=True, exist_ok=True)

YT_SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def get_bundled_binary(name: str) -> str:
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).parent
    candidate = base / name
    if candidate.exists():
        return str(candidate)
    return name


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, directory=None, **kwargs):
        super().__init__(*args, directory=directory, **kwargs)

    def log_message(self, format, *args):
        pass


class TempVideoHost:
    def __init__(self, directory: Path, log_fn):
        self.directory = directory
        self.log = log_fn
        self.httpd = None
        self.server_thread = None
        self.cf_proc = None
        self.public_url = None

    def start(self, filename: str) -> str:
        handler = lambda *args, **kwargs: QuietHandler(*args, directory=str(self.directory), **kwargs)
        self.httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
        port = self.httpd.server_address[1]
        self.server_thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.server_thread.start()

        cf_bin = get_bundled_binary("cloudflared.exe" if os.name == "nt" else "cloudflared")
        self.cf_proc = subprocess.Popen(
            [cf_bin, "tunnel", "--url", f"http://127.0.0.1:{port}", "--no-autoupdate"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )

        deadline = time.time() + 25
        while time.time() < deadline:
            line = self.cf_proc.stdout.readline()
            if not line:
                break
            match = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", line)
            if match:
                self.public_url = f"{match.group(0)}/{filename}"
                return self.public_url

        raise RuntimeError("Could not start temporary Cloudflare tunnel within 25 seconds.")

    def stop(self):
        if self.cf_proc:
            try:
                self.cf_proc.terminate()
            except Exception:
                pass
            self.cf_proc = None
        if self.httpd:
            try:
                self.httpd.shutdown()
                self.httpd.server_close()
            except Exception:
                pass
            self.httpd = None


class RepurposerApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(APP_NAME)
        self.root.geometry("680x660")
        self.root.configure(bg="#121218")
        self.root.protocol("WM_DELETE_WINDOW", self.hide_to_tray)

        self.running = False
        self.stop_event = threading.Event()
        self.worker_thread = None
        self.tray_icon = None

        self.config = self.load_config()
        self.build_ui()
        self.setup_tray()

    def load_config(self) -> dict:
        if CONFIG_FILE.exists():
            try:
                return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {
            "tiktok_username": "",
            "ig_business_id": "",
            "fb_page_id": "",
            "meta_page_token": "",
            "yt_client_secret_path": "",
            "yt_privacy": "public",
            "ig_trial_reel": True,
            "interval_minutes": 15,
            "enable_youtube": True,
            "enable_instagram": True,
            "enable_facebook": True,
        }

    def save_config(self):
        cfg = {
            "tiktok_username": self.var_tiktok.get().strip().lstrip("@"),
            "ig_business_id": self.var_ig_id.get().strip(),
            "fb_page_id": self.var_fb_id.get().strip(),
            "meta_page_token": self.var_meta_token.get().strip(),
            "yt_client_secret_path": self.var_yt_secret.get().strip(),
            "yt_privacy": self.var_yt_privacy.get(),
            "ig_trial_reel": self.var_ig_trial.get(),
            "interval_minutes": max(5, int(self.var_interval.get() or 15)),
            "enable_youtube": self.var_en_yt.get(),
            "enable_instagram": self.var_en_ig.get(),
            "enable_facebook": self.var_en_fb.get(),
        }
        self.config = cfg
        CONFIG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
        return cfg

    def build_ui(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background="#121218")
        style.configure("TLabel", background="#121218", foreground="#eaeaf2", font=("Segoe UI", 10))
        style.configure("Header.TLabel", background="#121218", foreground="#ffffff", font=("Segoe UI", 14, "bold"))
        style.configure("Sub.TLabel", background="#121218", foreground="#9aa0b4", font=("Segoe UI", 9))
        style.configure("TCheckbutton", background="#121218", foreground="#eaeaf2", font=("Segoe UI", 10))
        style.configure("TButton", font=("Segoe UI", 10, "bold"), padding=6)

        main = ttk.Frame(self.root, padding=18)
        main.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main, text="Music Promo Repurposer", style="Header.TLabel").pack(anchor="w")
        ttk.Label(
            main,
            text="Automatically reposts your new TikToks to YouTube Shorts, Instagram Trial Reels & Facebook Reels.",
            style="Sub.TLabel",
        ).pack(anchor="w", pady=(0, 14))

        form = ttk.Frame(main)
        form.pack(fill=tk.X)
        form.columnconfigure(1, weight=1)

        self.var_tiktok = tk.StringVar(value=self.config.get("tiktok_username", ""))
        self.var_ig_id = tk.StringVar(value=self.config.get("ig_business_id", ""))
        self.var_fb_id = tk.StringVar(value=self.config.get("fb_page_id", ""))
        self.var_meta_token = tk.StringVar(value=self.config.get("meta_page_token", ""))
        self.var_yt_secret = tk.StringVar(value=self.config.get("yt_client_secret_path", ""))
        self.var_yt_privacy = tk.StringVar(value=self.config.get("yt_privacy", "public"))
        self.var_interval = tk.StringVar(value=str(self.config.get("interval_minutes", 15)))
        self.var_ig_trial = tk.BooleanVar(value=self.config.get("ig_trial_reel", True))
        self.var_en_yt = tk.BooleanVar(value=self.config.get("enable_youtube", True))
        self.var_en_ig = tk.BooleanVar(value=self.config.get("enable_instagram", True))
        self.var_en_fb = tk.BooleanVar(value=self.config.get("enable_facebook", True))

        fields = [
            ("TikTok Username (no @):", self.var_tiktok, False),
            ("Instagram Business ID:", self.var_ig_id, False),
            ("Facebook Page ID:", self.var_fb_id, False),
            ("Meta Permanent Page Token:", self.var_meta_token, True),
        ]

        for idx, (label, var, secret) in enumerate(fields):
            ttk.Label(form, text=label).grid(row=idx, column=0, sticky="w", pady=5, padx=(0, 10))
            entry = tk.Entry(
                form,
                textvariable=var,
                show="*" if secret else "",
                bg="#1e1e28",
                fg="#ffffff",
                insertbackground="#ffffff",
                relief=tk.FLAT,
                font=("Segoe UI", 10),
            )
            entry.grid(row=idx, column=1, sticky="ew", pady=5, ipady=5)

        # YouTube client_secret.json picker
        ttk.Label(form, text="YouTube client_secret.json:").grid(row=4, column=0, sticky="w", pady=5, padx=(0, 10))
        yt_row = ttk.Frame(form)
        yt_row.grid(row=4, column=1, sticky="ew", pady=5)
        yt_row.columnconfigure(0, weight=1)
        yt_entry = tk.Entry(
            yt_row,
            textvariable=self.var_yt_secret,
            bg="#1e1e28",
            fg="#ffffff",
            insertbackground="#ffffff",
            relief=tk.FLAT,
            font=("Segoe UI", 10),
        )
        yt_entry.grid(row=0, column=0, sticky="ew", ipady=5, padx=(0, 6))
        ttk.Button(yt_row, text="Browse...", command=self.browse_yt_secret).grid(row=0, column=1)
        ttk.Button(yt_row, text="Connect YouTube", command=self.connect_youtube).grid(row=0, column=2, padx=(6, 0))

        # Options row
        opts = ttk.Frame(main)
        opts.pack(fill=tk.X, pady=(10, 6))
        ttk.Checkbutton(opts, text="YouTube Shorts", variable=self.var_en_yt).pack(side=tk.LEFT, padx=(0, 14))
        ttk.Checkbutton(opts, text="Instagram Reels", variable=self.var_en_ig).pack(side=tk.LEFT, padx=(0, 14))
        ttk.Checkbutton(opts, text="Facebook Reels", variable=self.var_en_fb).pack(side=tk.LEFT, padx=(0, 14))
        ttk.Checkbutton(opts, text="IG Trial Reel Mode", variable=self.var_ig_trial).pack(side=tk.LEFT)

        opts2 = ttk.Frame(main)
        opts2.pack(fill=tk.X, pady=(0, 12))
        ttk.Label(opts2, text="Check every (min):").pack(side=tk.LEFT, padx=(0, 6))
        tk.Entry(
            opts2,
            textvariable=self.var_interval,
            width=6,
            bg="#1e1e28",
            fg="#ffffff",
            insertbackground="#ffffff",
            relief=tk.FLAT,
            font=("Segoe UI", 10),
        ).pack(side=tk.LEFT, ipady=3, padx=(0, 18))

        ttk.Label(opts2, text="YouTube Visibility:").pack(side=tk.LEFT, padx=(0, 6))
        ttk.Combobox(
            opts2,
            textvariable=self.var_yt_privacy,
            values=["public", "unlisted", "private"],
            state="readonly",
            width=10,
        ).pack(side=tk.LEFT)

        # Action buttons
        btns = ttk.Frame(main)
        btns.pack(fill=tk.X, pady=(4, 10))
        self.btn_start = ttk.Button(btns, text="Start Auto-Poster", command=self.start_worker)
        self.btn_start.pack(side=tk.LEFT, padx=(0, 8))

        self.btn_stop = ttk.Button(btns, text="Stop", command=self.stop_worker, state=tk.DISABLED)
        self.btn_stop.pack(side=tk.LEFT, padx=(0, 8))

        ttk.Button(btns, text="Run Check Now", command=self.run_once_async).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(btns, text="Save Settings", command=self.on_save_clicked).pack(side=tk.LEFT)

        # Log console
        ttk.Label(main, text="Activity Log:", style="Sub.TLabel").pack(anchor="w")
        self.log_box = scrolledtext.ScrolledText(
            main,
            height=13,
            bg="#0c0c10",
            fg="#b8f2c8",
            font=("Consolas", 9),
            relief=tk.FLAT,
            state=tk.DISABLED,
        )
        self.log_box.pack(fill=tk.BOTH, expand=True, pady=(4, 0))
        self.log("Ready. Configure your accounts above and click 'Start Auto-Poster'.")

    def log(self, msg: str):
        ts = time.strftime("%H:%M:%S")
        line = f"[{ts}] {msg}\n"

        def append():
            self.log_box.configure(state=tk.NORMAL)
            self.log_box.insert(tk.END, line)
            self.log_box.see(tk.END)
            self.log_box.configure(state=tk.DISABLED)

        self.root.after(0, append)

    def on_save_clicked(self):
        self.save_config()
        self.log("Settings saved.")

    def browse_yt_secret(self):
        path = filedialog.askopenfilename(
            title="Select Google client_secret.json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if path:
            self.var_yt_secret.set(path)
            self.save_config()

    def get_youtube_service(self):
        creds = None
        if YT_TOKEN_FILE.exists():
            creds = Credentials.from_authorized_user_file(str(YT_TOKEN_FILE), YT_SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                secret_path = self.config.get("yt_client_secret_path")
                if not secret_path or not Path(secret_path).exists():
                    raise RuntimeError("YouTube client_secret.json file not selected.")
                flow = InstalledAppFlow.from_client_secrets_file(secret_path, YT_SCOPES)
                creds = flow.run_local_server(port=0)
            YT_TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
        return build("youtube", "v3", credentials=creds)

    def connect_youtube(self):
        self.save_config()
        def task():
            try:
                self.log("Opening browser for Google / YouTube authorization...")
                self.get_youtube_service()
                self.log("YouTube connected successfully!")
            except Exception as exc:
                self.log(f"YouTube connection failed: {exc}")
        threading.Thread(target=task, daemon=True).start()

    def start_worker(self):
        cfg = self.save_config()
        if not cfg["tiktok_username"]:
            messagebox.showerror(APP_NAME, "Please enter your TikTok username first.")
            return
        if self.running:
            return
        self.running = True
        self.stop_event.clear()
        self.btn_start.configure(state=tk.DISABLED)
        self.btn_stop.configure(state=tk.NORMAL)
        self.worker_thread = threading.Thread(target=self.loop_worker, daemon=True)
        self.worker_thread.start()
        self.log(f"Auto-Poster started (checking @{cfg['tiktok_username']} every {cfg['interval_minutes']} min).")

    def stop_worker(self):
        self.running = False
        self.stop_event.set()
        self.btn_start.configure(state=tk.NORMAL)
        self.btn_stop.configure(state=tk.DISABLED)
        self.log("Auto-Poster stopped.")

    def run_once_async(self):
        self.save_config()
        threading.Thread(target=self.process_cycle, daemon=True).start()

    def loop_worker(self):
        while not self.stop_event.is_set():
            self.process_cycle()
            wait_sec = self.config.get("interval_minutes", 15) * 60
            self.stop_event.wait(wait_sec)

    def process_cycle(self):
        cfg = self.config
        user = cfg.get("tiktok_username", "").strip()
        if not user:
            self.log("TikTok username is empty. Skipping check.")
            return

        self.log(f"Checking https://www.tiktok.com/@{user} for new videos...")
        for f in WORK_DIR.glob("latest_tiktok.*"):
            try:
                f.unlink()
            except Exception:
                pass

        ffmpeg_loc = str(Path(get_bundled_binary("ffmpeg.exe")).parent)
        ydl_opts = {
            "playlistend": 8,
            "dateafter": "now-1day",
            "max_downloads": 1,
            "download_archive": str(HISTORY_FILE),
            "writeinfojson": True,
            "format": "bv*[vcodec^=avc1]+ba[ext=m4a]/b[vcodec^=avc1]/b[ext=mp4]",
            "merge_output_format": "mp4",
            "ffmpeg_location": ffmpeg_loc,
            "outtmpl": str(WORK_DIR / "latest_tiktok.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
            "ignoreerrors": True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([f"https://www.tiktok.com/@{user}"])
        except yt_dlp.utils.MaxDownloadsReached:
            pass
        except Exception as exc:
            self.log(f"TikTok check error: {exc}")
            return

        mp4_path = WORK_DIR / "latest_tiktok.mp4"
        info_path = WORK_DIR / "latest_tiktok.info.json"
        if not mp4_path.exists():
            self.log("No new TikTok videos found in the last 24 hours.")
            return

        title = "New Music Short"
        caption = "New Music!"
        if info_path.exists():
            try:
                meta = json.loads(info_path.read_text(encoding="utf-8"))
                title = (meta.get("title") or "New Music Short")[:95]
                caption = meta.get("description") or "New Music!"
            except Exception:
                pass

        self.log(f"Downloaded new TikTok: {title}")

        # 1. YouTube Shorts
        if cfg.get("enable_youtube"):
            try:
                self.upload_youtube(mp4_path, title, caption, cfg.get("yt_privacy", "public"))
                self.log("YouTube Shorts: Published successfully!")
            except Exception as exc:
                self.log(f"YouTube Shorts failed: {exc}")

        # 2. Instagram & Facebook via temporary Cloudflare tunnel
        need_meta = (cfg.get("enable_instagram") or cfg.get("enable_facebook")) and cfg.get("meta_page_token")
        if need_meta:
            tunnel = TempVideoHost(WORK_DIR, self.log)
            try:
                self.log("Opening temporary HTTPS link for Meta servers...")
                video_url = tunnel.start("latest_tiktok.mp4")

                if cfg.get("enable_instagram") and cfg.get("ig_business_id"):
                    try:
                        self.upload_instagram(
                            cfg["ig_business_id"],
                            cfg["meta_page_token"],
                            video_url,
                            caption,
                            cfg.get("ig_trial_reel", True),
                        )
                        self.log("Instagram Reel: Published successfully!")
                    except Exception as exc:
                        self.log(f"Instagram Reel failed: {exc}")

                if cfg.get("enable_facebook") and cfg.get("fb_page_id"):
                    try:
                        self.upload_facebook(
                            cfg["fb_page_id"],
                            cfg["meta_page_token"],
                            video_url,
                            caption,
                        )
                        self.log("Facebook Page Reel: Published successfully!")
                    except Exception as exc:
                        self.log(f"Facebook Page Reel failed: {exc}")
            except Exception as exc:
                self.log(f"Temporary tunnel error: {exc}")
            finally:
                tunnel.stop()
                self.log("Temporary HTTPS link closed.")

    def upload_youtube(self, video_path: Path, title: str, description: str, privacy: str):
        yt = self.get_youtube_service()
        body = {
            "snippet": {
                "title": title,
                "description": description,
                "categoryId": "10",
            },
            "status": {
                "privacyStatus": privacy,
                "selfDeclaredMadeForKids": False,
            },
        }
        media = MediaFileUpload(str(video_path), chunksize=-1, resumable=True, mimetype="video/mp4")
        req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
        resp = None
        while resp is None:
            _, resp = req.next_chunk()

    def upload_instagram(self, ig_id: str, token: str, video_url: str, caption: str, trial: bool):
        payload = {
            "media_type": "REELS",
            "video_url": video_url,
            "caption": caption,
            "access_token": token,
        }
        if trial:
            payload["trial_params"] = {"graduation_strategy": "SS_PERFORMANCE"}

        res = requests.post(f"https://graph.facebook.com/v21.0/{ig_id}/media", json=payload, timeout=30)
        data = res.json()
        if "id" not in data:
            raise RuntimeError(str(data))
        creation_id = data["id"]

        for _ in range(18):
            time.sleep(5)
            st = requests.get(
                f"https://graph.facebook.com/v21.0/{creation_id}",
                params={"fields": "status_code,status", "access_token": token},
                timeout=20,
            ).json()
            code = st.get("status_code")
            if code == "FINISHED":
                break
            if code == "ERROR":
                raise RuntimeError(str(st))

        pub = requests.post(
            f"https://graph.facebook.com/v21.0/{ig_id}/media_publish",
            params={"creation_id": creation_id, "access_token": token},
            timeout=30,
        ).json()
        if "id" not in pub:
            raise RuntimeError(str(pub))

    def upload_facebook(self, page_id: str, token: str, video_url: str, description: str):
        res = requests.post(
            f"https://graph-video.facebook.com/v21.0/{page_id}/videos",
            params={
                "file_url": video_url,
                "description": description,
                "access_token": token,
            },
            timeout=60,
        ).json()
        if "id" not in res:
            raise RuntimeError(str(res))

    def setup_tray(self):
        img = Image.new("RGB", (64, 64), color=(18, 18, 24))
        draw = ImageDraw.Draw(img)
        draw.ellipse((10, 10, 54, 54), fill=(99, 102, 241))
        menu = pystray.Menu(
            pystray.MenuItem("Open Window", self.show_window, default=True),
            pystray.MenuItem("Run Check Now", lambda: self.run_once_async()),
            pystray.MenuItem("Quit", self.quit_app),
        )
        self.tray_icon = pystray.Icon(APP_NAME, img, APP_NAME, menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def hide_to_tray(self):
        self.root.withdraw()

    def show_window(self):
        self.root.after(0, self.root.deiconify)

    def quit_app(self):
        self.stop_worker()
        if self.tray_icon:
            self.tray_icon.stop()
        self.root.after(0, self.root.destroy)


if __name__ == "__main__":
    root = tk.Tk()
    app = RepurposerApp(root)
    root.mainloop()
