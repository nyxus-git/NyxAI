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
import httpx
from bs4 import BeautifulSoup

from core.agent.schemas import ToolDefinition, ToolParameter, ToolResult
from core.logging import get_logger

logger = get_logger(__name__)


# Tool Definitions

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

READ_WEBPAGE_DEF = ToolDefinition(
    name="read_webpage",
    description=(
        "Fetch and extract readable text from a URL. "
        "Use this tool when you need to read the contents of a specific website or article to answer a question."
    ),
    parameters={
        "url": ToolParameter(
            type="string",
            description="The URL of the webpage to read (must start with http:// or https://).",
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


# Tool Implementations

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


def read_webpage(url: str) -> ToolResult:
    """
    Fetch a URL and extract text content using BeautifulSoup.
    
    Args:
        url: The webpage URL.
        
    Returns:
        ToolResult with the extracted text (truncated to avoid massive context usage).
    """
    logger.info("tool_read_webpage", url=url[:80])
    try:
        # Use a normal user-agent to avoid basic anti-bot blocking
        headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) NyxAI/1.0"}
        response = httpx.get(url, headers=headers, timeout=10.0, follow_redirects=True)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        
        # Remove script and style elements
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.extract()

        text = soup.get_text(separator=" ", strip=True)
        
        # Truncate text to ~8000 characters to prevent blowing up the LLM context window
        max_chars = 8000
        truncated = False
        if len(text) > max_chars:
            text = text[:max_chars] + "... [Content truncated]"
            truncated = True
            
        data = {"url": url, "text_length": len(text), "truncated": truncated}
        display = f"Read {len(text)} characters from {url}."
        
        return ToolResult(
            tool_name="read_webpage",
            success=True,
            data=data,
            display_text=text,
        )
        
    except Exception as e:
        logger.error("tool_read_webpage_failed", url=url[:80], error=str(e))
        return ToolResult(
            tool_name="read_webpage",
            success=False,
            error=f"Failed to read webpage: {str(e)}",
        )
