#!/usr/bin/env python3
"""
File watcher for musicv1/ - watches for new ACE-Step output files,
renames them from UUID format to readable names using their JSON metadata,
and flattens them from batch subdirs into the musicv1 root.

Run: python file_watcher.py
"""
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path

MUSIC_DIR = Path(__file__).parent / "musicv1"
POLL_INTERVAL = 2.0  # seconds


def slug(text: str, max_len: int = 50) -> str:
    """Turn a caption into a safe filename slug."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9 ]", "", text)
    text = re.sub(r"\s+", "-", text.strip())
    return text[:max_len].rstrip("-")


def readable_name(json_path: Path) -> str | None:
    """Build a readable filename from ACE-Step JSON metadata."""
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except Exception:
        return None

    caption = (
        data.get("caption")
        or data.get("prompt")
        or data.get("lm_metadata", {}).get("caption")
        or ""
    ).strip()

    if not caption:
        return None

    date = time.strftime("%Y-%m-%d")
    seed = data.get("seed") or data.get("manual_seeds", [None])[0]
    seed_suffix = f"_s{seed}" if seed else ""
    name_slug = slug(caption)

    return f"{date}_{name_slug}{seed_suffix}"


def process_batch_dir(batch_dir: Path) -> int:
    """
    Process one batch_* subdirectory:
    - Find mp3/wav/flac pairs with their JSON sidecar
    - Rename and move to musicv1 root with readable names
    - Remove empty batch dir when done

    Returns count of files moved.
    """
    moved = 0
    audio_exts = {".mp3", ".wav", ".flac", ".aac", ".opus"}

    for json_file in batch_dir.glob("*.json"):
        stem = json_file.stem
        # Find matching audio file
        audio_file = None
        for ext in audio_exts:
            candidate = batch_dir / f"{stem}{ext}"
            if candidate.exists():
                audio_file = candidate
                break

        if not audio_file:
            continue

        name = readable_name(json_file)
        if not name:
            # Fallback: use timestamp + original stem
            name = f"{time.strftime('%Y-%m-%d')}_{stem[:16]}"

        # Avoid collisions
        dest_audio = MUSIC_DIR / f"{name}{audio_file.suffix}"
        dest_json = MUSIC_DIR / f"{name}.json"
        counter = 1
        while dest_audio.exists():
            dest_audio = MUSIC_DIR / f"{name}_{counter}{audio_file.suffix}"
            dest_json = MUSIC_DIR / f"{name}_{counter}.json"
            counter += 1

        shutil.move(str(audio_file), str(dest_audio))
        shutil.move(str(json_file), str(dest_json))
        print(f"  -> {dest_audio.name}")
        moved += 1

    # Clean up empty batch dir
    remaining = list(batch_dir.iterdir())
    if not remaining:
        batch_dir.rmdir()

    return moved


def watch():
    print(f"Watching {MUSIC_DIR} for new music files...")
    print("Files will be renamed and moved to musicv1 root.")
    print("Press Ctrl+C to stop.\n")

    seen_dirs: set[str] = set()

    while True:
        if not MUSIC_DIR.exists():
            time.sleep(POLL_INTERVAL)
            continue

        for entry in MUSIC_DIR.iterdir():
            if not entry.is_dir() or not entry.name.startswith("batch_"):
                continue
            if entry.name in seen_dirs:
                continue

            # Wait briefly to ensure ACE-Step has finished writing
            time.sleep(1.5)

            # Only process dirs where all audio files are done (no .tmp files)
            tmp_files = list(entry.glob("*.tmp")) + list(entry.glob("*.part"))
            if tmp_files:
                continue

            print(f"Processing {entry.name}:")
            n = process_batch_dir(entry)
            if n == 0:
                # Dir exists but no complete pairs yet - skip for now
                pass
            else:
                seen_dirs.add(entry.name)

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    MUSIC_DIR.mkdir(exist_ok=True)
    try:
        watch()
    except KeyboardInterrupt:
        print("\nStopped.")
