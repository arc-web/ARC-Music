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
from datetime import datetime
from pathlib import Path

import customtkinter as ctk
from gradio_client import Client
from PIL import Image, ImageTk

ACE_STEP_URL = "http://127.0.0.1:7860"
MUSIC_DIR = Path.home() / "Desktop" / "musicv1"
MUSIC_DIR.mkdir(exist_ok=True)
GENERATE_COVER = Path(__file__).parent / "generate_cover.py"
COVER_PYTHON = Path(__file__).parent / ".venv_flux" / "bin" / "python3.12"

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")


def _widget_in_subtree(widget, root):
    """Return True if widget is root or a descendant of root."""
    try:
        while widget is not None:
            if str(widget) == str(root):
                return True
            widget = widget.master
    except Exception:
        pass
    return False


class MusicApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Music Generator")
        self.geometry("700x780")
        self.minsize(700, 600)
        self.resizable(False, True)
        self.configure(fg_color="#0a0a0f")

        self._client = None
        self._generating = False
        self._track_rows = []
        self._debug_log = []
        # Player state
        self._player_proc = None
        self._player_paused = False
        self._player_idx = -1
        self._muted = False

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

        self._prompt_placeholder = "Describe the song you want — style, mood, vibe, instruments, tempo, anything.\n\nExamples:\n  upbeat pop song, female vocals, catchy chorus, 80s synth\n  dark trap beat, heavy 808s, moody atmosphere, no vocals\n  deep house groove, four-on-the-floor kick, late night club"
        self.prompt_box = ctk.CTkTextbox(
            self,
            height=140,
            fg_color="#111118",
            border_color="#2a2a3e",
            border_width=1,
            corner_radius=10,
            font=ctk.CTkFont(size=14),
            text_color="#e2e8f0",
            wrap="word",
        )
        self.prompt_box.pack(fill="x", padx=28)
        self.prompt_box.insert("1.0", self._prompt_placeholder)
        self.prompt_box.configure(text_color="#4a5568")
        self.prompt_box.bind("<FocusIn>", self._prompt_focus_in)
        self.prompt_box.bind("<FocusOut>", self._prompt_focus_out)
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
        self.instrumental_var = ctk.BooleanVar(value=False)
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
        progress_row = ctk.CTkFrame(self, fg_color="transparent")
        progress_row.pack(fill="x", padx=28, pady=(4, 0))
        self.progress_label = ctk.CTkLabel(
            progress_row, text="",
            font=ctk.CTkFont(size=12),
            text_color="#475569",
            anchor="w"
        )
        self.progress_label.pack(side="left", fill="x", expand=True)
        self.debug_btn = ctk.CTkButton(
            progress_row, text="Debug",
            width=58, height=20,
            corner_radius=5,
            fg_color="#1e1e2e",
            hover_color="#2a2a3e",
            font=ctk.CTkFont(size=11),
            text_color="#64748b",
            command=self._copy_debug,
        )
        self.debug_btn.pack(side="right")
        self.debug_btn.pack_forget()  # hidden until a generation has run
        self._last_status = ""

        # Divider
        ctk.CTkFrame(self, height=1, fg_color="#1e1e2e").pack(fill="x", padx=28, pady=(16, 0))

        # Player bar
        player = ctk.CTkFrame(self, fg_color="#0d0d14", corner_radius=10)
        player.pack(fill="x", padx=28, pady=(10, 6))

        btn_cfg = dict(width=44, height=36, corner_radius=8,
                       fg_color="#1a1a28", hover_color="#252538",
                       font=ctk.CTkFont(size=18), text_color="#a78bfa")

        self.prev_btn = ctk.CTkButton(player, text="⏮", command=self._prev_track, **btn_cfg)
        self.prev_btn.pack(side="left", padx=(12, 4), pady=8)

        self.play_btn = ctk.CTkButton(player, text="▶", command=self._toggle_play,
                                       width=52, height=36, corner_radius=8,
                                       fg_color="#7c3aed", hover_color="#6d28d9",
                                       font=ctk.CTkFont(size=18), text_color="white")
        self.play_btn.pack(side="left", padx=4, pady=8)

        self.next_btn = ctk.CTkButton(player, text="⏭", command=self._next_track, **btn_cfg)
        self.next_btn.pack(side="left", padx=(4, 12), pady=8)

        self.now_playing = ctk.CTkLabel(
            player, text="No track selected",
            font=ctk.CTkFont(size=12), text_color="#475569", anchor="w"
        )
        self.now_playing.pack(side="left", fill="x", expand=True, padx=(0, 4))

        self.speaker_btn = ctk.CTkButton(
            player, text="🔈",
            width=44, height=36, corner_radius=8,
            fg_color="#1a1a28", hover_color="#252538",
            font=ctk.CTkFont(size=18), text_color="#334155",
            command=self._toggle_mute,
        )
        self.speaker_btn.pack(side="right", padx=(0, 8), pady=8)

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
            scrollbar_button_color="#2a2a3e",
            scrollbar_button_hover_color="#3d3d5c",
        )
        self.track_list.pack(fill="both", expand=True, padx=28, pady=(8, 20))

        # Populate existing tracks
        self._load_existing_tracks()

    # ------------------------------------------------------------------
    # Logic
    # ------------------------------------------------------------------

    def _prompt_focus_in(self, _event=None):
        if self.prompt_box.get("1.0", "end-1c") == self._prompt_placeholder:
            self.prompt_box.delete("1.0", "end")
            self.prompt_box.configure(text_color="#e2e8f0")

    def _prompt_focus_out(self, _event=None):
        if not self.prompt_box.get("1.0", "end-1c").strip():
            self.prompt_box.delete("1.0", "end")
            self.prompt_box.insert("1.0", self._prompt_placeholder)
            self.prompt_box.configure(text_color="#4a5568")

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
        if not prompt or prompt == self._prompt_placeholder.strip():
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
        self._debug_log = []  # reset for each new generation
        self._dbg("generation_start", prompt=prompt, duration=duration, instrumental=instrumental)
        try:
            self.after(0, lambda: self._set_progress("Generating... (1-2 min)", 0.15))

            # Instrumental is controlled via the lyrics field:
            # "[Instrumental]" = no vocals, "" = auto-generate lyrics with LLM
            lyrics = "[Instrumental]" if instrumental else ""
            self._dbg("args_built", lyrics_field=lyrics, auto_lrc=not instrumental)

            # Positional args mapped from generation_run_wiring.py inputs order
            args = [
                prompt,      # [0]  captions
                lyrics,      # [1]  lyrics ("[Instrumental]" or "" for auto-vocal)
                0,           # [2]  bpm (0 = auto)
                "",          # [3]  key_scale
                "",          # [4]  time_signature
                "unknown",   # [5]  vocal_language
                25,          # [6]  inference_steps (25 = good quality with euler+heun)
                10.0,        # [7]  guidance_scale (was 7.0 - tighter prompt adherence)
                True,        # [8]  random_seed_checkbox
                "-1",        # [9]  seed (string)
                None,        # [10] reference_audio
                duration,    # [11] audio_duration
                1,           # [12] batch_size_input
                None,        # [13] src_audio
                None,        # [14] text2music_audio_code_string
                0.0,         # [15] repainting_start
                -1,          # [16] repainting_end
                "Fill the audio semantic mask based on the given conditions:",
                1.0,         # [18] audio_cover_strength
                0.0,         # [19] cover_noise_strength
                "text2music",# [20] task_type
                False,       # [21] use_adg
                0.0, 1.0, 3.0, "euler", "heun", 0.0, 0.1,  # euler+heun: 2nd-order sampler actually fires
                "",          # [29] custom_timesteps
                "mp3",       # [30] audio_format
                "320k",      # [31] mp3_bitrate
                44100,       # [32] mp3_sample_rate
                0.85,        # [33] lm_temperature
                True,        # [34] think_checkbox
                3.5,         # [35] lm_cfg_scale (was 2.0 - stronger vocal guidance)
                40,          # [36] lm_top_k (was 0 - enables diverse lyric vocabulary)
                0.9,         # [37] lm_top_p
                "NO USER INPUT",  # [38] lm_negative_prompt
                True,        # [39] use_cot_metas
                False,       # [40] use_cot_caption
                True,        # [41] use_cot_language
                # is_format_caption_state is a State component - API skips it, not passed
                False,       # [42] constrained_decoding_debug
                False,       # [43] allow_lm_batch
                False,       # [44] auto_score
                not instrumental,  # [45] auto_lrc (True = auto-generate lyrics for vocals)
                0.5,         # [46] score_scale (Slider, default 0.5)
                8,           # [47] lm_batch_chunk_size (Number, default 8)
                None,        # [48] track_name (Dropdown)
                [],          # [49] complete_track_classes (Checkboxgroup)
                True,        # [50] enable_normalization
                -3.0,        # [51] normalization_db (was -1.0 - headroom prevents harsh peaks)
                0.0,         # [52] fade_in_duration
                0.0,         # [53] fade_out_duration
                0.0,         # [54] latent_shift
                1.0,         # [55] latent_rescale
                "balanced",  # [56] repaint_mode
                0.5,         # [57] repaint_strength
                False,       # [58] autogen_checkbox
            ]

            # generation_wrapper is a streaming generator - use submit() not predict()
            self._dbg("submit", api="/generation_wrapper", n_args=len(args))
            job = self._client.submit(*args, api_name="/generation_wrapper")

            import time as _time
            start = _time.time()
            result = None
            partial_count = 0
            for partial in job:
                partial_count += 1
                elapsed = int(_time.time() - start)
                self._dbg("partial", n=partial_count, elapsed_s=elapsed,
                          type=type(partial).__name__,
                          len=len(partial) if hasattr(partial, "__len__") else "?")
                self.after(0, lambda e=elapsed: self._set_progress(f"Generating... {e}s", min(0.15 + e / 120, 0.9)))
                result = partial

            elapsed_total = round(_time.time() - start, 1)
            self._dbg("stream_done", partials=partial_count, elapsed_s=elapsed_total,
                      result_type=type(result).__name__,
                      result_len=len(result) if hasattr(result, "__len__") else "?")

            if result is None:
                self._dbg("fallback_result_call")
                result = job.result()

            self.after(0, lambda: self._set_progress("Processing audio...", 0.9))

            # Log all non-None result items to help debug path location
            if hasattr(result, "__len__"):
                for i, item in enumerate(result):
                    if item is not None and item != "" and item != []:
                        self._dbg("result_item", index=i, type=type(item).__name__, value=str(item)[:120])

            audio_path = self._extract_audio_path(result)
            self._dbg("audio_path_extracted", path=audio_path)
            if audio_path:
                final_path = self._save_to_musicv1(audio_path, prompt)
                self._dbg("saved", final_path=str(final_path))
                self.after(0, lambda: self._on_done(final_path, prompt))
            else:
                self._dbg("error", reason="no_audio_in_result")
                self.after(0, lambda: self._on_error("No audio in response"))

        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            self._dbg("exception", error=str(e), traceback=tb)
            print(tb, flush=True)
            err_msg = str(e)[:200]
            self.after(0, lambda msg=err_msg: self._on_error(msg))

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

    def _generate_title(self, prompt: str) -> str:
        """Generate a creative 2-3 word song title using Claude Haiku, fallback to heuristic."""
        try:
            import anthropic
            api_key = os.environ.get("ANTHROPIC_API_KEY", "")
            if not api_key:
                # Try loading from .env in agent dir
                env_file = Path(__file__).parent / ".env"
                if env_file.exists():
                    for line in env_file.read_text().splitlines():
                        if line.startswith("ANTHROPIC_API_KEY="):
                            api_key = line.split("=", 1)[1].strip().strip('"')
            if api_key:
                client = anthropic.Anthropic(api_key=api_key)
                msg = client.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=15,
                    messages=[{"role": "user", "content":
                        f"Generate a creative 2-3 word song title for this music prompt: '{prompt}'. "
                        "Reply with ONLY the title. No quotes, no punctuation, no explanation. "
                        "Examples: Midnight Static, Neon Rain, Broken Satellites"}]
                )
                title = msg.content[0].text.strip().strip('"\'').strip()
                self._dbg("title_generated", method="claude", title=title)
                return title
        except Exception as e:
            self._dbg("title_error", error=str(e))

        # Heuristic fallback: capitalize key words from prompt
        import re
        stop = {"a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
                "of", "with", "about", "make", "song", "music", "beat", "track", "me"}
        words = re.sub(r"[^a-z0-9 ]", "", prompt.lower()).split()
        key = [w.capitalize() for w in words if w not in stop][:3]
        title = " ".join(key) if key else "Untitled"
        self._dbg("title_generated", method="heuristic", title=title)
        return title

    def _save_to_musicv1(self, src_path: str, prompt: str) -> Path:
        """Copy the generated file to musicv1/ with a creative song title as filename."""
        import re, shutil
        src = Path(src_path)
        title = self._generate_title(prompt)
        slug = re.sub(r"[^a-z0-9 ]", "", title.lower())
        slug = re.sub(r"\s+", "-", slug.strip())[:40].rstrip("-")
        date = time.strftime("%Y-%m-%d")
        dest = MUSIC_DIR / f"{date}_{slug}{src.suffix}"
        counter = 2
        while dest.exists():
            dest = MUSIC_DIR / f"{date}_{slug}-{counter}{src.suffix}"
            counter += 1
        shutil.copy2(str(src), str(dest))
        return dest

    def _on_done(self, path: Path, prompt: str):
        self._dbg("on_done", path=str(path))
        self._set_progress(f"Done: {path.name}", 1.0)
        self.debug_btn.pack(side="right")
        self.gen_btn.configure(state="normal", text="Generate")
        self._generating = False
        self._add_track(path, prompt, prepend=True)
        threading.Thread(target=self._generate_cover, args=(path, prompt), daemon=True).start()

    def _generate_cover(self, audio_path: Path, prompt: str):
        cover_path = audio_path.with_suffix(".png")
        if cover_path.exists():
            self._dbg("cover_skip", reason="already_exists", path=str(cover_path))
            return
        self._dbg("cover_start", prompt=prompt, output=str(cover_path))
        self.after(0, lambda: self._set_progress("Generating cover art...", 0.5))
        try:
            result = subprocess.run(
                [str(COVER_PYTHON), str(GENERATE_COVER), prompt, str(cover_path)],
                capture_output=True, text=True, timeout=300
            )
            self._dbg("cover_done", returncode=result.returncode,
                      exists=cover_path.exists(),
                      stdout=result.stdout[-200:] if result.stdout else "",
                      stderr=result.stderr[-200:] if result.stderr else "")
            if result.returncode == 0 and cover_path.exists():
                self.after(0, lambda: self._set_progress("Cover art ready", 1.0))
                self.after(0, lambda: self._refresh_track_cover(audio_path, cover_path))
            else:
                self.after(0, lambda: self._set_progress("Cover art failed", 0))
        except Exception as e:
            self._dbg("cover_error", error=str(e))
            self.after(0, lambda: self._set_progress(f"Cover error: {str(e)[:80]}", 0))

    def _on_error(self, msg: str):
        self._dbg("on_error", msg=msg)
        self._set_progress(f"Error: {msg}", 0)
        self.debug_btn.pack(side="right")
        self.gen_btn.configure(state="normal", text="Generate")
        self._generating = False

    def _dbg(self, event: str, **kwargs):
        """Append a timestamped entry to the debug log and print to stdout."""
        entry = {"t": datetime.now().strftime("%H:%M:%S.%f")[:-3], "event": event, **kwargs}
        self._debug_log.append(entry)
        print(f"[DBG {entry['t']}] {event}: {kwargs}", flush=True)

    def _set_progress(self, msg: str, val: float):
        self.progress.set(val)
        self._last_status = msg
        self.progress_label.configure(text=msg, text_color="#475569")

    def _flash(self, msg: str):
        self._last_status = msg
        self.progress_label.configure(text=msg, text_color="#fca5a5")
        self.after(3000, lambda: self.progress_label.configure(text_color="#475569"))

    def _copy_debug(self):
        if not self._debug_log:
            return
        lines = ["=== ARC Music Debug Log ==="]
        for e in self._debug_log:
            t = e["t"]
            ev = e["event"]
            rest = {k: v for k, v in e.items() if k not in ("t", "event")}
            if rest:
                lines.append(f"[{t}] {ev}")
                for k, v in rest.items():
                    val_str = str(v)
                    if len(val_str) > 300:
                        val_str = val_str[:300] + "..."
                    lines.append(f"    {k}: {val_str}")
            else:
                lines.append(f"[{t}] {ev}")
        lines.append("=== end ===")
        payload = "\n".join(lines)
        self.clipboard_clear()
        self.clipboard_append(payload)
        self.debug_btn.configure(text="Copied!")
        self.after(1500, lambda: self.debug_btn.configure(text="Debug"))

    # ------------------------------------------------------------------
    # Track list
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Player
    # ------------------------------------------------------------------

    def _update_speaker(self):
        if self._muted:
            self.speaker_btn.configure(text="🔇", text_color="#64748b")
        elif self._player_proc and not self._player_paused:
            self.speaker_btn.configure(text="🔊", text_color="#a78bfa")
        elif self._player_paused:
            self.speaker_btn.configure(text="🔉", text_color="#64748b")
        else:
            self.speaker_btn.configure(text="🔈", text_color="#334155")

    def _toggle_mute(self):
        self._muted = not self._muted
        if self._muted:
            subprocess.run(["osascript", "-e", "set volume output muted true"],
                           capture_output=True)
        else:
            subprocess.run(["osascript", "-e", "set volume output muted false"],
                           capture_output=True)
        self._update_speaker()

    def _play_row(self, row):
        """Play the track associated with a row widget."""
        if row in self._track_rows:
            self._play_idx(self._track_rows.index(row))

    def _play_idx(self, idx: int):
        """Stop any current playback and start track at idx."""
        self._player_stop()
        if not self._track_rows or idx < 0 or idx >= len(self._track_rows):
            return
        path = self._track_rows[idx]._audio_path
        self._player_idx = idx
        self._player_paused = False
        self._player_proc = subprocess.Popen(
            ["afplay", str(path)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        self.play_btn.configure(text="⏸")
        self.now_playing.configure(text=path.stem[:50], text_color="#c4b5fd")
        self._highlight_row(idx)
        self._update_speaker()
        threading.Thread(target=self._watch_player, args=(self._player_proc,), daemon=True).start()

    def _watch_player(self, proc):
        """When afplay finishes naturally, advance to next track."""
        proc.wait()
        if self._player_proc is proc and not self._player_paused:
            self.after(0, self._next_track)

    def _toggle_play(self):
        import signal
        if self._player_proc is None:
            if self._track_rows:
                self._play_idx(0)
            return
        if self._player_paused:
            try:
                os.kill(self._player_proc.pid, signal.SIGCONT)
            except Exception:
                pass
            self._player_paused = False
            self.play_btn.configure(text="⏸")
        else:
            try:
                os.kill(self._player_proc.pid, signal.SIGSTOP)
            except Exception:
                pass
            self._player_paused = True
            self.play_btn.configure(text="▶")
        self._update_speaker()

    def _next_track(self):
        if not self._track_rows:
            return
        self._play_idx((self._player_idx + 1) % len(self._track_rows))

    def _prev_track(self):
        if not self._track_rows:
            return
        self._play_idx((self._player_idx - 1) % len(self._track_rows))

    def _player_stop(self):
        import signal
        if self._player_proc:
            try:
                os.kill(self._player_proc.pid, signal.SIGCONT)
            except Exception:
                pass
            try:
                self._player_proc.terminate()
                self._player_proc.wait(timeout=1)
            except Exception:
                pass
            self._player_proc = None
        self._player_paused = False
        self.play_btn.configure(text="▶")
        self._update_speaker()

    def _highlight_row(self, idx: int):
        for i, row in enumerate(self._track_rows):
            row.configure(fg_color="#1a1a2e" if i == idx else "#111118")

    def _load_existing_tracks(self):
        files = sorted(
            [f for f in MUSIC_DIR.iterdir()
             if f.suffix in (".mp3", ".wav", ".flac") and f.is_file()],
            key=lambda f: f.stat().st_mtime, reverse=True
        )[:20]
        for f in files:
            self._add_track(f, f.stem.replace("-", " "))

    def _add_track(self, path: Path, prompt: str, prepend: bool = False):
        row = ctk.CTkFrame(
            self.track_list,
            fg_color="#111118",
            corner_radius=8,
        )
        if prepend:
            children = self.track_list.winfo_children()
            if children:
                row.pack(fill="x", pady=3, before=children[0])
            else:
                row.pack(fill="x", pady=3)
            self._track_rows.insert(0, row)
        else:
            row.pack(fill="x", pady=3)
            self._track_rows.append(row)
        row._audio_path = path  # store for cover refresh

        # Thumbnail (48x48)
        cover_path = path.with_suffix(".png")
        thumb_label = ctk.CTkLabel(row, text="", width=48, height=48, cursor="hand2")
        thumb_label.pack(side="left", padx=(8, 0), pady=6)
        self._set_thumb(thumb_label, cover_path)
        thumb_label.bind("<Button-1>", lambda e, r=row: self._play_row(r))

        name_label = ctk.CTkLabel(
            row,
            text=path.stem[:52],
            font=ctk.CTkFont(size=12),
            text_color="#c4b5fd",
            anchor="w",
        )
        name_label.pack(side="left", padx=10, pady=8, fill="x", expand=True)
        name_label.bind("<Button-1>", lambda e, r=row: self._play_row(r))

        # Hover play button - overlaid with place(), never affects pack layout
        hover_play = ctk.CTkButton(
            row, text="▶",
            width=36, height=28,
            corner_radius=6,
            fg_color="#7c3aed",
            hover_color="#6d28d9",
            font=ctk.CTkFont(size=13),
            text_color="white",
            command=lambda r=row: self._play_row(r),
        )
        # Don't pack/grid hover_play - use place overlay so it never shifts layout

        def on_enter(e, btn=hover_play, r=row):
            btn.place(relx=1.0, rely=0.5, anchor="e", x=-8)
            btn.lift()

        def on_leave(e, btn=hover_play, r=row):
            dest = e.widget.winfo_containing(e.x_root, e.y_root)
            if dest is not None and _widget_in_subtree(dest, r):
                return
            btn.place_forget()

        for w in [row, thumb_label, name_label, hover_play]:
            w.bind("<Enter>", on_enter)
            w.bind("<Leave>", on_leave)

    def _set_thumb(self, label: ctk.CTkLabel, cover_path: Path):
        """Load cover image into label, or show purple placeholder."""
        if cover_path.exists():
            try:
                img = Image.open(cover_path).resize((48, 48), Image.LANCZOS)
                ctk_img = ctk.CTkImage(img, size=(48, 48))
                label.configure(image=ctk_img, text="")
                label._ctk_image = ctk_img  # prevent GC
                return
            except Exception:
                pass
        # Placeholder - purple square
        img = Image.new("RGB", (48, 48), "#2d0a5e")
        ctk_img = ctk.CTkImage(img, size=(48, 48))
        label.configure(image=ctk_img, text="")
        label._ctk_image = ctk_img

    def _refresh_track_cover(self, audio_path: Path, cover_path: Path):
        """Update thumbnail in track list once cover is ready."""
        for widget in self.track_list.winfo_children():
            if getattr(widget, "_audio_path", None) == audio_path:
                for child in widget.winfo_children():
                    if isinstance(child, ctk.CTkLabel) and child.cget("width") == 48:
                        self._set_thumb(child, cover_path)
                        break


if __name__ == "__main__":
    app = MusicApp()
    app.mainloop()
