"""
tools/browser/browser_tools.py

Browser and web tools for NyxAI.

These tools open external URLs or search results and require
PermissionLevel.CONFIRMATION before execution.

Tools:
  - open_url: Open a specific URL in the default browser
  - web_search: Open a DuckDuckGo search for a query in the default browser
"""

import urllib.parse
import webbrowser

from core.agent.schemas import ToolDefinition, ToolParameter, ToolResult
from core.logging import get_logger

logger = get_logger(__name__)


# ─── Tool Definitions ─────────────────────────────────────────────────────────

OPEN_URL_DEF = ToolDefinition(
    name="open_url",
    description=(
        "Open a specific URL in the user's default web browser. "
        "Use this when the user provides a specific website address or link. "
        "The URL must start with http:// or https://."
    ),
    parameters={
        "url": ToolParameter(
            type="string",
            description=(
                "The full URL to open, including the protocol. "
                "Example: 'https://github.com' or 'https://youtube.com'."
            ),
            required=True,
        ),
    },
    category="browser",
)

WEB_SEARCH_DEF = ToolDefinition(
    name="web_search",
    description=(
        "Search the web for a query using DuckDuckGo and open the results in the browser. "
        "Use this when the user asks to search for something online, "
        "find information, or look something up on the internet."
    ),
    parameters={
        "query": ToolParameter(
            type="string",
            description=(
                "The search query to look up. "
                "Example: 'FastAPI tutorial', 'Python async programming', "
                "'best Linux music player'."
            ),
            required=True,
        ),
    },
    category="browser",
)


# ─── Tool Implementations ─────────────────────────────────────────────────────

# DuckDuckGo is used as the default search engine for privacy reasons.
_SEARCH_BASE_URL = "https://duckduckgo.com/?q={query}"


def open_url(url: str) -> ToolResult:
    """
    Open a URL in the system's default web browser.

    Uses Python's webbrowser module which respects the user's default browser
    and works across desktop environments (GNOME, KDE, Hyprland, etc).

    Args:
        url: A valid http/https URL.

    Returns:
        ToolResult indicating whether the browser was opened.
    """
    logger.info("tool_open_url", url=url[:80])

    try:
        opened = webbrowser.open(url, new=2)  # new=2 opens in new tab if possible

        if not opened:
            return ToolResult(
                tool_name="open_url",
                success=False,
                error=f"webbrowser.open() returned False for URL: {url[:80]}",
            )

        data = {"url": url, "opened": True}
        display = f"Opened '{url}' in the default browser."

        logger.info("tool_url_opened", url=url[:80])

        return ToolResult(
            tool_name="open_url",
            success=True,
            data=data,
            display_text=display,
        )

    except Exception as e:
        logger.error("tool_url_open_failed", url=url[:80], error=str(e))
        return ToolResult(
            tool_name="open_url",
            success=False,
            error=f"Failed to open URL: {str(e)}",
        )


def web_search(query: str) -> ToolResult:
    """
    Open a DuckDuckGo web search in the default browser.

    Args:
        query: The search query string.

    Returns:
        ToolResult indicating whether the search was opened.
    """
    logger.info("tool_web_search", query=query[:80])

    # URL-encode the query so spaces and special chars are handled safely
    encoded_query = urllib.parse.quote_plus(query)
    search_url = _SEARCH_BASE_URL.format(query=encoded_query)

    try:
        opened = webbrowser.open(search_url, new=2)

        if not opened:
            return ToolResult(
                tool_name="web_search",
                success=False,
                error="Failed to open browser for search.",
            )

        data = {
            "query": query,
            "search_url": search_url,
            "opened": True,
        }
        display = f"Opened DuckDuckGo search for '{query}' in the browser."

        logger.info("tool_search_opened", query=query[:80])

        return ToolResult(
            tool_name="web_search",
            success=True,
            data=data,
            display_text=display,
        )

    except Exception as e:
        logger.error("tool_search_failed", query=query[:80], error=str(e))
        return ToolResult(
            tool_name="web_search",
            success=False,
            error=f"Failed to open search: {str(e)}",
        )
