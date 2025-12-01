"""Tests for MCP Tool Registry.

Testy rejestracji narzędzi, walidacji i wywoływania handlerów.
"""

import pytest
from pc_client.mcp.registry import Tool, ToolRegistry, ToolInvokeResult


class TestToolRegistry:
    """Tests for ToolRegistry class."""

    @pytest.fixture
    def registry(self):
        """Create a fresh registry for each test."""
        reg = ToolRegistry()
        return reg

    def test_register_tool(self, registry):
        """Test registering a tool."""
        tool = Tool(
            name="test.tool",
            description="A test tool",
            handler=lambda: {"ok": True},
        )
        registry.register(tool)
        assert registry.get("test.tool") is not None
        assert registry.get("test.tool").name == "test.tool"

    def test_register_duplicate_raises(self, registry):
        """Test that registering duplicate tool raises ValueError."""
        tool = Tool(name="test.tool", description="A test tool")
        registry.register(tool)
        with pytest.raises(ValueError, match="already registered"):
            registry.register(tool)

    def test_unregister_tool(self, registry):
        """Test unregistering a tool."""
        tool = Tool(name="test.tool", description="A test tool")
        registry.register(tool)
        assert registry.unregister("test.tool") is True
        assert registry.get("test.tool") is None

    def test_unregister_nonexistent(self, registry):
        """Test unregistering a nonexistent tool returns False."""
        assert registry.unregister("nonexistent") is False

    def test_list_tools(self, registry):
        """Test listing all tools."""
        tool1 = Tool(name="tool1", description="Tool 1")
        tool2 = Tool(name="tool2", description="Tool 2")
        registry.register(tool1)
        registry.register(tool2)
        tools = registry.list_tools()
        assert len(tools) == 2
        names = [t.name for t in tools]
        assert "tool1" in names
        assert "tool2" in names

    def test_list_tool_names(self, registry):
        """Test listing tool names."""
        tool1 = Tool(name="tool1", description="Tool 1")
        tool2 = Tool(name="tool2", description="Tool 2")
        registry.register(tool1)
        registry.register(tool2)
        names = registry.list_tool_names()
        assert "tool1" in names
        assert "tool2" in names

    def test_clear(self, registry):
        """Test clearing the registry."""
        tool = Tool(name="test.tool", description="A test tool")
        registry.register(tool)
        registry.clear()
        assert len(registry.list_tools()) == 0

    def test_get_stats(self, registry):
        """Test getting registry stats."""
        tool = Tool(name="test.tool", description="A test tool")
        registry.register(tool)
        stats = registry.get_stats()
        assert stats["total_tools"] == 1
        assert stats["invocation_count"] == 0
        assert stats["last_invoked_tool"] is None


