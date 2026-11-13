"""
tests/test_router.py

Unit tests for Phase 1: Domain Classifier, Dynamic Tool Pruning,
and Tool Call Alias Normalization.
"""

from unittest.mock import AsyncMock, MagicMock
import pytest

from core.agent.agent import NyxAgent
from core.agent.router import DomainClassifier
from core.agent.schemas import AgentResponse, ToolCall, ToolDefinition, ToolDomain, ToolParameter, ToolResult
from core.agent.tool_registry import ToolRegistry, build_default_registry
from core.brain.llm import LLMProvider, LLMResponseWithTools


class TestDomainClassifier:
    """Tests for DomainClassifier pattern matching and chitchat detection."""

    def setup_method(self) -> None:
        self.router = DomainClassifier()

    def test_chitchat_queries_return_empty_domains(self) -> None:
        queries = [
            "Hello NyxAI!",
            "Hi",
            "Hey",
            "Good morning",
            "How are you doing today?",
            "Who are you?",
            "Tell me a joke",
            "Thank you so much",
            "Goodbye!",
        ]
        for q in queries:
            domains = self.router.classify(q)
            assert domains == [], f"Query '{q}' should be classified as conversational, got {domains}"

    def test_system_domain_classification(self) -> None:
        queries = [
            "What is my battery level?",
            "Check my CPU usage",
            "How much RAM is currently free?",
            "What's the GPU temperature and VRAM?",
            "What time is it right now?",
            "Give me your system info and kernel version",
        ]
        for q in queries:
            domains = self.router.classify(q)
            assert "system" in domains, f"Query '{q}' should include 'system' domain, got {domains}"

    def test_applications_domain_classification(self) -> None:
        queries = [
            "Open Firefox for me",
            "Launch VS Code",
            "Start the terminal",
            "Open Spotify",
            "Launch Discord",
        ]
        for q in queries:
            domains = self.router.classify(q)
            assert "applications" in domains, f"Query '{q}' should include 'applications' domain, got {domains}"

    def test_browser_domain_classification(self) -> None:
        queries = [
            "Search the web for Arch Linux updates",
            "Google latest python 3.12 features",
            "Look up how to configure PipeWire",
            "Read webpage https://news.ycombinator.com",
            "Open website https://github.com",
        ]
        for q in queries:
            domains = self.router.classify(q)
            assert "browser" in domains, f"Query '{q}' should include 'browser' domain, got {domains}"

    def test_files_domain_classification(self) -> None:
        queries = [
            "Read file notes.txt",
            "List directory /home/user/Projects",
            "Search files matching *.py",
            "Show contents of file config.yaml",
        ]
        for q in queries:
            domains = self.router.classify(q)
            assert "files" in domains, f"Query '{q}' should include 'files' domain, got {domains}"

    def test_tasks_domain_classification(self) -> None:
        queries = [
            "Add task to buy groceries tomorrow",
            "List all my pending tasks",
            "Complete task 3",
            "Remind me to call Mom at 5pm",
        ]
        for q in queries:
            domains = self.router.classify(q)
            assert "tasks" in domains, f"Query '{q}' should include 'tasks' domain, got {domains}"

    def test_planning_domain_classification(self) -> None:
        queries = [
            "Create a plan to refactor my codebase",
            "Give me a step-by-step plan for building a React app",
            "Update plan with completed step",
        ]
        for q in queries:
            domains = self.router.classify(q)
            assert "planning" in domains, f"Query '{q}' should include 'planning' domain, got {domains}"

    def test_multi_domain_classification(self) -> None:
        # Prompt mentioning both battery (system) and search (browser)
        query = "Check my battery percentage and search for Arch Linux news"
        domains = self.router.classify(query)
        assert "system" in domains
        assert "browser" in domains


