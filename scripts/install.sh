#!/usr/bin/env bash
# scripts/install.sh — Cross-DE Linux Installer for NyxAI
# Designed for EndeavourOS / Arch Linux (KDE Plasma, GNOME, XFCE, Hyprland)
# and also supports Debian/Ubuntu and Fedora.
#
# Workflow:
#   git clone ... && cd NyxAI && ./scripts/install.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

MODEL_NAME="${OLLAMA_MODEL:-qwen2.5:3b}"
AUTO_YES=false
SKIP_MODEL=false
ENABLE_SERVICE=false

for arg in "$@"; do
    case "$arg" in
        -y|--yes) AUTO_YES=true ;;
        --skip-model) SKIP_MODEL=true ;;
        --enable-service) ENABLE_SERVICE=true ;;
        --model=*) MODEL_NAME="${arg#*=}" ;;
        -h|--help)
            cat <<EOF
NyxAI Linux Installer

Usage: ./scripts/install.sh [options]
  -y, --yes           Non-interactive install with defaults
  --model=<name>      Ollama model to pull (default: qwen2.5:3b)
  --skip-model        Skip pulling the Ollama model
  --enable-service    Enable systemd user service (nyxai-core) at login
EOF
            exit 0
            ;;
    esac
done

echo "=================================================="
echo "   NyxAI Desktop AI Companion Installer"
echo "=================================================="
echo "Project Root : $ROOT_DIR"
echo "Desktop Env  : ${XDG_CURRENT_DESKTOP:-Unknown} (${XDG_SESSION_TYPE:-Unknown})"
echo "Target Model : $MODEL_NAME"
echo ""

# ── 1. System Package Detection & Installation ───────────────────────────────
echo "[1/7] Checking system packages..."

detect_pkg_manager() {
    if command -v pacman >/dev/null 2>&1; then
        echo "pacman"
    elif command -v apt-get >/dev/null 2>&1; then
        echo "apt"
    elif command -v dnf >/dev/null 2>&1; then
        echo "dnf"
    else
        echo "unknown"
    fi
}

PKG_MGR="$(detect_pkg_manager)"
MISSING_CORE=()
for cmd in python3 node npm ffmpeg curl; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        MISSING_CORE+=("$cmd")
    fi
done

