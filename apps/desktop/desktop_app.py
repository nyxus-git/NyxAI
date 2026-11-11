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
import tempfile
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
from PyQt6.QtNetwork import QLocalServer
from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineSettings
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
SOCKET_PATH = Path(tempfile.gettempdir()) / SINGLE_INSTANCE_KEY
PID_FILE = Path(tempfile.gettempdir()) / f"{SINGLE_INSTANCE_KEY}.pid"
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


def _is_desktop_app_pid(pid: int) -> bool:
    """Return True if *pid* is another live process running apps/desktop/desktop_app.py."""
    if pid <= 0 or pid in (os.getpid(), os.getppid()):
        return False
    cmdline_path = Path(f"/proc/{pid}/cmdline")
    try:
        raw = cmdline_path.read_bytes()
    except OSError:
        return False
    args = [part for part in raw.decode("utf-8", errors="ignore").split("\0") if part]
    if len(args) < 2:
        return False
    exe_name = Path(args[0]).name
    if not exe_name.startswith("python"):
        return False
    target_script = str(Path(__file__).resolve())
    return any(
        not arg.startswith("-")
        and (arg == target_script or Path(arg).name == "desktop_app.py")
        for arg in args[1:]
    )


def _find_desktop_app_pids() -> list[int]:
    """Find PIDs of other running or suspended desktop_app.py instances."""
    pids: list[int] = []
    seen: set[int] = set()

    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text(encoding="utf-8").strip())
            if _is_desktop_app_pid(pid):
                pids.append(pid)
                seen.add(pid)
        except (OSError, ValueError):
            pass

    proc_dir = Path("/proc")
    if proc_dir.is_dir():
        for entry in proc_dir.iterdir():
            if not entry.name.isdigit():
                continue
            pid = int(entry.name)
            if pid not in seen and _is_desktop_app_pid(pid):
                pids.append(pid)
                seen.add(pid)

    return pids


def _cleanup_unresponsive_instance() -> None:
    """Terminate frozen/unresponsive desktop_app.py processes and remove stale IPC files."""
    for pid in _find_desktop_app_pids():
        print(
            f"[NyxAI] Stopping unresponsive or suspended desktop instance (PID {pid})...",
            file=sys.stderr,
        )
        try:
            # SIGCONT wakes Ctrl+Z-suspended instances so SIGTERM can complete.
            os.kill(pid, signal.SIGCONT)
            os.kill(pid, signal.SIGTERM)
        except OSError:
            continue

        deadline = time.monotonic() + 0.8
        while time.monotonic() < deadline:
            try:
                os.kill(pid, 0)
            except OSError:
                break
            time.sleep(0.05)
        else:
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass

    try:
        SOCKET_PATH.unlink(missing_ok=True)
    except OSError:
        pass
    try:
        PID_FILE.unlink(missing_ok=True)
    except OSError:
        pass


def send_single_instance_command(
    command: str = "toggle",
    *,
    timeout_s: float = 0.8,
    recover_unresponsive: bool = True,
) -> bool:
    """If a responsive desktop window is running, send *command* and await an ACK."""
    if not SOCKET_PATH.exists():
        return False

    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(timeout_s)
    try:
        sock.connect(str(SOCKET_PATH))
        sock.sendall(f"{command}\n".encode("utf-8"))
        reply = b""
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline and b"ok" not in reply:
            try:
                chunk = sock.recv(64)
            except TimeoutError:
                break
            if not chunk:
                break
            reply += chunk
        if b"ok" in reply:
            return True
    except (TimeoutError, OSError):
        pass
    finally:
        sock.close()

    if recover_unresponsive:
        _cleanup_unresponsive_instance()
    return False


