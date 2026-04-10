#!/usr/bin/env bash
# One-command setup for music_agent
set -e

AGENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$AGENT_DIR"

echo "==> Checking Python 3.12..."
if ! command -v python3.12 &>/dev/null; then
    echo "ERROR: python3.12 not found. Install with: brew install python@3.12"
    exit 1
fi

echo "==> Creating virtual environment..."
python3.12 -m venv .venv

echo "==> Installing dependencies..."
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install -r ace_step_1_5/requirements.txt
.venv/bin/pip install -e ace_step_1_5/

echo ""
echo "Setup complete."
echo ""
echo "Next steps:"
echo "  Start API server:  ./start_server.sh"
echo "  Start Gradio UI:   ./start_ui.sh"
echo "  Generate music:    source .venv/bin/activate && python music_agent.py generate --prompt 'lo-fi hip hop'"
