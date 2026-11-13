"""
tests/test_browser_research.py

Unit tests for Deep Web Research and Webpage Summarization capabilities
added in Phase 7, including ResearchAgent supervisor orchestration,
semantic routing cues, and safety policy classification.
"""

from unittest.mock import AsyncMock, MagicMock, patch
import httpx
import pytest

from core.agent.router import DomainClassifier
from core.agent.schemas import ToolResult
from core.agent.supervisor import NyxSupervisor
from core.agent.tool_registry import build_default_registry
from safety.policy import TOOL_POLICY, PermissionLevel
from tools.browser.browser_tools import deep_search, summarize_webpage


class TestBrowserResearchTools:
    """Tests for deep_search and summarize_webpage tools."""

    @pytest.mark.asyncio
    async def test_deep_search_success(self) -> None:
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "Heading": "Quantum Computing",
            "AbstractText": "Quantum computing is a rapidly-emerging technology that harnesses quantum mechanics.",
            "AbstractURL": "https://en.wikipedia.org/wiki/Quantum_computing",
            "RelatedTopics": [],
        }

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            result = await deep_search("quantum computing")

            assert result.success is True
            assert result.data["heading"] == "Quantum Computing"
            assert "quantum mechanics" in result.data["abstract"]
            assert "https://en.wikipedia.org/wiki/Quantum_computing" in result.data["source_url"]
            assert "Quantum Computing" in result.display_text

    @pytest.mark.asyncio
    async def test_deep_search_related_fallback(self) -> None:
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "Heading": "Arch Linux",
            "AbstractText": "",
            "AbstractURL": "",
            "RelatedTopics": [
                {
                    "Text": "Arch Linux is an independently developed x86-64 Linux distribution.",
                    "FirstURL": "https://en.wikipedia.org/wiki/Arch_Linux",
                }
            ],
        }

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            result = await deep_search("arch linux")

            assert result.success is True
            assert "Arch Linux is an independently developed" in result.data["abstract"]
            assert result.data["source_url"] == "https://en.wikipedia.org/wiki/Arch_Linux"

    @pytest.mark.asyncio
    async def test_deep_search_empty_query(self) -> None:
        result = await deep_search("   ")
        assert result.success is False
        assert "empty" in result.error.lower()

    @pytest.mark.asyncio
    async def test_deep_search_error_status(self) -> None:
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 503

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            result = await deep_search("sample query")

            assert result.success is False
            assert "503" in result.error

    @pytest.mark.asyncio
    async def test_deep_search_network_exception(self) -> None:
        with patch("httpx.AsyncClient.get", side_effect=httpx.ConnectError("Connection refused")):
            result = await deep_search("quantum computing")
            assert result.success is False
            assert "Connection refused" in result.error

    @pytest.mark.asyncio
    async def test_summarize_webpage_success(self) -> None:
        html_content = """
        <!DOCTYPE html>
        <html>
        <head><title>Kernel News 6.12 Released</title></head>
        <body>
            <nav><a href="/">Home</a></nav>
            <p>The Linux 6.12 kernel has officially been released with major real-time PREEMPT_RT patches merged.</p>
            <p>This long-term support release brings extensive hardware support and improved scheduler efficiency.</p>
            <footer>Copyright 2026</footer>
        </body>
        </html>
        """
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.text = html_content
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            result = await summarize_webpage("https://kernel.org/news/6.12")

            assert result.success is True
            assert result.data["title"] == "Kernel News 6.12 Released"
            assert result.data["paragraphs_count"] == 2
            assert "PREEMPT_RT" in result.display_text
            assert "Home" not in result.display_text  # Nav excluded

    @pytest.mark.asyncio
    async def test_summarize_webpage_invalid_url(self) -> None:
        result = await summarize_webpage("ftp://not-a-valid-web-url.com")
        assert result.success is False
        assert "http" in result.error.lower()

    @pytest.mark.asyncio
    async def test_summarize_webpage_network_exception(self) -> None:
        with patch("httpx.AsyncClient.get", side_effect=httpx.ConnectTimeout("Request timed out")):
            result = await summarize_webpage("https://kernel.org")
            assert result.success is False
            assert "timed out" in result.error.lower()


class TestResearchAgentOrchestration:
    """Tests for ResearchAgent registration, routing, and safety permissions."""

    def test_tools_registered_in_default_registry(self) -> None:
        registry = build_default_registry()
        assert registry.has_tool("deep_search")
        assert registry.has_tool("summarize_webpage")
        # Check aliases
        assert registry.has_tool("lookup")
        assert registry.has_tool("search_knowledge")
        assert registry.has_tool("summarize_page")
        assert registry.has_tool("summarize_url")

    def test_research_safety_policy(self) -> None:
        assert TOOL_POLICY.get("deep_search") == PermissionLevel.SAFE
        assert TOOL_POLICY.get("summarize_webpage") == PermissionLevel.SAFE

    def test_research_semantic_routing(self) -> None:
        classifier = DomainClassifier()
        assert "browser" in classifier.classify("deep search how quantum mechanics works")
        assert "browser" in classifier.classify("research latest news on Linux kernel")
        assert "browser" in classifier.classify("summarize webpage https://kernel.org")

    def test_supervisor_has_research_agent(self) -> None:
        registry = build_default_registry()
        mock_llm = MagicMock()
        supervisor = NyxSupervisor(llm_provider=mock_llm, tool_registry=registry)
        assert hasattr(supervisor, "research_agent")
        assert supervisor.research_agent.name == "ResearchAgent"
        assert supervisor.research_agent.domain == "browser"
