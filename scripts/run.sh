#!/usr/bin/env bash
# scripts/run.sh — NyxAI Lifecycle & Service Manager
# Supports systemd user unit management and direct foreground development mode.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON="$ROOT_DIR/.venv/bin/python"

SERVICES=("nyxai-core" "nyxai-ui" "nyxai-voice")

usage() {
    cat <<EOF
NyxAI Service & Lifecycle Manager

Usage:
    ./scripts/run.sh [command]

Commands:
    start       Start all NyxAI systemd user services
    stop        Stop all NyxAI systemd user services
    restart     Restart all NyxAI systemd user services
    status      Check status of systemd units and backend endpoints
    logs        Follow unified journalctl logs for all NyxAI services
    dev         Run Core backend and Companion UI in foreground dev mode
    toggle      Toggle Companion UI window (SUPER + J)
    ptt         Trigger push-to-talk voice interaction (SUPER + SPACE)
    help        Show this message
EOF
}

cmd="${1:-status}"

case "$cmd" in
    start)
        echo "Starting NyxAI services..."
        systemctl --user start "${SERVICES[@]}"
        echo "Services started."
        $PYTHON "$ROOT_DIR/apps/desktop/main.py" status || true
        ;;
    stop)
        echo "Stopping NyxAI services..."
        systemctl --user stop "${SERVICES[@]}"
        echo "Services stopped."
        ;;
    restart)
        echo "Restarting NyxAI services..."
        systemctl --user restart "${SERVICES[@]}"
        echo "Services restarted."
        $PYTHON "$ROOT_DIR/apps/desktop/main.py" status || true
        ;;
    status)
        echo "=== Systemd User Unit Status ==="
        for s in "${SERVICES[@]}"; do
            state=$(systemctl --user is-active "$s" 2>/dev/null || echo "inactive")
            printf "  %-18s: %s\n" "$s" "$state"
        done
        echo ""
        $PYTHON "$ROOT_DIR/apps/desktop/main.py" status || true
        ;;
    logs)
        echo "Streaming logs from NyxAI services (Ctrl+C to stop)..."
        exec journalctl --user -u nyxai-core -u nyxai-ui -u nyxai-voice -f
        ;;
    dev)
        echo "Starting NyxAI in foreground development mode..."
        trap 'echo "Stopping dev servers..."; kill $(jobs -p) 2>/dev/null || true' EXIT INT TERM
        
        # 1. Start core backend
        "$ROOT_DIR/.venv/bin/uvicorn" api.app.main:app --reload --host 127.0.0.1 --port 8000 &
        BACKEND_PID=$!
        
        # 2. Wait for backend to be ready
        echo "Waiting for core backend on http://127.0.0.1:8000..."
        for _ in {1..30}; do
            if curl -s http://127.0.0.1:8000/health >/dev/null 2>&1; then
                echo "Backend is ready!"
                break
            fi
            sleep 0.5
        done
        
        # 3. Start companion UI dev server
        if [ -d "$ROOT_DIR/apps/companion" ]; then
            echo "Starting Companion UI dev server..."
            (cd "$ROOT_DIR/apps/companion" && npm run dev) &
            UI_PID=$!
        fi
        
        wait
        ;;
    toggle)
        exec "$PYTHON" "$ROOT_DIR/apps/desktop/main.py" toggle-ui
        ;;
    ptt)
        exec "$PYTHON" "$ROOT_DIR/apps/desktop/main.py" ptt
        ;;
    help|--help|-h)
        usage
        ;;
    *)
        echo "Unknown command: $cmd"
        usage
        exit 1
        ;;
esac
