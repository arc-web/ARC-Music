#!/usr/bin/env python3
"""
Cover art generator for ARC Music.
Called as a subprocess after each song is generated.
Uses FLUX.1-schnell via mflux (native Apple Silicon MLX).

Usage:
  python generate_cover.py "dark trap song about late nights" /path/to/output.png
"""
import re
import subprocess
import sys
from pathlib import Path

FLUX_BIN = Path(__file__).parent / ".venv_flux" / "bin" / "mflux-generate"


def music_prompt_to_visual(prompt: str) -> str:
    """
    Expand a music generation prompt into a rich visual cover art prompt.
    Maps genre/mood keywords to visual aesthetics.
    """
    p = prompt.lower()

    # Genre → visual style
    styles = []
    if any(w in p for w in ["trap", "drill", "hip hop", "rap"]):
        styles.append("urban streetwear aesthetic, city at night, neon reflections on wet pavement")
    if any(w in p for w in ["lo-fi", "lofi", "chill"]):
        styles.append("cozy room, anime-style illustration, soft warm light, rain on window")
    if any(w in p for w in ["ambient", "atmospheric", "drone"]):
        styles.append("vast landscape, misty mountains, minimalist, ethereal fog")
    if any(w in p for w in ["electronic", "edm", "house", "techno"]):
        styles.append("geometric shapes, laser grid, synthwave neon colors, futuristic")
    if any(w in p for w in ["jazz"]):
        styles.append("smoky jazz club, warm amber light, art deco style")
    if any(w in p for w in ["cinematic", "orchestral", "epic"]):
        styles.append("dramatic cinematic scene, wide angle, god rays, epic scale")
    if any(w in p for w in ["soul", "r&b", "rnb"]):
        styles.append("golden hour light, warm tones, intimate portrait style")
    if any(w in p for w in ["rock", "metal", "punk"]):
        styles.append("dark dramatic lighting, gritty texture, raw energy")
    if any(w in p for w in ["reggaeton", "afrobeats", "latin"]):
        styles.append("vibrant tropical colors, warm sunset, energetic street scene")

    # Mood → color palette
    palette = []
    if any(w in p for w in ["dark", "menacing", "aggressive", "drill"]):
        palette.append("dark color palette, deep purples and blacks")
    if any(w in p for w in ["melancholic", "sad", "emotional"]):
        palette.append("muted blues and grays, moody atmosphere")
    if any(w in p for w in ["uplifting", "happy", "energetic", "upbeat"]):
        palette.append("bright warm colors, golden yellows and oranges")
    if any(w in p for w in ["dreamy", "ethereal", "soft"]):
        palette.append("pastel colors, soft gradients, dreamlike quality")

    # Build final prompt
    base = f"album cover art, square format, professional music cover"
    visual_style = ", ".join(styles) if styles else "abstract artistic composition, textured background"
    color = ", ".join(palette) if palette else "rich colors"

    # Include key words from original prompt
    keywords = re.sub(r"[^a-z0-9 ]", "", p)
    keywords = " ".join(w for w in keywords.split() if len(w) > 3 and w not in
                        {"with", "that", "this", "from", "have", "will", "make", "song", "music", "beat"})[:80]

    return f"{base}, {visual_style}, {color}, {keywords}, highly detailed, 4k, trending on artstation"


def generate(prompt: str, output_path: str, seed: int = 42) -> bool:
    visual_prompt = music_prompt_to_visual(prompt)
    print(f"Visual prompt: {visual_prompt[:100]}...")

    cmd = [
        str(FLUX_BIN),
        "--model", "schnell",
        "--quantize", "4",         # 4-bit quantization: ~8GB, fast
        "--prompt", visual_prompt,
        "--output", output_path,
        "--height", "1024",
        "--width", "1024",
        "--steps", "4",            # schnell sweet spot
        "--seed", str(seed),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error: {result.stderr[-300:]}", file=sys.stderr)
        return False

    print(f"Saved: {output_path}")
    return True


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: generate_cover.py <prompt> <output.png> [seed]")
        sys.exit(1)

    prompt = sys.argv[1]
    output = sys.argv[2]
    seed = int(sys.argv[3]) if len(sys.argv) > 3 else 42

    ok = generate(prompt, output, seed)
    sys.exit(0 if ok else 1)
