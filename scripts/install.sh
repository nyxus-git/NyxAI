#!/usr/bin/env bash
# scripts/install.sh — Automated Installer for NyxAI (Arch / EndeavourOS / Hyprland)
# Sets up Python virtualenv, UI build, systemd user services, and desktop shortcuts.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=========================================="
echo "      NyxAI System Installer 🌙          "
echo "=========================================="
echo "Target: Arch Linux / EndeavourOS / Hyprland"
echo "Root:   $ROOT_DIR"
echo ""

# 1. Dependency checks
echo "[1/6] Checking system prerequisites..."

if ! command -v python3 >/dev/null 2>&1; then
    echo "Error: python3 is not installed." >&2
    exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
    echo "Error: npm / nodejs is not installed." >&2
    exit 1
fi

if ! command -v ollama >/dev/null 2>&1; then
    echo "Warning: ollama is not found in PATH. Please install Ollama from https://ollama.ai"
else
    echo "  ✓ Ollama found: $(command -v ollama)"
fi

echo "  ✓ Python: $(python3 --version)"
echo "  ✓ Node:   $(node --version)"
echo "  ✓ npm:    $(npm --version)"

# 2. Python environment
echo ""
echo "[2/6] Setting up Python virtual environment..."
if [ ! -d "$ROOT_DIR/.venv" ]; then
    python3 -m venv "$ROOT_DIR/.venv"
fi

"$ROOT_DIR/.venv/bin/pip" install --upgrade pip
"$ROOT_DIR/.venv/bin/pip" install -r "$ROOT_DIR/requirements.txt"
echo "  ✓ Python dependencies installed."

# 3. Environment configuration
echo ""
echo "[3/6] Configuring environment (.env)..."
if [ ! -f "$ROOT_DIR/.env" ]; then
    if [ -f "$ROOT_DIR/.env.example" ]; then
        cp "$ROOT_DIR/.env.example" "$ROOT_DIR/.env"
        echo "  ✓ Copied .env.example to .env"
    fi
else
    echo "  ✓ Existing .env found."
fi

# 4. Companion UI Build
echo ""
echo "[4/6] Building Companion Web UI..."
if [ -d "$ROOT_DIR/apps/companion" ]; then
    (
        cd "$ROOT_DIR/apps/companion"
        npm install
        npm run build
    )
    echo "  ✓ Companion UI built successfully."
fi

# 5. Systemd User Units
echo ""
echo "[5/6] Installing systemd user units..."
SYSTEMD_USER_DIR="$HOME/.config/systemd/user"
mkdir -p "$SYSTEMD_USER_DIR"

for unit in nyxai-core.service nyxai-ui.service nyxai-voice.service; do
    src="$ROOT_DIR/deployment/systemd/$unit"
    dest="$SYSTEMD_USER_DIR/$unit"
    if [ -f "$src" ]; then
        cp "$src" "$dest"
        echo "  ✓ Installed $unit -> $dest"
    fi
done

systemctl --user daemon-reload
echo "  ✓ systemd user daemon reloaded."

# Make scripts executable
chmod +x "$ROOT_DIR/scripts/run.sh" "$ROOT_DIR/scripts/install.sh" "$ROOT_DIR/apps/desktop/main.py"

# 6. Activation and Hyprland guidance
echo ""
echo "[6/6] Installation Complete!"
echo "=========================================="
echo "To enable and start NyxAI persistent services automatically on login:"
echo "    systemctl --user enable --now nyxai-core.service nyxai-ui.service"
echo ""
echo "To manage services at any time:"
echo "    $ROOT_DIR/scripts/run.sh start"
echo "    $ROOT_DIR/scripts/run.sh status"
echo "    $ROOT_DIR/scripts/run.sh logs"
echo ""
echo "For Hyprland desktop integration, add these lines to ~/.config/hypr/hyprland.conf:"
echo "--------------------------------------------------"
echo "# NyxAI Companion & Voice Keybindings"
echo "bind = SUPER, J, exec, $ROOT_DIR/scripts/run.sh toggle"
echo "bind = SUPER, SPACE, exec, $ROOT_DIR/scripts/run.sh ptt"
echo "--------------------------------------------------"
echo "=========================================="