if [ "$PKG_MGR" = "pacman" ]; then
    ARCH_PKGS=()
    command -v python3 >/dev/null 2>&1 || ARCH_PKGS+=(python)
    command -v node >/dev/null 2>&1 || ARCH_PKGS+=(nodejs npm)
    command -v ffmpeg >/dev/null 2>&1 || ARCH_PKGS+=(ffmpeg)
    command -v curl >/dev/null 2>&1 || ARCH_PKGS+=(curl)
    command -v espeak-ng >/dev/null 2>&1 || ARCH_PKGS+=(espeak-ng)
    pacman -Qq portaudio >/dev/null 2>&1 || ARCH_PKGS+=(portaudio)
    pacman -Qq qt6-webengine >/dev/null 2>&1 || ARCH_PKGS+=(qt6-webengine)

    if [ ${#ARCH_PKGS[@]} -gt 0 ]; then
        echo "  Missing Arch packages: ${ARCH_PKGS[*]}"
        if [ "$AUTO_YES" = true ]; then
            sudo pacman -Sy --needed --noconfirm "${ARCH_PKGS[@]}"
        else
            read -r -p "  Install missing Arch packages via sudo pacman? [Y/n] " ans
            if [[ -z "$ans" || "$ans" =~ ^[Yy]$ ]]; then
                sudo pacman -Sy --needed "${ARCH_PKGS[@]}"
            fi
        fi
    fi
elif [ ${#MISSING_CORE[@]} -gt 0 ]; then
    echo "  Missing tools (${MISSING_CORE[*]})."
    if [ "$PKG_MGR" = "apt" ]; then
        echo "  Installing via apt..."
        sudo apt-get update && sudo apt-get install -y python3 python3-venv python3-pip nodejs npm ffmpeg espeak-ng portaudio19-dev curl
    elif [ "$PKG_MGR" = "dnf" ]; then
        echo "  Installing via dnf..."
        sudo dnf install -y python3 python3-pip nodejs npm ffmpeg espeak-ng portaudio-devel curl
    else
        echo "  Error: Please install ${MISSING_CORE[*]} manually and re-run." >&2
        exit 1
    fi
fi

# Verify Ollama
if ! command -v ollama >/dev/null 2>&1; then
    echo "  Ollama not found."
    if [ "$PKG_MGR" = "pacman" ]; then
        read -r -p "  Install Ollama via pacman (recommended)? [Y/n] " ans || ans="y"
        if [[ -z "$ans" || "$ans" =~ ^[Yy]$ ]]; then
            sudo pacman -Sy --needed ollama
        fi
    else
        echo "  Install Ollama from https://ollama.com/download and ensure 'ollama serve' is running."
    fi
fi

echo "  ✓ Python : $(python3 --version)"
echo "  ✓ Node   : $(node --version)"
echo "  ✓ npm    : $(npm --version)"
command -v ollama >/dev/null 2>&1 && echo "  ✓ Ollama : $(ollama --version 2>/dev/null || command -v ollama)"

# ── 2. Python Virtual Environment & Dependencies ─────────────────────────────
echo ""
echo "[2/7] Setting up Python environment (.venv)..."
if [ ! -d "$ROOT_DIR/.venv" ]; then
    python3 -m venv "$ROOT_DIR/.venv"
fi

"$ROOT_DIR/.venv/bin/python" -m pip install --upgrade pip
"$ROOT_DIR/.venv/bin/python" -m pip install -r "$ROOT_DIR/requirements.txt"
echo "  ✓ Python + PyQt6 WebEngine dependencies installed."

# ── 3. Environment File (.env) ───────────────────────────────────────────────
echo ""
echo "[3/7] Configuring .env..."
if [ ! -f "$ROOT_DIR/.env" ]; then
    if [ -f "$ROOT_DIR/.env.example" ]; then
        cp "$ROOT_DIR/.env.example" "$ROOT_DIR/.env"
    else
        cat > "$ROOT_DIR/.env" <<EOF
APP_NAME=NyxAI
HOST=127.0.0.1
PORT=8000
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=$MODEL_NAME
TTS_ENGINE=kokoro
TTS_VOICE=af_heart
EOF
    fi
    echo "  ✓ Created .env"
else
    echo "  ✓ Existing .env preserved."
fi

# ── 4. Ollama Service & Model Pull ───────────────────────────────────────────
echo ""
echo "[4/7] Setting up local AI model ($MODEL_NAME)..."
if [ "$SKIP_MODEL" = false ] && command -v ollama >/dev/null 2>&1; then
    if ! curl -sf http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
        echo "  Starting Ollama daemon..."
        if command -v systemctl >/dev/null 2>&1 && systemctl list-unit-files ollama.service >/dev/null 2>&1; then
            sudo systemctl enable --now ollama || (nohup ollama serve >/tmp/nyxai-ollama.log 2>&1 &)
        else
            nohup ollama serve >/tmp/nyxai-ollama.log 2>&1 &
        fi
        sleep 2
    fi

    if curl -sf http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
        if [ "$AUTO_YES" = false ]; then
            read -r -p "  Ollama model to install [$MODEL_NAME]: " custom_model || custom_model=""
            if [ -n "${custom_model:-}" ]; then
                MODEL_NAME="$custom_model"
                sed -i "s/^OLLAMA_MODEL=.*/OLLAMA_MODEL=$MODEL_NAME/" "$ROOT_DIR/.env" || true
            fi
        fi
        echo "  Pulling $MODEL_NAME (this may take a few minutes the first time)..."
        ollama pull "$MODEL_NAME"
        echo "  ✓ Model $MODEL_NAME ready."
    else
        echo "  ! Ollama daemon is not responding yet. Run 'ollama serve && ollama pull $MODEL_NAME' manually."
    fi
else
    echo "  Skipped model pull."
fi

# ── 5. Build Companion Frontend ──────────────────────────────────────────────
echo ""
echo "[5/7] Building Companion UI..."
if [ -d "$ROOT_DIR/apps/companion" ]; then
    (
        cd "$ROOT_DIR/apps/companion"
        npm install --no-audit --no-fund
        npm run build
    )
    # Cache optional MediaPipe FaceLandmarker model locally for 100% offline photo alignment
    TASK_DEST="$ROOT_DIR/apps/companion/dist/mediapipe/face_landmarker.task"
    if [ ! -f "$TASK_DEST" ]; then
        mkdir -p "$(dirname "$TASK_DEST")"
        curl -fsSL \
            "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task" \
            -o "$TASK_DEST" || echo "  (Optional offline landmark model skipped; manual alignment still available)"
    fi
    echo "  ✓ Companion UI built into apps/companion/dist/."
fi

# ── 6. Install Dedicated Desktop Launcher & Command ──────────────────────────
echo ""
echo "[6/7] Installing NyxAI Desktop App & CLI launcher..."
mkdir -p "$HOME/.local/bin" "$HOME/.local/share/applications"

cat > "$HOME/.local/bin/nyxai" <<EOF
#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$ROOT_DIR"
PYTHON="\$ROOT_DIR/.venv/bin/python"

case "\${1:-app}" in
    app|open|ui)
        exec "\$PYTHON" "\$ROOT_DIR/apps/desktop/desktop_app.py" --action show
        ;;
    toggle)
        exec "\$PYTHON" "\$ROOT_DIR/apps/desktop/desktop_app.py" --action toggle
        ;;
    status|ptt|start|stop|restart|logs|dev)
        exec "\$ROOT_DIR/scripts/run.sh" "\$@"
        ;;
    *)
        exec "\$PYTHON" "\$ROOT_DIR/apps/desktop/desktop_app.py" "\$@"
        ;;
