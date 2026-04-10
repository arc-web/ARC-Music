#!/usr/bin/env bash
# Launch ACE-Step 1.5 REST API server - optimized for M4 Max (MLX backend)
set -e

AGENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

if ! command -v uv &>/dev/null; then
    echo "uv not found - install with: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

echo "=============================="
echo "  ACE-Step 1.5 API - M4 Max"
echo "=============================="
echo ""
echo "API -> http://127.0.0.1:8001"
echo "Docs -> http://127.0.0.1:8001/docs"
echo ""

cd "$AGENT_DIR/ace_step_1_5"
exec bash start_api_server_macos.sh