class NyxWebPage(QWebEnginePage):
    """WebEnginePage that grants local microphone/audio access and logs JS errors."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.featurePermissionRequested.connect(self._on_permission_requested)

    def javaScriptConsoleMessage(self, level, message, lineNumber, sourceID) -> None:
        try:
            logs_dir = PROJECT_ROOT / "logs"
            logs_dir.mkdir(parents=True, exist_ok=True)
            with open(logs_dir / "desktop_app.log", "a", encoding="utf-8") as f:
                f.write(f"[{level}] {sourceID}:{lineNumber} {message}\n")
        except Exception:
            pass

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
        if self._ipc_server.listen(SINGLE_INSTANCE_KEY):
            try:
                PID_FILE.write_text(str(os.getpid()), encoding="utf-8")
            except OSError:
                pass
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
        reload_action.triggered.connect(self.hard_reload)
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
            self.show_window()

    def show_window(self) -> None:
        if self.isMinimized():
            self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized)
            self.hide()
        if not self.isVisible():
            self.show()
        self.raise_()
        self.activateWindow()
        QApplication.alert(self, 0)

    def hard_reload(self) -> None:
        profile = QWebEngineProfile.defaultProfile()
        if profile is not None:
            profile.clearHttpCache()
        self.web_view.setUrl(QUrl(self._app_url))

    def _on_ipc_connection(self) -> None:
        while self._ipc_server.hasPendingConnections():
            conn = self._ipc_server.nextPendingConnection()
            if not conn:
                continue
            if not conn.bytesAvailable():
                conn.waitForReadyRead(200)
            cmd = bytes(conn.readAll()).decode("utf-8", errors="ignore").strip()
            if cmd == "show":
                self.show_window()
            elif cmd == "reload":
                self.hard_reload()
                self.show_window()
            elif cmd == "ping":
                pass
            else:
                self.toggle_visibility()
            conn.write(b"ok\n")
            conn.flush()
            conn.waitForBytesWritten(250)
            conn.disconnectFromServer()

    def closeEvent(self, event) -> None:
        if not self._force_quit and self._tray is not None and self._tray.isVisible():
            event.ignore()
            self.hide()
            return
        self._cleanup_ipc()
        self._cleanup_backend()
        super().closeEvent(event)

    def quit_app(self) -> None:
        self._force_quit = True
        if self._tray is not None:
            self._tray.hide()
        self._cleanup_ipc()
        self._cleanup_backend()
        QApplication.quit()

    def _cleanup_ipc(self) -> None:
        try:
            self._ipc_server.close()
        except Exception:
            pass
        try:
            PID_FILE.unlink(missing_ok=True)
        except OSError:
            pass

    def _cleanup_backend(self) -> None:
        if self._spawned_backend is not None and self._spawned_backend.poll() is None:
            try:
                os.killpg(os.getpgid(self._spawned_backend.pid), signal.SIGTERM)
            except Exception:
                self._spawned_backend.terminate()
            self._spawned_backend = None


def _launch_detached(args: argparse.Namespace) -> int:
    """Spawn desktop_app.py in a detached session and wait until IPC responds."""
    logs_dir = PROJECT_ROOT / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / "desktop_app_process.log"

    cmd = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--action",
        args.action,
    ]
    if args.no_autostart:
        cmd.append("--no-autostart")

    with open(log_path, "ab+") as log_f:
        start_offset = log_f.tell()
        proc = subprocess.Popen(
            cmd,
            cwd=str(PROJECT_ROOT),
            stdin=subprocess.DEVNULL,
            stdout=log_f,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )

    deadline = time.monotonic() + 30.0
    while time.monotonic() < deadline:
        if send_single_instance_command("ping", timeout_s=0.3, recover_unresponsive=False):
            print(f"NyxAI Desktop App started (PID {proc.pid}).")
            return 0
        ret = proc.poll()
        if ret is not None:
            try:
                with open(log_path, "rb") as log_f:
                    log_f.seek(start_offset)
                    output = log_f.read().decode("utf-8", errors="replace").strip()
            except OSError:
                output = ""
            print(
                f"[NyxAI] Desktop App exited unexpectedly (code {ret}).",
                file=sys.stderr,
            )
            if output:
                print(output[-2000:], file=sys.stderr)
            return ret if ret != 0 else 1
        time.sleep(0.2)

    print(
        f"NyxAI Desktop App launched (PID {proc.pid}); still initializing. Check {log_path} if needed."
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="NyxAI Dedicated Desktop App")
    parser.add_argument(
        "--action",
        choices=["show", "toggle", "reload"],
        default="show",
        help="Behavior when another instance is already running.",
    )
    parser.add_argument(
        "--no-autostart",
        action="store_true",
        help="Do not auto-start local FastAPI backend if offline.",
    )
    parser.add_argument(
        "--detach",
        action="store_true",
        help="Launch desktop window in background and return once ready.",
    )
    args = parser.parse_args()

    # Focus/toggle existing responsive instance (or clean up a frozen/stale one)
    if send_single_instance_command(args.action):
        if args.detach:
            print("NyxAI Desktop App is already running (window focused).")
        return 0

    if args.detach:
        return _launch_detached(args)

    app = QApplication(sys.argv)
    app.setApplicationName("NyxAI")
    app.setDesktopFileName("nyxai")
    app.setQuitOnLastWindowClosed(False)

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
