#!/usr/bin/env python3
"""
apps/desktop/desktop_app.py

Dedicated native Linux Desktop App for NyxAI using PyQt6 + Qt6 WebEngine.
Works across EndeavourOS KDE Plasma, GNOME, XFCE, Hyprland, Sway (Wayland & X11).

Features:
  - Native desktop window (no browser tabs or address bar)
  - Auto-starts local FastAPI backend if not already running
  - Auto-grants local microphone & audio permissions for voice chat
  - System Tray icon with Show/Hide, Always-on-Top, and Quit controls
  - Single-instance Unix socket so launching again focuses existing window
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Configure Chromium WebEngine flags cleanly before QApplication initialization.
# Enables autoplay for TTS responses and smooth WebGL rendering on Linux/Wayland.
_DEFAULT_CHROMIUM_FLAGS = "--autoplay-policy=no-user-gesture-required --ignore-gpu-blocklist"
if "QTWEBENGINE_CHROMIUM_FLAGS" not in os.environ:
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = _DEFAULT_CHROMIUM_FLAGS

from PyQt6.QtCore import QTimer, Qt, QUrl
from PyQt6.QtGui import QAction, QColor, QIcon
from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QMenu,
    QSystemTrayIcon,
)

BACKEND_HOST = os.getenv("NYXAI_HOST", "127.0.0.1")
BACKEND_PORT = int(os.getenv("NYXAI_PORT", "8000"))
APP_URL = os.getenv("NYXAI_APP_URL", f"http://{BACKEND_HOST}:{BACKEND_PORT}")
SINGLE_INSTANCE_KEY = "nyxai-desktop-app-instance"
ICON_PATH = PROJECT_ROOT / "apps" / "companion" / "public" / "favicon.svg"


def is_backend_ready(url: str = APP_URL, timeout: float = 1.0) -> bool:
    """Return True if a NyxAI FastAPI backend /health endpoint responds cleanly."""
    try:
        with urllib.request.urlopen(f"{url}/health", timeout=timeout) as resp:
            if resp.status != 200:
                return False
            payload = json.loads(resp.read().decode("utf-8"))
            return "ollama_connected" in payload and "model" in payload
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return False


def _is_port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex((host, port)) == 0


def _find_free_port(host: str, preferred_port: int) -> int:
    if not _is_port_in_use(host, preferred_port):
        return preferred_port
    for candidate in range(8100, 8200):
        if not _is_port_in_use(host, candidate):
            return candidate
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, 0))
        return int(s.getsockname()[1])


def ensure_backend_running() -> tuple[str, subprocess.Popen[bytes] | None]:
    """
    Ensure a NyxAI FastAPI backend is running on an available local port.

    Returns:
        Tuple of (resolved_app_url, spawned_popen_or_none).
    """
    if is_backend_ready(APP_URL):
        return APP_URL, None

    target_port = _find_free_port(BACKEND_HOST, BACKEND_PORT)
    target_url = f"http://{BACKEND_HOST}:{target_port}"

    logs_dir = PROJECT_ROOT / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = open(logs_dir / "desktop_backend.log", "ab")

    python_bin = PROJECT_ROOT / ".venv" / "bin" / "python"
    executable = str(python_bin) if python_bin.exists() else sys.executable

    proc = subprocess.Popen(
        [
            executable,
            "-m",
            "uvicorn",
            "api.app.main:app",
            "--host",
            BACKEND_HOST,
            "--port",
            str(target_port),
        ],
        cwd=str(PROJECT_ROOT),
        stdout=log_file,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )

    deadline = time.monotonic() + 25.0
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            break
        if is_backend_ready(target_url, timeout=0.5):
            return target_url, proc
        time.sleep(0.35)

    return target_url, proc


def send_single_instance_command(command: str = "toggle") -> bool:
    """If an existing desktop window is running, send a command to it."""
    sock = QLocalSocket()
    sock.connectToServer(SINGLE_INSTANCE_KEY)
    if not sock.waitForConnected(250):
        return False
    sock.write(command.encode("utf-8"))
    sock.flush()
    sock.waitForBytesWritten(250)
    sock.disconnectFromServer()
    return True


class NyxWebPage(QWebEnginePage):
    """WebEnginePage that grants local microphone/audio access cleanly."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.featurePermissionRequested.connect(self._on_permission_requested)

    def _on_permission_requested(self, security_origin: QUrl, feature: QWebEnginePage.Feature) -> None:
        host = security_origin.host()
        if host in ("127.0.0.1", "localhost", "") and feature in (
            QWebEnginePage.Feature.MediaAudioCapture,
            QWebEnginePage.Feature.MediaAudioVideoCapture,
            QWebEnginePage.Feature.DesktopAudioVideoCapture,
        ):
            self.setFeaturePermission(
                security_origin,
                feature,
                QWebEnginePage.PermissionPolicy.PermissionGrantedByUser,
            )
        else:
            self.setFeaturePermission(
                security_origin,
                feature,
                QWebEnginePage.PermissionPolicy.PermissionDeniedByUser,
            )