class TestToolInvocation:
    """Tests for tool invocation."""

    @pytest.fixture
    def registry(self):
        """Create a fresh registry for each test."""
        return ToolRegistry()

    @pytest.mark.asyncio
    async def test_invoke_simple_tool(self, registry):
        """Test invoking a simple tool."""
        tool = Tool(
            name="test.simple",
            description="A simple tool",
            handler=lambda: {"result": "success"},
        )
        registry.register(tool)

        result = await registry.invoke("test.simple")
        assert result.ok is True
        assert result.tool == "test.simple"
        assert result.result == {"result": "success"}
        assert result.error is None

    @pytest.mark.asyncio
    async def test_invoke_with_arguments(self, registry):
        """Test invoking a tool with arguments."""
        tool = Tool(
            name="test.args",
            description="Tool with arguments",
            handler=lambda x, y: {"sum": x + y},
        )
        registry.register(tool)

        result = await registry.invoke("test.args", {"x": 5, "y": 3})
        assert result.ok is True
        assert result.result == {"sum": 8}

    @pytest.mark.asyncio
    async def test_invoke_async_handler(self, registry):
        """Test invoking an async handler."""

        async def async_handler():
            return {"async": True}

        tool = Tool(
            name="test.async",
            description="Async tool",
            handler=async_handler,
        )
        registry.register(tool)

        result = await registry.invoke("test.async")
        assert result.ok is True
        assert result.result == {"async": True}

    @pytest.mark.asyncio
    async def test_invoke_nonexistent_tool(self, registry):
        """Test invoking a nonexistent tool."""
        result = await registry.invoke("nonexistent")
        assert result.ok is False
        assert "not found" in result.error

    @pytest.mark.asyncio
    async def test_invoke_tool_without_handler(self, registry):
        """Test invoking a tool without handler."""
        tool = Tool(name="test.nohandler", description="No handler")
        registry.register(tool)

        result = await registry.invoke("test.nohandler")
        assert result.ok is False
        assert "no handler" in result.error

    @pytest.mark.asyncio
    async def test_invoke_requires_confirm(self, registry):
        """Test tool requiring confirmation."""
        tool = Tool(
            name="test.confirm",
            description="Requires confirmation",
            handler=lambda: {"done": True},
            permissions=["high", "confirm"],
        )
        registry.register(tool)

        # Without confirmation
        result = await registry.invoke("test.confirm")
        assert result.ok is False
        assert "confirmation" in result.error.lower()
        assert result.meta.get("requires_confirm") is True

        # With confirmation
        result = await registry.invoke("test.confirm", confirm=True)
        assert result.ok is True
        assert result.result == {"done": True}

    @pytest.mark.asyncio
    async def test_invoke_updates_stats(self, registry):
        """Test that successful invocation updates stats."""
        tool = Tool(
            name="test.stats",
            description="Stats test",
            handler=lambda: {"ok": True},
        )
        registry.register(tool)

        await registry.invoke("test.stats")
        stats = registry.get_stats()
        assert stats["invocation_count"] == 1
        assert stats["last_invoked_tool"] == "test.stats"

    @pytest.mark.asyncio
    async def test_invoke_with_invalid_args(self, registry):
        """Test invoking with invalid arguments."""
        tool = Tool(
            name="test.invalid",
            description="Test tool",
            handler=lambda x: {"x": x},
        )
        registry.register(tool)

        result = await registry.invoke("test.invalid", {"y": 5})
        assert result.ok is False
        assert "Invalid arguments" in result.error

    @pytest.mark.asyncio
    async def test_invoke_with_exception(self, registry):
        """Test invoking a tool that raises an exception."""

        def failing_handler():
            raise RuntimeError("Something went wrong")

        tool = Tool(
            name="test.fail",
            description="Failing tool",
            handler=failing_handler,
        )
        registry.register(tool)

        result = await registry.invoke("test.fail")
        assert result.ok is False
        assert "Something went wrong" in result.error


class TestToolInvokeResult:
    """Tests for ToolInvokeResult class."""

    def test_to_dict(self):
        """Test converting result to dictionary."""
        result = ToolInvokeResult(
            ok=True,
            tool="test.tool",
            result={"data": "value"},
            meta={"duration_ms": 10},
        )
        d = result.to_dict()
        assert d["ok"] is True
        assert d["tool"] == "test.tool"
        assert d["result"] == {"data": "value"}
        assert d["error"] is None
        assert d["meta"]["duration_ms"] == 10


class TestTool:
    """Tests for Tool dataclass."""

    def test_default_values(self):
        """Test tool with default values."""
        tool = Tool(name="test", description="Test")
        assert tool.args_schema == {"type": "object", "properties": {}, "required": []}
        assert tool.permissions == ["low"]
        assert tool.handler is None

    def test_custom_values(self):
        """Test tool with custom values."""
        schema = {"type": "object", "properties": {"x": {"type": "integer"}}}
        handler = lambda x: x

        tool = Tool(
            name="custom",
            description="Custom tool",
            args_schema=schema,
            handler=handler,
            permissions=["high"],
        )
        assert tool.args_schema == schema
        assert tool.permissions == ["high"]
        assert tool.handler is handler
