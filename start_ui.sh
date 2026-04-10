#!/usr/bin/env bash
# Launch ACE-Step 1.5 Gradio UI - optimized for M4 Max (MLX backend)
# All generated music saved to: music_agent/musicv1/
set -e

AGENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Add uv to PATH if needed
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

if ! command -v uv &>/dev/null; then
    echo "uv not found - install with: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

echo "=============================="
echo "  ACE-Step 1.5 - M4 Max MLX"
echo "  Output: $AGENT_DIR/musicv1/"
echo "=============================="
echo ""
echo "Gradio UI -> http://127.0.0.1:7860"
echo ""

cd "$AGENT_DIR/ace_step_1_5"
exec bash start_gradio_ui_macos.sh
