"""
safety/command_validator.py

Validates tool arguments before execution.

This module is the last line of defense before any tool is called.
It checks arguments for injection attacks, dangerous patterns, and
ensures values stay within safe bounds.

Security model:
  - All string arguments are checked for shell injection characters
  - Application names and URLs are validated against patterns
  - Arguments are length-bounded to prevent abuse
  - Returns a structured ValidationResult so callers get clear error messages
"""

import re
from dataclasses import dataclass


# ─── Result Type ──────────────────────────────────────────────────────────────


@dataclass
class ValidationResult:
    """
    Result of a tool argument validation check.

    Attributes:
        ok: True if validation passed. False if the tool should NOT execute.
        reason: Human-readable explanation if ok=False. Empty string if ok=True.
    """

    ok: bool
    reason: str = ""

    @classmethod
    def passed(cls) -> "ValidationResult":
        """Return a passing validation result."""
        return cls(ok=True, reason="")

    @classmethod
    def failed(cls, reason: str) -> "ValidationResult":
        """Return a failing validation result with an explanation."""
        return cls(ok=False, reason=reason)


# ─── Shell Injection Blocklist ────────────────────────────────────────────────
# These characters/patterns are dangerous in shell contexts.
# If any argument contains these, reject the tool call.

_SHELL_INJECTION_PATTERN = re.compile(
    r"[;&|`$<>\\]|"            # Shell metacharacters
    r"\.\./|"                  # Directory traversal
    r"\b(rm|dd|mkfs|fdisk|"    # Dangerous commands (word boundary required)
    r"chmod|chown|sudo|su|"
    r"wget|curl|nc|netcat)\s", # Network/download tools — only match standalone commands
    re.IGNORECASE,
)

# ─── URL Validation ───────────────────────────────────────────────────────────
_URL_PATTERN = re.compile(
    r"^https?://"              # Must start with http:// or https://
    r"[a-zA-Z0-9\-._~:/?#\[\]@!$&'()*+,;=%]+"  # Valid URL characters
    r"$"
)

# ─── Application Name Allowlist ───────────────────────────────────────────────
# Only allow known, safe application names. This prevents "rm -rf /" being
# passed as an application name to xdg-open or similar.
_ALLOWED_APPLICATIONS: set[str] = {
    # Browsers
    "firefox", "chromium", "google-chrome", "brave", "opera",
    # Development
    "code", "codium", "vscodium", "nvim", "vim", "nano",
    "kitty", "alacritty", "wezterm", "ghostty", "foot",
    "gitk", "gitkraken",
    # Office & Productivity
    "libreoffice", "writer", "calc", "impress",
    "obsidian", "notion", "logseq",
    # Media
    "vlc", "mpv", "celluloid", "totem",
    "rhythmbox", "audacity", "spotify",
    "gimp", "inkscape", "krita",
    # File Managers
    "nautilus", "thunar", "dolphin", "nemo", "ranger",
    # Communication
    "discord", "telegram-desktop", "signal-desktop", "slack",
    # System
    "gnome-system-monitor", "htop", "btop", "bashtop",
    "pavucontrol", "blueman-manager",
}

# Max lengths
_MAX_STRING_ARG_LENGTH = 512
_MAX_QUERY_LENGTH = 256
_MAX_URL_LENGTH = 2048


# ─── Main Validator ───────────────────────────────────────────────────────────


class CommandValidator:
    """
    Validates tool arguments before the tool is executed.

    Usage:
        validator = CommandValidator()
        result = validator.validate_tool_args("open_application", {"application": "firefox"})
        if not result.ok:
            raise SafetyError(result.reason)
    """

    def validate_tool_args(
        self,
        tool_name: str,
        arguments: dict,
    ) -> ValidationResult:
        """
        Validate all arguments for a given tool call.

        Args:
            tool_name: The name of the tool being called.
            arguments: Dict of argument name → value from the LLM.

        Returns:
            ValidationResult with ok=True if safe, ok=False with reason if not.
        """
        # First: check all string args for injection
        for arg_name, arg_value in arguments.items():
            if isinstance(arg_value, str):
                result = self._check_string_arg(arg_name, arg_value)
                if not result.ok:
                    return result

        # Then: apply tool-specific validation
        if tool_name == "open_application":
            return self._validate_open_application(arguments)

        if tool_name in ("open_url",):
            return self._validate_url(arguments)

        if tool_name == "web_search":
            return self._validate_search_query(arguments)

        # For safe read-only tools (system info), no extra checks needed
        return ValidationResult.passed()

    def _check_string_arg(self, arg_name: str, value: str) -> ValidationResult:
        """Check a string argument for injection patterns and length limits."""
        if len(value) > _MAX_STRING_ARG_LENGTH:
            return ValidationResult.failed(
                f"Argument '{arg_name}' is too long "
                f"({len(value)} chars, max {_MAX_STRING_ARG_LENGTH})"
            )

        if _SHELL_INJECTION_PATTERN.search(value):
            return ValidationResult.failed(
                f"Argument '{arg_name}' contains unsafe characters. "
                f"Rejected for security reasons."
            )

        return ValidationResult.passed()

    def _validate_open_application(self, arguments: dict) -> ValidationResult:
        """Validate that the application name is in the safe allowlist."""
        app_name = arguments.get("application", "").strip().lower()

        if not app_name:
            return ValidationResult.failed("Application name cannot be empty.")

        # Check exact match or prefix match (e.g. "code" matches "code --new-window")
        base_name = app_name.split()[0] if " " in app_name else app_name
        if base_name not in _ALLOWED_APPLICATIONS:
            return ValidationResult.failed(
                f"Application '{app_name}' is not in the allowed list. "
                f"Add it to safety/command_validator.py if it's safe."
            )

        return ValidationResult.passed()

    def _validate_url(self, arguments: dict) -> ValidationResult:
        """Validate that a URL is safe to open."""
        url = arguments.get("url", "").strip()

        if not url:
            return ValidationResult.failed("URL cannot be empty.")

        if len(url) > _MAX_URL_LENGTH:
            return ValidationResult.failed(
                f"URL is too long ({len(url)} chars, max {_MAX_URL_LENGTH})."
            )

        if not _URL_PATTERN.match(url):
            return ValidationResult.failed(
                f"URL '{url[:50]}...' is not a valid http/https URL."
            )

        return ValidationResult.passed()

    def _validate_search_query(self, arguments: dict) -> ValidationResult:
        """Validate a web search query."""
        query = arguments.get("query", "").strip()

        if not query:
            return ValidationResult.failed("Search query cannot be empty.")

        if len(query) > _MAX_QUERY_LENGTH:
            return ValidationResult.failed(
                f"Search query is too long ({len(query)} chars, max {_MAX_QUERY_LENGTH})."
            )

        return ValidationResult.passed()