esac
EOF
chmod +x "$HOME/.local/bin/nyxai"

cat > "$HOME/.local/share/applications/nyxai.desktop" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=NyxAI
GenericName=AI Girl Companion & Desktop Agent
Comment=Local-first animated AI companion and Linux desktop agent
Exec=$HOME/.local/bin/nyxai app
Icon=$ROOT_DIR/apps/companion/public/favicon.svg
Terminal=false
Categories=Utility;Development;ArtificialIntelligence;
StartupWMClass=nyxai
Keywords=ai;assistant;companion;agent;nyx;
EOF

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$HOME/.local/share/applications" >/dev/null 2>&1 || true
fi

chmod +x "$ROOT_DIR/scripts/run.sh" "$ROOT_DIR/scripts/install.sh" "$ROOT_DIR/apps/desktop/main.py" "$ROOT_DIR/apps/desktop/desktop_app.py"
echo "  ✓ Installed launcher: $HOME/.local/bin/nyxai"
echo "  ✓ Installed desktop entry: $HOME/.local/share/applications/nyxai.desktop"

# ── 7. Install Templated Systemd User Units ──────────────────────────────────
echo ""
echo "[7/7] Installing systemd user units (using $ROOT_DIR)..."
SYSTEMD_USER_DIR="$HOME/.config/systemd/user"
mkdir -p "$SYSTEMD_USER_DIR"

for unit in nyxai-core.service nyxai-ui.service nyxai-voice.service; do
    src="$ROOT_DIR/deployment/systemd/$unit"
    dest="$SYSTEMD_USER_DIR/$unit"
    if [ -f "$src" ]; then
        sed "s|%h/Projects/NyxAI|$ROOT_DIR|g" "$src" > "$dest"
        echo "  ✓ Installed $unit -> $dest"
    fi
done

if command -v systemctl >/dev/null 2>&1; then
    systemctl --user daemon-reload || true
    if [ "$ENABLE_SERVICE" = true ]; then
        systemctl --user enable --now nyxai-core.service || true
    fi
fi

echo ""
echo "=================================================="
echo "  NyxAI Setup Complete!"
echo "=================================================="
echo "Launch the dedicated desktop app anytime:"
echo "  1. Open 'NyxAI' from your KDE / GNOME / Linux Application Menu"
echo "  2. Or run in terminal:  nyxai   (ensure ~/.local/bin is in PATH)"
echo ""
echo "Tip (KDE Plasma shortcut):"
echo "  System Settings -> Keyboard -> Shortcuts -> Add New -> Command"
echo "  Command: $HOME/.local/bin/nyxai toggle   (e.g. Meta+J)"
echo "=================================================="