class NyxDesktopWindow(QMainWindow):
    """Main standalone desktop companion window + System Tray controller."""

    def __init__(self, app_url: str, spawned_backend: subprocess.Popen[bytes] | None) -> None:
        super().__init__()
        self._app_url = app_url
        self._spawned_backend = spawned_backend
        self._force_quit = False
        self._always_on_top = False

        self.setWindowTitle("NyxAI — AI Companion")
        self.resize(1140, 760)
        self.setMinimumSize(420, 620)
        if ICON_PATH.exists():
            self.setWindowIcon(QIcon(str(ICON_PATH)))

        # WebView setup
        self.web_view = QWebEngineView(self)
        self.web_page = NyxWebPage(self.web_view)
        self.web_view.setPage(self.web_page)
        self.web_page.setBackgroundColor(QColor("#070910"))

        settings = self.web_view.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.WebGLEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.PlaybackRequiresUserGesture, False)
        settings.setAttribute(QWebEngineSettings.WebAttribute.Accelerated2dCanvasEnabled, True)

        self.setCentralWidget(self.web_view)
        self._load_app_or_splash()

        # Single-instance listener
        QLocalServer.removeServer(SINGLE_INSTANCE_KEY)
        self._ipc_server = QLocalServer(self)
        self._ipc_server.listen(SINGLE_INSTANCE_KEY)
        self._ipc_server.newConnection.connect(self._on_ipc_connection)

        # System tray setup
        self._tray: QSystemTrayIcon | None = None
        self._setup_tray()

    def _load_app_or_splash(self) -> None:
        if is_backend_ready(self._app_url):
            self.web_view.setUrl(QUrl(self._app_url))
            return

        splash_html = """
        <!DOCTYPE html>
        <html>
        <body style="margin:0;height:100vh;display:flex;align-items:center;justify-content:center;
                     background:#070910;color:#f8fafc;font-family:sans-serif;flex-direction:column;gap:14px;">
          <div style="width:44px;height:44px;border-radius:50%;border:3px solid #00f2fe;
                      border-top-color:transparent;animation:spin 0.9s linear infinite;"></div>
          <div style="font-size:16px;font-weight:600;">Starting NyxAI Companion...</div>
          <div style="font-size:12px;color:#94a3b8;">Waiting for local AI backend on port 8000</div>
          <style>@keyframes spin{to{transform:rotate(360deg);}}</style>
        </body>
        </html>
        """
        self.web_view.setHtml(splash_html)
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._check_backend_and_load)
        self._poll_timer.start(600)

    def _check_backend_and_load(self) -> None:
        if is_backend_ready(self._app_url):
            self._poll_timer.stop()
            self.web_view.setUrl(QUrl(self._app_url))

    def _setup_tray(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return

        icon = QIcon(str(ICON_PATH)) if ICON_PATH.exists() else self.windowIcon()
        tray = QSystemTrayIcon(icon, self)
        tray.setToolTip("NyxAI — Desktop AI Companion")

        menu = QMenu()
        show_action = QAction("Show / Hide NyxAI", self)
        show_action.triggered.connect(self.toggle_visibility)
        menu.addAction(show_action)

        top_action = QAction("Always on Top", self)
        top_action.setCheckable(True)
        top_action.triggered.connect(self._toggle_always_on_top)
        menu.addAction(top_action)

        reload_action = QAction("Reload Interface", self)
        reload_action.triggered.connect(lambda: self.web_view.setUrl(QUrl(self._app_url)))
        menu.addAction(reload_action)

        menu.addSeparator()
        quit_action = QAction("Quit NyxAI", self)
        quit_action.triggered.connect(self.quit_app)
        menu.addAction(quit_action)

        tray.setContextMenu(menu)
        tray.activated.connect(self._on_tray_activated)
        tray.show()
        self._tray = tray

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.toggle_visibility()

    def _toggle_always_on_top(self, checked: bool) -> None:
        self._always_on_top = checked
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, checked)
        self.show()

    def toggle_visibility(self) -> None:
        if self.isVisible() and not self.isMinimized():
            self.hide()
        else:
            self.showNormal()
            self.raise_()
            self.activateWindow()

    def show_window(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _on_ipc_connection(self) -> None:
        conn = self._ipc_server.nextPendingConnection()
        if not conn:
            return
        conn.waitForReadyRead(200)
        cmd = bytes(conn.readAll()).decode("utf-8", errors="ignore").strip()
        conn.disconnectFromServer()
        if cmd == "show":
            self.show_window()
        else:
            self.toggle_visibility()

    def closeEvent(self, event) -> None:
        if not self._force_quit and self._tray is not None and self._tray.isVisible():
            event.ignore()
            self.hide()
            return
        self._cleanup_backend()
        super().closeEvent(event)

    def quit_app(self) -> None:
        self._force_quit = True
        if self._tray is not None:
            self._tray.hide()
        self._cleanup_backend()
        QApplication.quit()

    def _cleanup_backend(self) -> None:
        if self._spawned_backend is not None and self._spawned_backend.poll() is None:
            try:
                os.killpg(os.getpgid(self._spawned_backend.pid), signal.SIGTERM)
            except Exception:
                self._spawned_backend.terminate()
            self._spawned_backend = None


def main() -> int:
    parser = argparse.ArgumentParser(description="NyxAI Dedicated Desktop App")
    parser.add_argument(
        "--action",
        choices=["show", "toggle"],
        default="show",
        help="Behavior when another instance is already running.",
    )
    parser.add_argument(
        "--no-autostart",
        action="store_true",
        help="Do not auto-start local FastAPI backend if offline.",
    )
    args = parser.parse_args()

    app = QApplication(sys.argv)
    app.setApplicationName("NyxAI")
    app.setDesktopFileName("nyxai")
    app.setQuitOnLastWindowClosed(False)

    # Focus/toggle existing instance if already running
    if send_single_instance_command(args.action):
        return 0

    if args.no_autostart:
        resolved_url, spawned_backend = APP_URL, None
    else:
        resolved_url, spawned_backend = ensure_backend_running()
    window = NyxDesktopWindow(resolved_url, spawned_backend)
    window.show()

    # Clean exit on Ctrl+C in terminal
    signal.signal(signal.SIGINT, lambda *_: window.quit_app())
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
