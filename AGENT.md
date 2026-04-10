# Music Agent

A music generation agent powered by [ACE-Step 1.5](https://github.com/ace-step/ACE-Step-1.5) - an open-source foundation model for commercial-grade audio generation.

## Capabilities

- **Text-to-music** - Generate full songs from natural language descriptions
- **Lyrics support** - Pass optional lyrics (50+ languages)
- **Audio editing** - Cover generation, selective repaint, track separation
- **Metadata extraction** - BPM, key, time signature, lyric timestamps
- **LoRA fine-tuning** - Personalization from minimal audio samples
- **Batch generation** - Up to 8 songs simultaneously

## Setup

```bash
# Requires Python 3.11-3.12 (NOT 3.13)
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r ace_step_1_5/requirements.txt
pip install -e ace_step_1_5/
```

Or use the convenience script:
```bash
./setup.sh
```

## Start the API server

```bash
./start_server.sh
# API available at http://localhost:7865
```

## Start the Gradio UI

```bash
./start_ui.sh
# UI available at http://localhost:7860
```

## Python Usage

```python
from music_agent import MusicAgent

agent = MusicAgent()

# Generate from a prompt
result = agent.generate(
    prompt="upbeat lo-fi hip hop with soft piano and rain sounds",
    duration=60,
    output_path="output.mp3"
)

# Generate with lyrics
result = agent.generate(
    prompt="melancholic indie folk with acoustic guitar",
    lyrics="Verse 1:\nWalking through the empty streets...",
    duration=120,
    output_path="song.mp3"
)

# Analyze existing audio
metadata = agent.analyze("my_song.mp3")
print(metadata)  # {caption, bpm, key, language}
```

## CLI Usage

```bash
# Generate via prompt
python music_agent.py generate --prompt "dark ambient electronic" --duration 60 --output output.mp3

# Analyze audio
python music_agent.py analyze --input my_song.mp3

# Launch interactive wizard (ace-step CLI)
python ace_step_1_5/cli.py
```

## Environment Variables

Copy `.env.example` to `.env` and configure:

```
ACESTEP_API_KEY=        # optional, enables auth on the API server
ACESTEP_QUEUE_MAXSIZE=200
```

## Structure

```
music_agent/
  ace_step_1_5/     - cloned ACE-Step-1.5 repo
  .venv/            - Python 3.12 virtual environment
  music_agent.py    - main agent wrapper
  setup.sh          - one-command setup script
  start_server.sh   - launch API server
  start_ui.sh       - launch Gradio UI
  .env.example      - environment variable template
  AGENT.md          - this file
```

## Hardware Notes

- Minimum: 4GB VRAM (DiT-only mode, no LLM)
- Recommended: 12GB+ VRAM for full model
- Apple Silicon: uses MLX acceleration automatically
- Models download automatically on first run from HuggingFace
