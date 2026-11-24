import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.parse
from datetime import datetime, timedelta
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

import imageio_ffmpeg
import requests
import yt_dlp

try:
    import pystray
    from PIL import Image, ImageDraw
    HAS_TRAY = True
except Exception:
    HAS_TRAY = False

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    HAS_GOOGLE = True
except Exception:
    HAS_GOOGLE = False

APP_DIR = Path.home() / "MusicPromoRepurposer"
APP_DIR.mkdir(parents=True, exist_ok=True)

CONFIG_FILE = APP_DIR / "config.json"
HISTORY_FILE = APP_DIR / "tiktok_history.txt"
YT_TOKEN_FILE = APP_DIR / "youtube_token.json"
WORK_DIR = APP_DIR / "media"
WORK_DIR.mkdir(parents=True, exist_ok=True)

YOUTUBE_SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

TRIAL_STRATEGY_MAP = {
    "Auto-Share to Followers": "SS_PERFORMANCE",
    "Manual Approval Only": "MANUAL",
}
REVERSE_TRIAL_STRATEGY_MAP = {v: k for k, v in TRIAL_STRATEGY_MAP.items()}

INTERVAL_MAP = {
    "Every 5 minutes": 5,
    "Every 15 minutes": 15,
    "Every 30 minutes": 30,
    "Every 60 minutes": 60,
    "Every 2 hours": 120,
    "Every 6 hours": 360,
}


def get_bundled_binary(base_name: str) -> str:
    exe_name = f"{base_name}.exe" if sys.platform == "win32" else base_name
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        candidate = Path(sys._MEIPASS) / exe_name
        if candidate.exists():
            return str(candidate)
    local_candidate = Path(__file__).resolve().parent / exe_name
    if local_candidate.exists():
        return str(local_candidate)
    return exe_name


class QuietHTTPHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, directory=None, **kwargs):
        super().__init__(*args, directory=str(WORK_DIR), **kwargs)

    def log_message(self, format, *args):
        pass


class MusicPromoRepurposerApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Music Promo Repurposer — TikTok to Shorts & Reels")
        self.root.geometry("760x730")
        self.root.minsize(700, 660)
        self.root.configure(bg="#18181b")

        self.running = False
        self.worker_thread = None
        self.stop_event = threading.Event()
        self.tray_icon = None

        self._setup_styles()
        self._build_ui()
        self._load_config()
        self._setup_tray()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _setup_styles(self):
        style = ttk.Style(self.root)
        # Use 'clam' theme so macOS Aqua never turns buttons white on window focus
        try:
            style.theme_use("clam")
        except Exception:
            pass

        bg_main = "#18181b"
        bg_card = "#27272a"
        bg_btn = "#3f3f46"
        bg_btn_hover = "#52525b"
        bg_accent = "#2563eb"
        bg_accent_hover = "#1d4ed8"
        bg_danger = "#dc2626"
        bg_danger_hover = "#b91c1c"
        fg_text = "#f4f4f5"
        fg_muted = "#a1a1aa"

        style.configure("TFrame", background=bg_main)
        style.configure("TLabel", background=bg_main, foreground=fg_text, font=("Helvetica", 11))
        style.configure("Header.TLabel", background=bg_main, foreground="#ffffff", font=("Helvetica", 18, "bold"))
        style.configure("SubHeader.TLabel", background=bg_main, foreground=fg_muted, font=("Helvetica", 11))
        style.configure("Field.TLabel", background=bg_main, foreground="#e4e4e7", font=("Helvetica", 11, "bold"))

        style.configure(
            "TEntry",
            fieldbackground=bg_card,
            foreground=fg_text,
            insertcolor=fg_text,
            bordercolor="#3f3f46",
            lightcolor="#3f3f46",
            darkcolor="#3f3f46",
            padding=6,
        )

        style.configure(
            "TCombobox",
            fieldbackground=bg_card,
            background=bg_btn,
            foreground=fg_text,
            arrowcolor=fg_text,
            bordercolor="#3f3f46",
            lightcolor="#3f3f46",
            darkcolor="#3f3f46",
            padding=5,
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", bg_card)],
            selectbackground=[("readonly", bg_card)],
            selectforeground=[("readonly", fg_text)],
            background=[("active", bg_btn_hover)],
        )

        style.configure(
            "TCheckbutton",
            background=bg_main,
            foreground=fg_text,
            font=("Helvetica", 11, "bold"),
        )
        style.map(
            "TCheckbutton",
            background=[("active", bg_main)],
            foreground=[("active", "#ffffff")],
        )

        style.configure(
            "Dark.TButton",
            background=bg_btn,
            foreground="#ffffff",
            bordercolor="#52525b",
            lightcolor=bg_btn,
            darkcolor=bg_btn,
            focuscolor="none",
            font=("Helvetica", 11, "bold"),
            padding=(12, 7),
        )
        style.map(
            "Dark.TButton",
            background=[("disabled", "#27272a"), ("pressed", "#27272a"), ("active", bg_btn_hover)],
            foreground=[("disabled", "#71717a"), ("active", "#ffffff")],
        )

        style.configure(
            "Primary.TButton",
            background=bg_accent,
            foreground="#ffffff",
            bordercolor=bg_accent,
            lightcolor=bg_accent,
            darkcolor=bg_accent,
            focuscolor="none",
            font=("Helvetica", 11, "bold"),
            padding=(14, 7),
        )
        style.map(
            "Primary.TButton",
            background=[("disabled", "#1e3a8a"), ("pressed", "#1e40af"), ("active", bg_accent_hover)],
            foreground=[("disabled", "#93c5fd"), ("active", "#ffffff")],
        )

        style.configure(
            "Danger.TButton",
            background=bg_danger,
            foreground="#ffffff",
            bordercolor=bg_danger,
            lightcolor=bg_danger,
            darkcolor=bg_danger,
            focuscolor="none",
            font=("Helvetica", 11, "bold"),
            padding=(14, 7),
        )
        style.map(
            "Danger.TButton",
            background=[("disabled", "#451a1a"), ("pressed", "#991b1b"), ("active", bg_danger_hover)],
            foreground=[("disabled", "#71717a"), ("active", "#ffffff")],
        )

    def _build_ui(self):
        container = ttk.Frame(self.root, padding=20)
        container.pack(fill=tk.BOTH, expand=True)

        ttk.Label(container, text="Music Promo Repurposer", style="Header.TLabel").pack(anchor="w")
        ttk.Label(
            container,
            text="Auto-repost new TikToks to YouTube Shorts, Instagram Trial Reels & Facebook Reels",
            style="SubHeader.TLabel",
        ).pack(anchor="w", pady=(2, 14))

        self.tiktok_var = tk.StringVar()
        self.ig_id_var = tk.StringVar()
        self.fb_id_var = tk.StringVar()
        self.meta_token_var = tk.StringVar()
        self.yt_secret_var = tk.StringVar()

        self._add_labeled_entry(container, "TikTok Username (without @):", self.tiktok_var)
        self._add_labeled_entry(container, "Instagram Business Account ID (178414...):", self.ig_id_var)
        self._add_labeled_entry(container, "Facebook Page ID:", self.fb_id_var)
        self._add_labeled_entry(container, "Permanent Meta Page Token:", self.meta_token_var, show="*")

        # YouTube JSON picker row
        ttk.Label(container, text="YouTube Google OAuth JSON (client_secret.json):", style="Field.TLabel").pack(
            anchor="w", pady=(6, 2)
        )
        yt_row = ttk.Frame(container)
        yt_row.pack(fill=tk.X, pady=(0, 8))
        yt_entry = ttk.Entry(yt_row, textvariable=self.yt_secret_var)
        yt_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        ttk.Button(yt_row, text="Browse...", style="Dark.TButton", command=self._browse_yt_secret).pack(side=tk.RIGHT)

        # Platform toggles
        toggles_row = ttk.Frame(container)
        toggles_row.pack(fill=tk.X, pady=(6, 8))
        self.enable_yt = tk.BooleanVar(value=True)
        self.enable_ig = tk.BooleanVar(value=True)
        self.enable_fb = tk.BooleanVar(value=True)

        ttk.Checkbutton(toggles_row, text="YouTube Shorts", variable=self.enable_yt).pack(side=tk.LEFT, padx=(0, 18))
        ttk.Checkbutton(toggles_row, text="IG Trial Reels", variable=self.enable_ig).pack(side=tk.LEFT, padx=(0, 18))
        ttk.Checkbutton(toggles_row, text="Facebook Reels", variable=self.enable_fb).pack(side=tk.LEFT)

        # Settings row: YT Privacy | IG Trial Mode | Check Interval
        settings_row = ttk.Frame(container)
        settings_row.pack(fill=tk.X, pady=(4, 14))

        ttk.Label(settings_row, text="YT Privacy:", style="Field.TLabel").pack(side=tk.LEFT, padx=(0, 6))
        self.yt_privacy_var = tk.StringVar(value="private")
        yt_cb = ttk.Combobox(
            settings_row,
            textvariable=self.yt_privacy_var,
            values=["private", "unlisted", "public"],
            state="readonly",
            width=9,
        )
        yt_cb.pack(side=tk.LEFT, padx=(0, 14))

        ttk.Label(settings_row, text="IG Trial Mode:", style="Field.TLabel").pack(side=tk.LEFT, padx=(0, 6))
        self.ig_strategy_var = tk.StringVar(value="Auto-Share to Followers")
        ig_cb = ttk.Combobox(
            settings_row,
            textvariable=self.ig_strategy_var,
            values=list(TRIAL_STRATEGY_MAP.keys()),
            state="readonly",
            width=21,
        )
        ig_cb.pack(side=tk.LEFT, padx=(0, 14))

        ttk.Label(settings_row, text="Check Interval:", style="Field.TLabel").pack(side=tk.LEFT, padx=(0, 6))
        self.interval_var = tk.StringVar(value="Every 15 minutes")
        int_cb = ttk.Combobox(
            settings_row,
            textvariable=self.interval_var,
            values=list(INTERVAL_MAP.keys()),
            state="readonly",
            width=16,
        )
        int_cb.pack(side=tk.LEFT)

        # Action Buttons
        btn_row = ttk.Frame(container)
        btn_row.pack(fill=tk.X, pady=(2, 12))

        self.start_btn = ttk.Button(
            btn_row, text="Start Auto-Sync", style="Primary.TButton", command=self.start_loop
        )
        self.start_btn.pack(side=tk.LEFT, padx=(0, 8))

        self.stop_btn = ttk.Button(
            btn_row, text="Stop", style="Danger.TButton", command=self.stop_loop, state=tk.DISABLED
        )
        self.stop_btn.pack(side=tk.LEFT, padx=(0, 8))

        self.test_btn = ttk.Button(
            btn_row, text="Run Now (Test)", style="Dark.TButton", command=self.run_once_manual
        )
        self.test_btn.pack(side=tk.LEFT, padx=(0, 8))

        self.yt_auth_btn = ttk.Button(
            btn_row, text="Connect YouTube", style="Dark.TButton", command=self.connect_youtube
        )
        self.yt_auth_btn.pack(side=tk.RIGHT)

        # Activity Log
        ttk.Label(container, text="Activity Log", style="Field.TLabel").pack(anchor="w", pady=(4, 4))
        self.log_box = scrolledtext.ScrolledText(
            container,
            height=13,
            bg="#09090b",
            fg="#e4e4e7",
            insertbackground="#ffffff",
            font=("Courier", 10),
            relief=tk.FLAT,
            padx=10,
            pady=10,
        )
        self.log_box.pack(fill=tk.BOTH, expand=True)
        self.log("Ready. Enter your details above and click 'Run Now (Test)' or 'Start Auto-Sync'.")

    def _add_labeled_entry(self, parent, label_text: str, variable: tk.StringVar, show: str = None):
        ttk.Label(parent, text=label_text, style="Field.TLabel").pack(anchor="w", pady=(6, 2))
        entry = ttk.Entry(parent, textvariable=variable, show=show if show else "")
        entry.pack(fill=tk.X, pady=(0, 4))

    def log(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] {message}\n"

        def _append():
            self.log_box.insert(tk.END, line)
            self.log_box.see(tk.END)

        self.root.after(0, _append)

    def _browse_yt_secret(self):
        path = filedialog.askopenfilename(
            title="Select Google client_secret.json",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
        )
        if path:
            self.yt_secret_var.set(path)
            self._save_config()

    def _save_config(self):
        data = {
            "tiktok_username": self.tiktok_var.get().strip().lstrip("@"),
            "ig_business_id": self.ig_id_var.get().strip(),
            "fb_page_id": self.fb_id_var.get().strip(),
            "meta_page_token": self.meta_token_var.get().strip(),
            "yt_client_secret": self.yt_secret_var.get().strip(),
            "enable_yt": self.enable_yt.get(),
            "enable_ig": self.enable_ig.get(),
            "enable_fb": self.enable_fb.get(),
            "yt_privacy": self.yt_privacy_var.get(),
            "ig_trial_label": self.ig_strategy_var.get(),
            "check_interval_label": self.interval_var.get(),
        }
        CONFIG_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _load_config(self):
        if not CONFIG_FILE.exists():
            return
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            self.tiktok_var.set(data.get("tiktok_username", ""))
            self.ig_id_var.set(data.get("ig_business_id", ""))
            self.fb_id_var.set(data.get("fb_page_id", ""))
            self.meta_token_var.set(data.get("meta_page_token", ""))
            self.yt_secret_var.set(data.get("yt_client_secret", ""))
            self.enable_yt.set(data.get("enable_yt", True))
            self.enable_ig.set(data.get("enable_ig", True))
            self.enable_fb.set(data.get("enable_fb", True))
            self.yt_privacy_var.set(data.get("yt_privacy", "private"))

            saved_label = data.get("ig_trial_label")
            if saved_label in TRIAL_STRATEGY_MAP:
                self.ig_strategy_var.set(saved_label)
            elif data.get("ig_strategy") in REVERSE_TRIAL_STRATEGY_MAP:
                self.ig_strategy_var.set(REVERSE_TRIAL_STRATEGY_MAP[data["ig_strategy"]])

            saved_interval = data.get("check_interval_label")
            if saved_interval in INTERVAL_MAP:
                self.interval_var.set(saved_interval)
        except Exception as e:
            self.log(f"Warning: Could not load saved config: {e}")

    def _setup_tray(self):
        if not HAS_TRAY or sys.platform == "darwin":
            return
        try:
            img = Image.new("RGB", (64, 64), color=(37, 99, 235))
            draw = ImageDraw.Draw(img)
            draw.polygon([(22, 16), (22, 48), (48, 32)], fill=(255, 255, 255))

            menu = pystray.Menu(
                pystray.MenuItem("Open Window", self._show_window, default=True),
                pystray.MenuItem("Quit", self._quit_app),
            )
            self.tray_icon = pystray.Icon("MusicPromoRepurposer", img, "Music Promo Repurposer", menu)
            threading.Thread(target=self.tray_icon.run, daemon=True).start()
        except Exception:
            self.tray_icon = None

    def _show_window(self, icon=None, item=None):
        self.root.after(0, self.root.deiconify)

    def _on_close(self):
        self._save_config()
        if self.tray_icon and self.running:
            self.root.withdraw()
        else:
            self._quit_app()

    def _quit_app(self, icon=None, item=None):
        self.stop_event.set()
        if self.tray_icon:
            try:
                self.tray_icon.stop()
            except Exception:
                pass
        self.root.after(0, self.root.destroy)

    def connect_youtube(self):
        if not HAS_GOOGLE:
            messagebox.showerror("Missing Libraries", "Google API libraries were not bundled in this build.")
            return
        secret_path = self.yt_secret_var.get().strip()
        if not secret_path or not os.path.exists(secret_path):
            messagebox.showwarning("Missing File", "Please select your Google client_secret.json file first.")
            return
        self._save_config()

        def _auth():
            try:
                self.log("Opening browser for YouTube Google OAuth login...")
                flow = InstalledAppFlow.from_client_secrets_file(secret_path, YOUTUBE_SCOPES)
                creds = flow.run_local_server(port=0)
                YT_TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
                self.log("YouTube connected successfully! Token saved.")
            except Exception as e:
                self.log(f"YouTube login error: {e}")

        threading.Thread(target=_auth, daemon=True).start()

    def _get_youtube_service(self):
        if not HAS_GOOGLE or not YT_TOKEN_FILE.exists():
            return None
        creds = Credentials.from_authorized_user_file(str(YT_TOKEN_FILE), YOUTUBE_SCOPES)
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            YT_TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
        return build("youtube", "v3", credentials=creds)

    def start_loop(self):
        self._save_config()
        if not self.tiktok_var.get().strip():
            messagebox.showwarning("Missing Username", "Please enter your TikTok username.")
            return
        if self.running:
            return

        self.running = True
        self.stop_event.clear()
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)

        interval_label = self.interval_var.get()
        interval_mins = INTERVAL_MAP.get(interval_label, 15)
        self.log(f"Auto-Sync started (checking TikTok {interval_label.lower()}).")

        def _loop():
            while not self.stop_event.is_set():
                self._run_pipeline()
                if self.stop_event.wait(timeout=interval_mins * 60):
                    break

        self.worker_thread = threading.Thread(target=_loop, daemon=True)
        self.worker_thread.start()

    def stop_loop(self):
        self.running = False
        self.stop_event.set()
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.log("Auto-Sync stopped.")

    def run_once_manual(self):
        self._save_config()
        if not self.tiktok_var.get().strip():
            messagebox.showwarning("Missing Username", "Please enter your TikTok username.")
            return
        threading.Thread(target=self._run_pipeline, daemon=True).start()

    def _run_pipeline(self):
        username = self.tiktok_var.get().strip().lstrip("@")
        self.log(f"Checking @{username} on TikTok for new posts (last 24h)...")

        for old_file in WORK_DIR.glob("latest_tiktok.*"):
            try:
                old_file.unlink()
            except Exception:
                pass

        ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")

        ydl_opts = {
            "playlistend": 8,
            "max_downloads": 1,
            "download_archive": str(HISTORY_FILE),
            "daterange": yt_dlp.utils.DateRange(start=yesterday),
            "format": "bv*[vcodec^=avc1]+ba[ext=m4a]/b[vcodec^=avc1]/b[ext=mp4]",
            "merge_output_format": "mp4",
            "ffmpeg_location": ffmpeg_path,
            "outtmpl": str(WORK_DIR / "latest_tiktok.%(ext)s"),
            "writeinfojson": True,
            "quiet": True,
            "no_warnings": True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([f"https://www.tiktok.com/@{username}"])
        except yt_dlp.utils.MaxDownloadsReached:
            pass
        except Exception as e:
            self.log(f"TikTok check notice: {e}")

        video_file = WORK_DIR / "latest_tiktok.mp4"
        info_file = WORK_DIR / "latest_tiktok.info.json"

        if not video_file.exists():
            self.log("No new unposted TikToks found in the last 24 hours.")
            return

        title = "New Music Short"
        description = "New Music!"
        if info_file.exists():
            try:
                info = json.loads(info_file.read_text(encoding="utf-8"))
                raw_title = (info.get("title") or info.get("description") or "New Music Short").strip()
                title = raw_title[:95] if raw_title else "New Music Short"
                description = (info.get("description") or raw_title or "New Music!").strip()
            except Exception:
                pass

        self.log(f"Downloaded new TikTok: '{title}'")

        # 1. YouTube Shorts
        if self.enable_yt.get():
            self._upload_youtube(video_file, title, description)

        # 2. Instagram Trial Reels & Facebook Page Reels (via temporary Cloudflare Quick Tunnel)
        if self.enable_ig.get() or self.enable_fb.get():
            self._publish_meta_platforms(video_file, description)

        self.log("Cycle complete!")

    def _upload_youtube(self, video_file: Path, title: str, description: str):
        try:
            yt = self._get_youtube_service()
            if not yt:
                self.log("YouTube skipped: Click 'Connect YouTube' first.")
                return
            self.log("Uploading YouTube Short...")
            body = {
                "snippet": {
                    "title": title,
                    "description": description,
                    "categoryId": "10",
                },
                "status": {
                    "privacyStatus": self.yt_privacy_var.get(),
                    "selfDeclaredMadeForKids": False,
                },
            }
            media = MediaFileUpload(str(video_file), mimetype="video/mp4", resumable=True)
            req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
            resp = req.execute()
            self.log(f"YouTube Short uploaded! Video ID: {resp.get('id')}")
        except Exception as e:
            self.log(f"YouTube upload failed: {e}")

    def _publish_meta_platforms(self, video_file: Path, caption: str):
        token = self.meta_token_var.get().strip()
        if not token:
            self.log("Meta upload skipped: Permanent Meta Page Token is missing.")
            return

        server = ThreadingHTTPServer(("127.0.0.1", 0), QuietHTTPHandler)
        port = server.server_address[1]
        srv_thread = threading.Thread(target=server.serve_forever, daemon=True)
        srv_thread.start()

        cloudflared_bin = get_bundled_binary("cloudflared")
        cf_proc = None
        tunnel_url = None

        try:
            self.log("Opening temporary secure tunnel for Instagram & Facebook...")
            creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            cf_proc = subprocess.Popen(
                [cloudflared_bin, "tunnel", "--url", f"http://127.0.0.1:{port}"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=creation_flags,
            )

            deadline = time.time() + 25
            while time.time() < deadline:
                line = cf_proc.stdout.readline()
                if not line:
                    break
                match = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", line)
                if match:
                    tunnel_url = match.group(0)
                    break

            if not tunnel_url:
                self.log("Could not establish Cloudflare tunnel URL. Skipping Meta uploads.")
                return

            public_video_url = f"{tunnel_url}/latest_tiktok.mp4"
            time.sleep(3)

            if self.enable_ig.get():
                self._upload_instagram_trial_reel(public_video_url, caption, token)

            if self.enable_fb.get():
                self._upload_facebook_reel(public_video_url, caption, token)

        except Exception as e:
            self.log(f"Meta tunnel/upload error: {e}")
        finally:
            if cf_proc:
                try:
                    cf_proc.terminate()
                except Exception:
                    pass
            try:
                server.shutdown()
            except Exception:
                pass

    def _upload_instagram_trial_reel(self, video_url: str, caption: str, token: str):
        ig_id = self.ig_id_var.get().strip()
        if not ig_id:
            self.log("Instagram skipped: Instagram Business Account ID is missing.")
            return

        strategy_code = TRIAL_STRATEGY_MAP.get(self.ig_strategy_var.get(), "SS_PERFORMANCE")

        try:
            self.log(f"Creating Instagram Trial Reel ({self.ig_strategy_var.get()})...")
            create_resp = requests.post(
                f"https://graph.facebook.com/v21.0/{ig_id}/media",
                json={
                    "media_type": "REELS",
                    "video_url": video_url,
                    "caption": caption,
                    "trial_params": {"graduation_strategy": strategy_code},
                    "access_token": token,
                },
                timeout=30,
            ).json()

            creation_id = create_resp.get("id")
            if not creation_id:
                self.log(f"Instagram container error: {create_resp}")
                return

            self.log("Waiting for Instagram to process video...")
            for _ in range(18):
                time.sleep(5)
                status_resp = requests.get(
                    f"https://graph.facebook.com/v21.0/{creation_id}",
                    params={"fields": "status_code", "access_token": token},
                    timeout=15,
                ).json()
                status_code = status_resp.get("status_code")
                if status_code == "FINISHED":
                    break
                if status_code == "ERROR":
                    self.log(f"Instagram processing failed: {status_resp}")
                    return

            pub_params = urllib.parse.urlencode({"creation_id": creation_id, "access_token": token})
            pub_resp = requests.post(
                f"https://graph.facebook.com/v21.0/{ig_id}/media_publish?{pub_params}",
                timeout=30,
            ).json()

            if pub_resp.get("id"):
                self.log(f"Instagram Trial Reel published! Post ID: {pub_resp['id']}")
            else:
                self.log(f"Instagram publish error: {pub_resp}")
        except Exception as e:
            self.log(f"Instagram upload failed: {e}")

    def _upload_facebook_reel(self, video_url: str, description: str, token: str):
        fb_id = self.fb_id_var.get().strip()
        if not fb_id:
            self.log("Facebook skipped: Facebook Page ID is missing.")
            return

        try:
            self.log("Uploading Facebook Page Reel...")
            resp = requests.post(
                f"https://graph-video.facebook.com/v21.0/{fb_id}/videos",
                params={
                    "file_url": video_url,
                    "description": description,
                    "access_token": token,
                },
                timeout=60,
            ).json()

            if resp.get("id"):
                self.log(f"Facebook Reel published! Video ID: {resp['id']}")
            else:
                self.log(f"Facebook upload error: {resp}")
        except Exception as e:
            self.log(f"Facebook upload failed: {e}")


if __name__ == "__main__":
    root = tk.Tk()
    app = MusicPromoRepurposerApp(root)
    root.mainloop()