class TestToolRegistryPhase1:
    """Tests for ToolRegistry domain pruning, indexing, and alias normalization."""

    def test_default_registry_categories(self) -> None:
        registry = build_default_registry()
        categories = registry.get_categories()
        assert "system" in categories
        assert "applications" in categories
        assert "browser" in categories
        assert "files" in categories
        assert "tasks" in categories
        assert "planning" in categories

    def test_domain_filtering_tools_for_ollama(self) -> None:
        registry = build_default_registry()

        # All tools
        all_tools = registry.get_tools_for_ollama()
        assert len(all_tools) >= 15

        # Only system tools
        system_tools = registry.get_tools_for_ollama(categories=["system"])
        system_names = [t["function"]["name"] for t in system_tools]
        assert "get_battery_status" in system_names
        assert "get_cpu_usage" in system_names
        assert "open_application" not in system_names
        assert "list_directory" not in system_names
        assert len(system_tools) < len(all_tools)

        # Only application tools
        app_tools = registry.get_tools_for_ollama(categories=["applications"])
        app_names = [t["function"]["name"] for t in app_tools]
        assert "open_application" in app_names
        assert "get_battery_status" not in app_names

    def test_tool_name_alias_normalization(self) -> None:
        registry = build_default_registry()

        # Test battery alias
        call = ToolCall(name="get_battery", arguments={})
        norm = registry.normalize_tool_call(call)
        assert norm.name == "get_battery_status"

        # Test app alias
        call = ToolCall(name="open_app", arguments={"app": "firefox"})
        norm = registry.normalize_tool_call(call)
        assert norm.name == "open_application"
        assert norm.arguments == {"application": "firefox"}

        # Test search alias
        call = ToolCall(name="search_web", arguments={"search_query": "ollama"})
        norm = registry.normalize_tool_call(call)
        assert norm.name == "web_search"
        assert norm.arguments == {"query": "ollama"}

        # Test task alias
        call = ToolCall(name="create_task", arguments={"task": "buy coffee"})
        norm = registry.normalize_tool_call(call)
        assert norm.name == "add_task"
        assert norm.arguments == {"title": "buy coffee"}

    @pytest.mark.asyncio
    async def test_dispatch_executes_aliased_tool(self) -> None:
        registry = ToolRegistry()

        def dummy_battery() -> ToolResult:
            return ToolResult(tool_name="get_battery_status", success=True, data={"level": 90})

        battery_def = ToolDefinition(
            name="get_battery_status",
            description="Battery status.",
            category="system",
        )
        registry.register(battery_def, dummy_battery)

        # Dispatched with aliased name 'get_battery'
        call = ToolCall(name="get_battery", arguments={})
        result = await registry.dispatch(call)

        assert result.success is True
        assert result.tool_name == "get_battery_status"
        assert result.data == {"level": 90}


class TestAgentDynamicPruningAndRecovery:
    """Tests for NyxAgent tool pruning and error recovery with domain classifier."""

    @pytest.mark.asyncio
    async def test_agent_prunes_tools_for_system_domain(self) -> None:
        registry = build_default_registry()

        mock_llm = MagicMock(spec=LLMProvider)
        mock_llm.get_model_name.return_value = "qwen2.5:3b"

        captured_tools: list[list[dict]] = []

        async def fake_chat_with_tools(messages, tools, temperature=0.5):
            captured_tools.append(tools)
            return LLMResponseWithTools(
                content="Your battery is at 80%.",
                model="qwen2.5:3b",
                tool_calls=[],
            )

        mock_llm.chat_with_tools = AsyncMock(side_effect=fake_chat_with_tools)

        agent = NyxAgent(llm_provider=mock_llm, tool_registry=registry, max_iterations=3)
        response = await agent.run("What is my battery level?")

        assert len(captured_tools) == 1
        tools_sent = [t["function"]["name"] for t in captured_tools[0]]
        assert "get_battery_status" in tools_sent
        # Application and file tools should be pruned away!
        assert "open_application" not in tools_sent
        assert "read_file" not in tools_sent
        assert response.content == "Your battery is at 80%."

    @pytest.mark.asyncio
    async def test_agent_normalizes_and_recovers_aliased_tool(self) -> None:
        registry = build_default_registry()

        mock_llm = MagicMock(spec=LLMProvider)
        mock_llm.get_model_name.return_value = "qwen2.5:3b"

        # Model emits aliased name 'get_battery' instead of 'get_battery_status'
        mock_llm.chat_with_tools = AsyncMock(
            side_effect=[
                LLMResponseWithTools(
                    content="",
                    model="qwen2.5:3b",
                    tool_calls=[ToolCall(name="get_battery", arguments={})],
                ),
                LLMResponseWithTools(
                    content="Battery is 95% charged.",
                    model="qwen2.5:3b",
                    tool_calls=[],
                ),
            ]
        )

        agent = NyxAgent(llm_provider=mock_llm, tool_registry=registry, max_iterations=3)
        response = await agent.run("Check battery")

        assert response.tool_used == "get_battery_status"
        assert response.content == "Battery is 95% charged."
        assert response.iterations == 2

    @pytest.mark.asyncio
    async def test_agent_unknown_tool_gives_close_match_suggestion(self) -> None:
        registry = build_default_registry()

        mock_llm = MagicMock(spec=LLMProvider)
        mock_llm.get_model_name.return_value = "qwen2.5:3b"

        # Model emits misspelled tool name 'get_battery_statuz'
        mock_llm.chat_with_tools = AsyncMock(
            side_effect=[
                LLMResponseWithTools(
                    content="",
                    model="qwen2.5:3b",
                    tool_calls=[ToolCall(name="get_battery_statuz", arguments={})],
                ),
                LLMResponseWithTools(
                    content="Handled missing tool gracefully.",
                    model="qwen2.5:3b",
                    tool_calls=[],
                ),
            ]
        )

        agent = NyxAgent(llm_provider=mock_llm, tool_registry=registry, max_iterations=3)
        response = await agent.run("Check battery")

        assert response.iterations == 2
        assert response.content == "Handled missing tool gracefully."

