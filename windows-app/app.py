import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

import requests
import yt_dlp

try:
    import imageio_ffmpeg
except ImportError:
    imageio_ffmpeg = None

try:
    import pystray
    from PIL import Image, ImageDraw
    HAS_TRAY = True
except ImportError:
    HAS_TRAY = False

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    HAS_GOOGLE = True
except ImportError:
    HAS_GOOGLE = False

APP_DIR = Path.home() / "MusicPromoRepurposer"
TEMP_DIR = APP_DIR / "temp"
CONFIG_FILE = APP_DIR / "config.json"
ARCHIVE_FILE = APP_DIR / "tiktok_history.txt"
YT_TOKEN_FILE = APP_DIR / "youtube_token.json"
YT_SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def get_bundled_binary(base_name: str) -> str:
    exe_name = f"{base_name}.exe" if sys.platform == "win32" else base_name
    candidates = []
    if getattr(sys, "_MEIPASS", None):
        candidates.append(Path(sys._MEIPASS) / exe_name)
    candidates.append(Path(__file__).resolve().parent / exe_name)
    for c in candidates:
        if c.exists():
            return str(c)
    if base_name == "ffmpeg" and imageio_ffmpeg is not None:
        try:
            return imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            pass
    found = shutil.which(exe_name) or shutil.which(base_name)
    return found or exe_name


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass


class CloudflareTunnel:
    def __init__(self, directory: Path, log_fn):
        self.directory = directory
        self.log = log_fn
        self.httpd = None
        self.server_thread = None
        self.proc = None
        self.public_url = None

    def start(self) -> str:
        handler = partial(QuietHandler, directory=str(self.directory))
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        port = self.httpd.server_address[1]
        self.server_thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.server_thread.start()

        cf_bin = get_bundled_binary("cloudflared")
        creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        self.proc = subprocess.Popen(
            [cf_bin, "tunnel", "--url", f"http://127.0.0.1:{port}", "--no-autoupdate"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            creationflags=creationflags,
        )

        deadline = time.time() + 25
        pattern = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")
        while time.time() < deadline:
            if self.proc.poll() is not None:
                break
            line = self.proc.stdout.readline()
            if not line:
                time.sleep(0.2)
                continue
            match = pattern.search(line)
            if match:
                self.public_url = match.group(0)
                return self.public_url

        self.stop()
        raise RuntimeError("Could not establish temporary Cloudflare tunnel URL within 25s.")

    def stop(self):
        if self.proc:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=5)
            except Exception:
                try:
                    self.proc.kill()
                except Exception:
                    pass
            self.proc = None
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
        self.root.title("Music Promo Repurposer — TikTok to Shorts & Reels")
        self.root.geometry("680x760")
        self.root.configure(bg="#12141a")

        APP_DIR.mkdir(parents=True, exist_ok=True)
        TEMP_DIR.mkdir(parents=True, exist_ok=True)

        self.running = False
        self.busy = False
        self.stop_event = threading.Event()
        self.tray_icon = None

        self.config = self.load_config()
        self.build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def load_config(self) -> dict:
        if CONFIG_FILE.exists():
            try:
                return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {
            "tiktok_username": "",
            "ig_user_id": "",
            "fb_page_id": "",
            "meta_page_token": "",
            "yt_client_secret": "",
            "yt_privacy": "private",
            "ig_graduation": "SS_PERFORMANCE",
            "enable_yt": True,
            "enable_ig": True,
            "enable_fb": True,
        }

    def save_config(self):
        data = {
            "tiktok_username": self.var_tiktok.get().strip().lstrip("@"),
            "ig_user_id": self.var_ig_id.get().strip(),
            "fb_page_id": self.var_fb_id.get().strip(),
            "meta_page_token": self.var_meta_token.get().strip(),
            "yt_client_secret": self.var_yt_secret.get().strip(),
            "yt_privacy": self.var_yt_privacy.get().strip(),
            "ig_graduation": self.var_ig_grad.get().strip(),
            "enable_yt": self.var_en_yt.get(),
            "enable_ig": self.var_en_ig.get(),
            "enable_fb": self.var_en_fb.get(),
        }
        CONFIG_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
        self.config = data

    def log(self, msg: str):
        ts = time.strftime("%H:%M:%S")
        line = f"[{ts}] {msg}\n"

        def _append():
            self.log_box.configure(state="normal")
            self.log_box.insert(tk.END, line)
            self.log_box.see(tk.END)
            self.log_box.configure(state="disabled")

        self.root.after(0, _append)

    def build_ui(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass

        bg = "#12141a"
        card = "#1c202a"
        fg = "#f1f5f9"
        muted = "#94a3b8"
        accent = "#6366f1"

        header = tk.Frame(self.root, bg=bg)
        header.pack(fill="x", padx=20, pady=(16, 8))
        tk.Label(
            header,
            text="Music Promo Repurposer",
            font=("Helvetica", 18, "bold"),
            bg=bg,
            fg=fg,
        ).pack(anchor="w")
        tk.Label(
            header,
            text="Auto-repost new TikToks to YouTube Shorts, Instagram Trial Reels & Facebook Reels",
            font=("Helvetica", 10),
            bg=bg,
            fg=muted,
        ).pack(anchor="w")

        form = tk.Frame(self.root, bg=card, padx=16, pady=14)
        form.pack(fill="x", padx=20, pady=6)

        self.var_tiktok = tk.StringVar(value=self.config.get("tiktok_username", ""))
        self.var_ig_id = tk.StringVar(value=self.config.get("ig_user_id", ""))
        self.var_fb_id = tk.StringVar(value=self.config.get("fb_page_id", ""))
        self.var_meta_token = tk.StringVar(value=self.config.get("meta_page_token", ""))
        self.var_yt_secret = tk.StringVar(value=self.config.get("yt_client_secret", ""))
        self.var_yt_privacy = tk.StringVar(value=self.config.get("yt_privacy", "private"))
        self.var_ig_grad = tk.StringVar(value=self.config.get("ig_graduation", "SS_PERFORMANCE"))
        self.var_en_yt = tk.BooleanVar(value=self.config.get("enable_yt", True))
        self.var_en_ig = tk.BooleanVar(value=self.config.get("enable_ig", True))
        self.var_en_fb = tk.BooleanVar(value=self.config.get("enable_fb", True))

        fields = [
            ("TikTok Username (without @):", self.var_tiktok, False),
            ("Instagram Business Account ID (178414...):", self.var_ig_id, False),
            ("Facebook Page ID:", self.var_fb_id, False),
            ("Permanent Meta Page Token:", self.var_meta_token, True),
        ]

        for idx, (label_text, var, is_secret) in enumerate(fields):
            tk.Label(form, text=label_text, bg=card, fg=fg, font=("Helvetica", 10, "bold")).grid(
                row=idx * 2, column=0, columnspan=2, sticky="w", pady=(6, 2)
            )
            entry = tk.Entry(
                form,
                textvariable=var,
                bg="#0f1117",
                fg=fg,
                insertbackground=fg,
                relief="flat",
                font=("Helvetica", 10),
                show="*" if is_secret else "",
            )
            entry.grid(row=idx * 2 + 1, column=0, columnspan=2, sticky="ew", ipady=5)

        # YouTube client_secret.json picker
        tk.Label(
            form,
            text="YouTube Google OAuth JSON (client_secret.json):",
            bg=card,
            fg=fg,
            font=("Helvetica", 10, "bold"),
        ).grid(row=8, column=0, columnspan=2, sticky="w", pady=(8, 2))

        yt_entry = tk.Entry(
            form,
            textvariable=self.var_yt_secret,
            bg="#0f1117",
            fg=fg,
            insertbackground=fg,
            relief="flat",
            font=("Helvetica", 10),
        )
        yt_entry.grid(row=9, column=0, sticky="ew", ipady=5, padx=(0, 8))

        tk.Button(
            form,
            text="Browse...",
            command=self.browse_yt_secret,
            bg="#334155",
            fg=fg,
            relief="flat",
            padx=10,
            pady=4,
        ).grid(row=9, column=1, sticky="e")

        # Options row
        opts = tk.Frame(form, bg=card)
        opts.grid(row=10, column=0, columnspan=2, sticky="ew", pady=(10, 4))

        tk.Checkbutton(
            opts, text="YouTube Shorts", variable=self.var_en_yt, bg=card, fg=fg, selectcolor="#0f1117", activebackground=card, activeforeground=fg
        ).pack(side="left", padx=(0, 12))
        tk.Checkbutton(
            opts, text="IG Trial Reels", variable=self.var_en_ig, bg=card, fg=fg, selectcolor="#0f1117", activebackground=card, activeforeground=fg
        ).pack(side="left", padx=(0, 12))
        tk.Checkbutton(
            opts, text="Facebook Reels", variable=self.var_en_fb, bg=card, fg=fg, selectcolor="#0f1117", activebackground=card, activeforeground=fg
        ).pack(side="left")

        dropdowns = tk.Frame(form, bg=card)
        dropdowns.grid(row=11, column=0, columnspan=2, sticky="ew", pady=(6, 2))

        tk.Label(dropdowns, text="YT Privacy:", bg=card, fg=muted, font=("Helvetica", 9)).pack(side="left")
        ttk.Combobox(
            dropdowns,
            textvariable=self.var_yt_privacy,
            values=["private", "unlisted", "public"],
            width=10,
            state="readonly",
        ).pack(side="left", padx=(4, 16))

        tk.Label(dropdowns, text="IG Trial Strategy:", bg=card, fg=muted, font=("Helvetica", 9)).pack(side="left")
        ttk.Combobox(
            dropdowns,
            textvariable=self.var_ig_grad,
            values=["SS_PERFORMANCE", "MANUAL"],
            width=16,
            state="readonly",
        ).pack(side="left", padx=(4, 0))

        form.columnconfigure(0, weight=1)

        # Action Buttons
        btns = tk.Frame(self.root, bg=bg)
        btns.pack(fill="x", padx=20, pady=10)

        self.btn_start = tk.Button(
            btns,
            text="Start Auto-Sync (15m)",
            command=self.start_loop,
            bg=accent,
            fg="#ffffff",
            font=("Helvetica", 10, "bold"),
            relief="flat",
            padx=14,
            pady=8,
        )
        self.btn_start.pack(side="left", padx=(0, 8))

        self.btn_stop = tk.Button(
            btns,
            text="Stop",
            command=self.stop_loop,
            bg="#334155",
            fg="#ffffff",
            font=("Helvetica", 10),
            relief="flat",
            padx=12,
            pady=8,
            state="disabled",
        )
        self.btn_stop.pack(side="left", padx=(0, 8))

        tk.Button(
            btns,
            text="Run Now (Test)",
            command=self.run_once_async,
            bg="#0ea5e9",
            fg="#ffffff",
            font=("Helvetica", 10, "bold"),
            relief="flat",
            padx=12,
            pady=8,
        ).pack(side="left", padx=(0, 8))

        tk.Button(
            btns,
            text="Connect YouTube",
            command=self.connect_youtube_async,
            bg="#1e293b",
            fg="#f1f5f9",
            font=("Helvetica", 10),
            relief="flat",
            padx=12,
            pady=8,
        ).pack(side="right")

        # Log area
        tk.Label(self.root, text="Activity Log", bg=bg, fg=muted, font=("Helvetica", 9, "bold")).pack(
            anchor="w", padx=20
        )
        self.log_box = scrolledtext.ScrolledText(
            self.root,
            height=13,
            bg="#0f1117",
            fg="#cbd5e1",
            font=("Courier", 9),
            relief="flat",
            state="disabled",
        )
        self.log_box.pack(fill="both", expand=True, padx=20, pady=(4, 16))
        self.log("Ready. Enter your details above and click 'Run Now (Test)' or 'Start Auto-Sync'.")

    def browse_yt_secret(self):
        path = filedialog.askopenfilename(
            title="Select Google OAuth client_secret.json",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
        )
        if path:
            self.var_yt_secret.set(path)
            self.save_config()

    def get_youtube_service(self):
        if not HAS_GOOGLE:
            raise RuntimeError("Google API libraries missing in build.")
        secret_path = self.config.get("yt_client_secret", "")
        if not secret_path or not Path(secret_path).exists():
            raise RuntimeError("Please select your Google client_secret.json file first.")

        creds = None
        if YT_TOKEN_FILE.exists():
            creds = Credentials.from_authorized_user_file(str(YT_TOKEN_FILE), YT_SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(secret_path, YT_SCOPES)
                creds = flow.run_local_server(port=0)
            YT_TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
        return build("youtube", "v3", credentials=creds)

    def connect_youtube_async(self):
        self.save_config()

        def _work():
            try:
                self.log("Opening browser for Google / YouTube login...")
                self.get_youtube_service()
                self.log("YouTube connected successfully!")
            except Exception as exc:
                self.log(f"YouTube login error: {exc}")

        threading.Thread(target=_work, daemon=True).start()

    def start_loop(self):
        self.save_config()
        if not self.config.get("tiktok_username"):
            messagebox.showwarning("Missing Username", "Please enter your TikTok username.")
            return
        if self.running:
            return
        self.running = True
        self.stop_event.clear()
        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.log("Auto-Sync started (checking every 15 minutes).")
        threading.Thread(target=self._poll_worker, daemon=True).start()

    def stop_loop(self):
        self.running = False
        self.stop_event.set()
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")
        self.log("Auto-Sync stopped.")

    def _poll_worker(self):
        while self.running and not self.stop_event.is_set():
            self.execute_pipeline()
            self.stop_event.wait(15 * 60)

    def run_once_async(self):
        self.save_config()
        if not self.config.get("tiktok_username"):
            messagebox.showwarning("Missing Username", "Please enter your TikTok username.")
            return
        if self.busy:
            self.log("A sync run is already in progress...")
            return
        threading.Thread(target=self.execute_pipeline, daemon=True).start()

    def execute_pipeline(self):
        if self.busy:
            return
        self.busy = True
        try:
            user = self.config["tiktok_username"]
            self.log(f"Checking @{user} on TikTok for new videos (last 24h)...")

            for old in TEMP_DIR.glob("latest_tiktok.*"):
                try:
                    old.unlink()
                except Exception:
                    pass

            ffmpeg_loc = get_bundled_binary("ffmpeg")
            ydl_opts = {
                "playlistend": 8,
                "max_downloads": 1,
                "download_archive": str(ARCHIVE_FILE),
                "writeinfojson": True,
                "format": "bv*[vcodec^=avc1]+ba[ext=m4a]/b[vcodec^=avc1]/b[ext=mp4]",
                "merge_output_format": "mp4",
                "outtmpl": str(TEMP_DIR / "latest_tiktok.%(ext)s"),
                "ffmpeg_location": ffmpeg_loc,
                "quiet": True,
                "no_warnings": True,
                "ignoreerrors": True,
            }

            try:
                from yt_dlp.utils import DateRange
                ydl_opts["dateafter"] = DateRange("now-1day")
            except Exception:
                pass

            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([f"https://www.tiktok.com/@{user}"])
            except Exception:
                pass

            mp4_file = TEMP_DIR / "latest_tiktok.mp4"
            info_file = TEMP_DIR / "latest_tiktok.info.json"

            if not mp4_file.exists():
                self.log("No new unposted TikTok found in the last 24 hours.")
                return

            title = "New Music Short"
            desc = "New Music!"
            if info_file.exists():
                try:
                    meta = json.loads(info_file.read_text(encoding="utf-8"))
                    title = (meta.get("title") or "New Music Short")[:95]
                    desc = meta.get("description") or title
                except Exception:
                    pass

            self.log(f"Downloaded new TikTok: '{title}'")

            # 1. YouTube Shorts
            if self.config.get("enable_yt"):
                try:
                    self.log("Uploading to YouTube Shorts...")
                    yt = self.get_youtube_service()
                    body = {
                        "snippet": {
                            "title": title,
                            "description": desc,
                            "categoryId": "10",
                        },
                        "status": {
                            "privacyStatus": self.config.get("yt_privacy", "private"),
                            "selfDeclaredMadeForKids": False,
                        },
                    }
                    media = MediaFileUpload(str(mp4_file), mimetype="video/mp4", resumable=True)
                    req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
                    resp = None
                    while resp is None:
                        _, resp = req.next_chunk()
                    self.log(f"YouTube Short uploaded! Video ID: {resp.get('id')}")
                except Exception as exc:
                    self.log(f"YouTube upload failed: {exc}")

            # 2. Instagram Trial Reels & Facebook Page Reels via temporary Cloudflare Tunnel
            need_meta = (self.config.get("enable_ig") or self.config.get("enable_fb")) and self.config.get("meta_page_token")
            if need_meta:
                tunnel = CloudflareTunnel(TEMP_DIR, self.log)
                try:
                    self.log("Opening temporary HTTPS tunnel for Instagram / Facebook...")
                    base_url = tunnel.start()
                    video_url = f"{base_url}/latest_tiktok.mp4"
                    token = self.config["meta_page_token"]

                    # Instagram Trial Reel
                    if self.config.get("enable_ig") and self.config.get("ig_user_id"):
                        try:
                            ig_id = self.config["ig_user_id"]
                            self.log("Creating Instagram Trial Reel container...")
                            r1 = requests.post(
                                f"https://graph.facebook.com/v21.0/{ig_id}/media",
                                json={
                                    "media_type": "REELS",
                                    "video_url": video_url,
                                    "caption": desc,
                                    "trial_params": {
                                        "graduation_strategy": self.config.get("ig_graduation", "SS_PERFORMANCE")
                                    },
                                    "access_token": token,
                                },
                                timeout=60,
                            )
                            r1.raise_for_status()
                            creation_id = r1.json()["id"]
                            self.log("Waiting 45s for Instagram to process video...")
                            time.sleep(45)

                            r2 = requests.post(
                                f"https://graph.facebook.com/v21.0/{ig_id}/media_publish",
                                params={"creation_id": creation_id, "access_token": token},
                                timeout=60,
                            )
                            r2.raise_for_status()
                            self.log(f"Instagram Trial Reel published! Media ID: {r2.json().get('id')}")
                        except Exception as exc:
                            detail = getattr(getattr(exc, "response", None), "text", str(exc))
                            self.log(f"Instagram Trial Reel failed: {detail}")

                    # Facebook Page Reel
                    if self.config.get("enable_fb") and self.config.get("fb_page_id"):
                        try:
                            fb_id = self.config["fb_page_id"]
                            self.log("Publishing Reel to Facebook Page...")
                            rf = requests.post(
                                f"https://graph-video.facebook.com/v21.0/{fb_id}/videos",
                                params={
                                    "file_url": video_url,
                                    "description": desc,
                                    "access_token": token,
                                },
                                timeout=120,
                            )
                            rf.raise_for_status()
                            self.log(f"Facebook Page Reel uploaded! Video ID: {rf.json().get('id')}")
                            time.sleep(15)
                        except Exception as exc:
                            detail = getattr(getattr(exc, "response", None), "text", str(exc))
                            self.log(f"Facebook Page upload failed: {detail}")
                finally:
                    tunnel.stop()
                    self.log("Closed temporary tunnel.")

            self.log("Sync cycle complete!")
        finally:
            self.busy = False

    def create_tray_image(self):
        img = Image.new("RGB", (64, 64), color=(99, 102, 241))
        draw = ImageDraw.Draw(img)
        draw.polygon([(22, 16), (22, 48), (48, 32)], fill=(255, 255, 255))
        return img

    def on_close(self):
        self.save_config()
        if HAS_TRAY and self.running:
            self.root.withdraw()
            if self.tray_icon is None:
                menu = pystray.Menu(
                    pystray.MenuItem("Open Window", self.restore_window, default=True),
                    pystray.MenuItem("Quit", self.quit_app),
                )
                self.tray_icon = pystray.Icon("MusicPromoRepurposer", self.create_tray_image(), "Music Promo Repurposer", menu)
                threading.Thread(target=self.tray_icon.run, daemon=True).start()
        else:
            self.quit_app()

    def restore_window(self, icon=None, item=None):
        self.root.after(0, self.root.deiconify)

    def quit_app(self, icon=None, item=None):
        self.running = False
        self.stop_event.set()
        if self.tray_icon:
            try:
                self.tray_icon.stop()
            except Exception:
                pass
        self.root.after(0, self.root.destroy)


if __name__ == "__main__":
    root = tk.Tk()
    app = RepurposerApp(root)
    root.mainloop()
