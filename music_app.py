#!/usr/bin/env python3
"""
Music Generator - native desktop app for ACE-Step 1.5
Drop a prompt, hit generate, track lands in musicv1/
"""
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import customtkinter as ctk
from gradio_client import Client

ACE_STEP_URL = "http://127.0.0.1:7860"
MUSIC_DIR = Path.home() / "Desktop" / "musicv1"
MUSIC_DIR.mkdir(exist_ok=True)

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")


class MusicApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Music Generator")
        self.geometry("700x560")
        self.resizable(False, False)
        self.configure(fg_color="#0a0a0f")

        self._client = None
        self._generating = False

        self._build_ui()
        self._check_server()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=28, pady=(24, 0))

        ctk.CTkLabel(
            header, text="Music Generator",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color="#a78bfa"
        ).pack(side="left")

        self.status_dot = ctk.CTkLabel(
            header, text="● connecting...",
            font=ctk.CTkFont(size=12),
            text_color="#475569"
        )
        self.status_dot.pack(side="right", pady=6)

        # Prompt
        ctk.CTkLabel(
            self, text="What do you want to make?",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#94a3b8",
            anchor="w"
        ).pack(fill="x", padx=28, pady=(20, 6))

        self.prompt_box = ctk.CTkTextbox(
            self,
            height=110,
            fg_color="#111118",
            border_color="#2a2a3e",
            border_width=1,
            corner_radius=10,
            font=ctk.CTkFont(size=14),
            text_color="#e2e8f0",
            wrap="word",
        )
        self.prompt_box.pack(fill="x", padx=28)
        self.prompt_box.insert("1.0", "")
        self.prompt_box.bind("<Return>", self._on_enter)

        # Duration row
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=28, pady=(14, 0))

        ctk.CTkLabel(
            row, text="Duration",
            font=ctk.CTkFont(size=12),
            text_color="#64748b"
        ).pack(side="left")

        self.dur_val = ctk.CTkLabel(
            row, text="60s",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#a78bfa", width=36
        )
        self.dur_val.pack(side="left", padx=(8, 0))

        self.dur_slider = ctk.CTkSlider(
            row, from_=15, to=240, number_of_steps=45,
            width=220,
            button_color="#7c3aed",
            button_hover_color="#6d28d9",
            progress_color="#4c1d95",
            command=self._on_dur
        )
        self.dur_slider.set(60)
        self.dur_slider.pack(side="left", padx=(12, 0))

        # Instrumental toggle
        self.instrumental_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            row, text="Instrumental",
            variable=self.instrumental_var,
            font=ctk.CTkFont(size=12),
            text_color="#64748b",
            fg_color="#7c3aed",
            hover_color="#6d28d9",
            checkbox_width=16, checkbox_height=16
        ).pack(side="right")

        # Generate button
        self.gen_btn = ctk.CTkButton(
            self,
            text="Generate",
            height=52,
            corner_radius=12,
            fg_color="#7c3aed",
            hover_color="#6d28d9",
            font=ctk.CTkFont(size=16, weight="bold"),
            command=self._generate,
        )
        self.gen_btn.pack(fill="x", padx=28, pady=18)

        # Progress
        self.progress = ctk.CTkProgressBar(
            self,
            height=4,
            corner_radius=2,
            fg_color="#1e1e2e",
            progress_color="#7c3aed",
        )
        self.progress.pack(fill="x", padx=28)
        self.progress.set(0)
        self.progress_label = ctk.CTkLabel(
            self, text="",
            font=ctk.CTkFont(size=12),
            text_color="#475569"
        )
        self.progress_label.pack(pady=(4, 0))

        # Divider
        ctk.CTkFrame(self, height=1, fg_color="#1e1e2e").pack(fill="x", padx=28, pady=16)

        # Track list header
        list_header = ctk.CTkFrame(self, fg_color="transparent")
        list_header.pack(fill="x", padx=28)
        ctk.CTkLabel(
            list_header, text="Recent Tracks",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#475569"
        ).pack(side="left")
        ctk.CTkButton(
            list_header, text="Open Folder",
            width=90, height=24,
            corner_radius=6,
            fg_color="#1e1e2e",
            hover_color="#2a2a3e",
            font=ctk.CTkFont(size=11),
            text_color="#64748b",
            command=lambda: subprocess.run(["open", str(MUSIC_DIR)])
        ).pack(side="right")

        # Scrollable track list
        self.track_list = ctk.CTkScrollableFrame(
            self,
            fg_color="#0a0a0f",
            scrollbar_button_color="#1e1e2e",
            height=140,
        )
        self.track_list.pack(fill="both", expand=True, padx=28, pady=(8, 20))

        # Populate existing tracks
        self._load_existing_tracks()

    # ------------------------------------------------------------------
    # Logic
    # ------------------------------------------------------------------

    def _on_dur(self, val):
        self.dur_val.configure(text=f"{int(val)}s")

    def _on_enter(self, event):
        if event.state & 0x1:  # shift+enter = newline
            return
        self._generate()
        return "break"

    def _check_server(self):
        def check():
            import urllib.request
            for _ in range(60):
                try:
                    urllib.request.urlopen(ACE_STEP_URL, timeout=2)
                    self._client = Client(ACE_STEP_URL, verbose=False)
                    self.after(0, lambda: self.status_dot.configure(
                        text="● ready", text_color="#86efac"))
                    return
                except Exception:
                    time.sleep(2)
            self.after(0, lambda: self.status_dot.configure(
                text="● offline", text_color="#fca5a5"))
        threading.Thread(target=check, daemon=True).start()

    def _generate(self):
        if self._generating:
            return
        prompt = self.prompt_box.get("1.0", "end").strip()
        if not prompt:
            self._flash("Type a prompt first")
            return
        if self._client is None:
            self._flash("ACE-Step not connected - is it running?")
            return

        duration = int(self.dur_slider.get())
        instrumental = self.instrumental_var.get()

        self._generating = True
        self.gen_btn.configure(state="disabled", text="Generating...")
        self.progress.set(0)
        self._set_progress("Starting generation...", 0.05)

        threading.Thread(
            target=self._run_generation,
            args=(prompt, duration, instrumental),
            daemon=True
        ).start()

    def _run_generation(self, prompt, duration, instrumental):
        try:
            self.after(0, lambda: self._set_progress("Generating... (1-2 min)", 0.15))

            # Positional args in exact parameter order from /gradio_api/info
            args = [
                prompt,      # [0]  caption
                "",          # [1]  lyrics
                duration,    # [2]  duration
                "",          # [3]  audio_codes
                "",          # [4]  key (empty = auto)
                "unknown",   # [5]  bpm
                8,           # [6]  inference_steps
                7.0,         # [7]  guidance_scale
                True,        # [8]  think
                "-1",        # [9]  seed (string)
                None,        # [10] ref audio
                -1,          # [11] ref audio end
                1,           # [12] batch_size
                None,        # [13] repaint audio
                None,        # [14] repaint end
                0.0,         # [15] repaint start
                -1,          # [16] repaint end secs
                "Fill the audio semantic mask based on the given conditions:",
                1.0,         # [18]
                0.0,         # [19]
                "text2music",# [20] task
                instrumental,# [21] instrumental
                0.0, 1.0, 3.0, "ode", "euler", 0.0, 0.0,
                "",          # [29]
                "mp3",       # [30] format
                "320k",      # [31] bitrate
                44100,       # [32] sample_rate
                0.85, True, 2.0, 0, 0.9,
                "NO USER INPUT",
                True, False, True, False, True, False, False,
                0.5,         # [46]
                1,           # [47] batch_size (second occurrence)
                None, [],    # [48-49]
                True, -1.0, 0.0, 0.0, 0.0, 1.0,
                "balanced",
                0.5, False,
            ]

            # generation_wrapper is a streaming generator - use submit() not predict()
            job = self._client.submit(*args, api_name="/generation_wrapper")

            # Poll for completion, updating progress
            import time as _time
            start = _time.time()
            result = None
            for partial in job:
                elapsed = int(_time.time() - start)
                self.after(0, lambda e=elapsed: self._set_progress(f"Generating... {e}s", min(0.15 + e / 120, 0.9)))
                result = partial  # keep last value

            if result is None:
                result = job.result()

            self.after(0, lambda: self._set_progress("Processing audio...", 0.9))

            # Result is a tuple; first audio element is (path, ...) or just path
            audio_path = self._extract_audio_path(result)
            if audio_path:
                final_path = self._save_to_musicv1(audio_path, prompt)
                self.after(0, lambda: self._on_done(final_path, prompt))
            else:
                self.after(0, lambda: self._on_error("No audio in response"))

        except Exception as e:
            self.after(0, lambda: self._on_error(str(e)[:120]))

    def _extract_audio_path(self, result):
        """Pull the audio file path out of Gradio's response tuple.
        result[8] is a list of file paths - first entry is the mp3."""
        if result is None:
            return None
        items = result if isinstance(result, (list, tuple)) else [result]

        # result[8] = list of generated audio paths
        if len(items) > 8 and isinstance(items[8], list) and items[8]:
            path = items[8][0]
            if isinstance(path, str) and os.path.exists(path):
                return path

        # Fallback: scan all items
        for item in items:
            if isinstance(item, str) and item.endswith(('.mp3', '.wav', '.flac')) and os.path.exists(item):
                return item
            if isinstance(item, list):
                for sub in item:
                    if isinstance(sub, str) and sub.endswith(('.mp3', '.wav', '.flac')) and os.path.exists(sub):
                        return sub
        return None

    def _save_to_musicv1(self, src_path: str, prompt: str) -> Path:
        """Copy/move the generated file to musicv1/ with a readable name."""
        import re, shutil
        src = Path(src_path)
        # Build slug from prompt
        slug = re.sub(r"[^a-z0-9 ]", "", prompt.lower())
        slug = re.sub(r"\s+", "-", slug.strip())[:50].rstrip("-")
        date = time.strftime("%Y-%m-%d")
        dest = MUSIC_DIR / f"{date}_{slug}{src.suffix}"
        counter = 1
        while dest.exists():
            dest = MUSIC_DIR / f"{date}_{slug}_{counter}{src.suffix}"
            counter += 1
        shutil.copy2(str(src), str(dest))
        return dest

    def _on_done(self, path: Path, prompt: str):
        self._set_progress(f"Saved: {path.name}", 1.0)
        self.gen_btn.configure(state="normal", text="Generate")
        self._generating = False
        self._add_track(path, prompt)

    def _on_error(self, msg: str):
        self._set_progress(f"Error: {msg}", 0)
        self.gen_btn.configure(state="normal", text="Generate")
        self._generating = False

    def _set_progress(self, msg: str, val: float):
        self.progress.set(val)
        self.progress_label.configure(text=msg)

    def _flash(self, msg: str):
        self.progress_label.configure(text=msg, text_color="#fca5a5")
        self.after(3000, lambda: self.progress_label.configure(
            text="", text_color="#475569"))

    # ------------------------------------------------------------------
    # Track list
    # ------------------------------------------------------------------

    def _load_existing_tracks(self):
        files = sorted(
            [f for f in MUSIC_DIR.iterdir()
             if f.suffix in (".mp3", ".wav", ".flac") and f.is_file()],
            key=lambda f: f.stat().st_mtime, reverse=True
        )[:20]
        for f in files:
            self._add_track(f, f.stem.replace("-", " "))

    def _add_track(self, path: Path, prompt: str):
        row = ctk.CTkFrame(
            self.track_list,
            fg_color="#111118",
            corner_radius=8,
        )
        row.pack(fill="x", pady=3)

        ctk.CTkLabel(
            row,
            text=path.name,
            font=ctk.CTkFont(size=12),
            text_color="#c4b5fd",
            anchor="w"
        ).pack(side="left", padx=12, pady=8, fill="x", expand=True)

        ctk.CTkButton(
            row, text="▶ Play",
            width=70, height=28,
            corner_radius=6,
            fg_color="#1e1e2e",
            hover_color="#2a2a3e",
            font=ctk.CTkFont(size=11),
            text_color="#94a3b8",
            command=lambda p=path: subprocess.run(["open", str(p)])
        ).pack(side="right", padx=8)


if __name__ == "__main__":
    app = MusicApp()
    app.mainloop()
