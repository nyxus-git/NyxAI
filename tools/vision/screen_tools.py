"""
tools/vision/screen_tools.py

Multimodal Desktop Vision and Screen Awareness tools for NyxAI.

Provides:
  - capture_screen: Takes a screenshot of desktop or active window using native Linux capture utilities.
  - read_screen_text: Extracts text from the screen using local high-speed Tesseract OCR.
  - inspect_screen_for_errors: Extracts text and pinpoints visible stack traces, compiler errors, or warnings.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from core.agent.schemas import ToolDefinition, ToolParameter, ToolResult
from core.logging import get_logger

logger = get_logger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
TESSDATA_DIR = PROJECT_ROOT / "data" / "tessdata"


# Tool Definitions for Agent Registry

CAPTURE_SCREEN_DEF = ToolDefinition(
    name="capture_screen",
    description=(
        "Capture a screenshot of the user's desktop or active window. "
        "Use this when the user asks you to 'take a screenshot' or 'capture my screen'."
    ),
    parameters={
        "mode": ToolParameter(
            type="string",
            description="Capture mode: 'fullscreen' for all monitors, or 'active_window' for the focused window.",
            required=False,
        ),
    },
    category="vision",
)

READ_SCREEN_TEXT_DEF = ToolDefinition(
    name="read_screen_text",
    description=(
        "Read and extract all visible text on the user's screen or active window using local OCR. "
        "Use this when the user asks 'what is on my screen', 'read this document', or to inspect what they are viewing."
    ),
    parameters={
        "mode": ToolParameter(
            type="string",
            description="Capture mode: 'fullscreen' or 'active_window'.",
            required=False,
        ),
    },
    category="vision",
)

INSPECT_SCREEN_ERRORS_DEF = ToolDefinition(
    name="inspect_screen_for_errors",
    description=(
        "Inspect the user's screen specifically for terminal tracebacks, compiler errors, exceptions, or build failures. "
        "Use this when the user says 'look at my error', 'why did it fail', or 'debug my screen'."
    ),
    parameters={
        "mode": ToolParameter(
            type="string",
            description="Capture mode: 'fullscreen' or 'active_window'.",
            required=False,
        ),
    },
    category="vision",
)


def _find_screenshot_utility() -> tuple[str, list[str]]:
    """
    Detect the available Linux screenshot capture command.
    Checks KDE Spectacle, Wayland grim, ImageMagick import, and X11 scrot.

    Returns:
        Tuple of (utility_name, base_command_args_template).
    """
    # 1. KDE Plasma (Wayland / X11) - spectacle
    if shutil.which("spectacle"):
        return "spectacle", ["spectacle", "-b", "-n"]

    # 2. Hyprland / Sway / wlroots - grim
    if shutil.which("grim"):
        return "grim", ["grim"]

    # 3. ImageMagick - import
    if shutil.which("import"):
        return "import", ["import", "-window", "root"]

    # 4. Scrot (X11)
    if shutil.which("scrot"):
        return "scrot", ["scrot", "-z"]

    return "", []


def _capture_screen_file(
    mode: str = "fullscreen",
    output_path: str | None = None,
) -> dict[str, Any]:
    """Internal helper to capture screenshot file to disk."""
    utility, base_cmd = _find_screenshot_utility()
    if not utility:
        return {
            "success": False,
            "error": "No screenshot utility found. Install spectacle, grim, or scrot.",
        }

    target_path = output_path or os.path.join(
        tempfile.gettempdir(), f"nyx_screen_{int(time.time() * 1000)}.png"
    )

    try:
        cmd: list[str] = list(base_cmd)
        if utility == "spectacle":
            if mode == "active_window":
                cmd.extend(["-a", "-o", target_path])
            else:
                cmd.extend(["-o", target_path])
        elif utility == "grim":
            cmd.append(target_path)
        elif utility == "import":
            cmd.append(target_path)
        elif utility == "scrot":
            if mode == "active_window":
                cmd.extend(["-u", target_path])
            else:
                cmd.append(target_path)

        subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            timeout=8.0,
        )

        if not os.path.exists(target_path) or os.path.getsize(target_path) == 0:
            return {
                "success": False,
                "error": f"Screenshot utility {utility} completed but produced no output file.",
            }

        size_kb = round(os.path.getsize(target_path) / 1024, 1)
        logger.info(
            "screen_captured_successfully",
            utility=utility,
            mode=mode,
            path=target_path,
            size_kb=size_kb,
        )

        return {
            "success": True,
            "utility": utility,
            "mode": mode,
            "path": target_path,
            "size_kb": size_kb,
            "timestamp": time.time(),
        }

    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"Screenshot utility {utility} timed out after 8s."}
    except Exception as exc:
        logger.error("screen_capture_failed", utility=utility, error=str(exc))
        return {"success": False, "error": f"Failed to capture screen: {exc}"}


def capture_screen(
    mode: str = "fullscreen",
    output_path: str | None = None,
) -> ToolResult:
    """
    Capture a screenshot of the current Linux desktop or active window.

    Args:
        mode: 'fullscreen' to capture all displays, or 'active_window' to capture current window.
        output_path: Optional custom path to save PNG image. If None, saves to a temp file.
    """
    res = _capture_screen_file(mode=mode, output_path=output_path)
    if not res.get("success"):
        return ToolResult(
            tool_name="capture_screen",
            success=False,
            error=res.get("error", "Failed to capture screen"),
        )

    target_path = res["path"]
    size_kb = res["size_kb"]
    display = f"📸 Screenshot captured successfully ({size_kb} KB, mode: {mode}). Saved to: {target_path}"
    return ToolResult(
        tool_name="capture_screen",
        success=True,
        data=res,
        display_text=display,
    )


def _read_screen_text_data(
    mode: str = "fullscreen",
    languages: str = "eng+hin+mar",
) -> dict[str, Any]:
    """Internal helper to OCR screen image and return text metadata."""
    tesseract_bin = shutil.which("tesseract")
    if not tesseract_bin:
        return {
            "success": False,
            "error": "Tesseract binary not installed. Please install tesseract.",
        }

    cap = _capture_screen_file(mode=mode)
    if not cap.get("success"):
        return cap

    img_path = cap["path"]

    try:
        env = os.environ.copy()
        if TESSDATA_DIR.exists():
            env["TESSDATA_PREFIX"] = str(TESSDATA_DIR)

        # First try with requested languages, fall back to eng if model files missing
        lang_arg = languages
        if not (TESSDATA_DIR / "hin.traineddata").exists() and "hin" in languages:
            lang_arg = "eng"

        proc = subprocess.run(
            [tesseract_bin, img_path, "stdout", "-l", lang_arg],
            capture_output=True,
            text=True,
            env=env,
            timeout=25.0,
        )

        raw_text = proc.stdout.strip()
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        cleaned_text = "\n".join(lines)

        logger.info(
            "screen_ocr_complete",
            lines_extracted=len(lines),
            chars=len(cleaned_text),
        )

        return {
            "success": True,
            "mode": mode,
            "text": cleaned_text,
            "line_count": len(lines),
            "character_count": len(cleaned_text),
            "image_path": img_path,
        }

    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Tesseract OCR timed out after 25s."}
    except Exception as exc:
        logger.error("screen_ocr_failed", error=str(exc))
        return {"success": False, "error": f"Failed to extract screen text: {exc}"}


def read_screen_text(
    mode: str = "fullscreen",
    languages: str = "eng+hin+mar",
) -> ToolResult:
    """
    Take a screenshot and extract all visible text using local Tesseract OCR.
    """
    res = _read_screen_text_data(mode=mode, languages=languages)
    if not res.get("success"):
        return ToolResult(
            tool_name="read_screen_text",
            success=False,
            error=res.get("error", "Failed to extract screen text"),
        )

    text = res.get("text", "")
    line_count = res.get("line_count", 0)
    char_count = res.get("character_count", 0)

    if not text:
        display = "Screen captured, but no visible text was detected."
    else:
        preview = text[:1500]
        if len(text) > 1500:
            preview += f"\n... [Truncated {len(text) - 1500} characters]"
        display = f"🖥️ Screen Text Extracted ({line_count} lines, {char_count} chars):\n\n{preview}"

    return ToolResult(
        tool_name="read_screen_text",
        success=True,
        data=res,
        display_text=display,
    )


def inspect_screen_for_errors(mode: str = "fullscreen") -> ToolResult:
    """
    Inspect the screen specifically for terminal tracebacks, compiler errors, or warnings.
    """
    res = _read_screen_text_data(mode=mode)
    if not res.get("success"):
        return ToolResult(
            tool_name="inspect_screen_for_errors",
            success=False,
            error=res.get("error", "Failed to inspect screen"),
        )

    text = res.get("text", "")
    lines = text.splitlines()

    error_lines: list[str] = []
    error_keywords = (
        "error",
        "exception",
        "traceback",
        "failed",
        "syntaxerror",
        "typeerror",
        "valueerror",
        "modulenotfounderror",
        "fatal",
        "panic",
        "segmentation fault",
        "warning",
    )

    for idx, line in enumerate(lines):
        line_lower = line.lower()
        if any(kw in line_lower for kw in error_keywords):
            # Capture context (1 line before, matching line, 2 lines after)
            start = max(0, idx - 1)
            end = min(len(lines), idx + 3)
            context = "\n".join(lines[start:end])
            if context not in error_lines:
                error_lines.append(context)

    has_errors = len(error_lines) > 0
    data = {
        "success": True,
        "has_errors": has_errors,
        "error_count": len(error_lines),
        "detected_issues": error_lines[:5],  # Cap to top 5 issues
        "full_text": text[:3000],  # Truncate to safe context size
        "image_path": res.get("image_path"),
    }

    if not has_errors:
        display = "✅ No obvious stack traces or compiler errors detected on screen."
    else:
        issues_summary = "\n---\n".join(error_lines[:5])
        display = f"⚠️ Found {len(error_lines)} potential issue(s) on screen:\n\n{issues_summary}"

    return ToolResult(
        tool_name="inspect_screen_for_errors",
        success=True,
        data=data,
        display_text=display,
    )
