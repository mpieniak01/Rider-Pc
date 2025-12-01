"""Tests for MCP Router endpoints.

Testy endpointów API MCP:
- GET /api/mcp/tools
- GET /api/mcp/resources
- POST /api/mcp/tools/invoke
- GET /api/mcp/stats
"""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from pc_client.api.routers import mcp_router
from pc_client.mcp.registry import Tool, ToolRegistry


@pytest.fixture
def app():
    """Create test FastAPI app with MCP router."""
    test_app = FastAPI()
    test_app.include_router(mcp_router.router)

    # Mock settings
    class MockSettings:
        mcp_standalone = False
        mcp_port = 8210

    test_app.state.settings = MockSettings()

    return test_app


@pytest.fixture
def clean_registry():
    """Ensure registry is clean before and after each test."""
    # Import the global registry
    from pc_client.mcp.registry import registry

    # Store current tools
    original_tools = list(registry._tools.keys())

    yield registry

    # Restore original state (remove test tools, keep original)
    current_tools = list(registry._tools.keys())
    for tool_name in current_tools:
        if tool_name not in original_tools:
            registry.unregister(tool_name)


class TestListToolsEndpoint:
    """Tests for GET /api/mcp/tools endpoint."""

    @pytest.mark.asyncio
    async def test_list_tools_returns_ok(self, app):
        """Test that list tools endpoint returns ok status."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/mcp/tools")
            assert response.status_code == 200
            data = response.json()
            assert data["ok"] is True
            assert "tools" in data
            assert "count" in data

    @pytest.mark.asyncio
    async def test_list_tools_includes_system_tools(self, app):
        """Test that system tools are included in the list."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/mcp/tools")
            data = response.json()
            tool_names = [t["name"] for t in data["tools"]]
            assert "system.get_time" in tool_names
            assert "system.get_status" in tool_names

    @pytest.mark.asyncio
    async def test_list_tools_includes_robot_tools(self, app):
        """Test that robot tools are included in the list."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/mcp/tools")
            data = response.json()
            tool_names = [t["name"] for t in data["tools"]]
            assert "robot.status" in tool_names
            assert "robot.move" in tool_names

    @pytest.mark.asyncio
    async def test_list_tools_includes_weather_tools(self, app):
        """Test that weather tools are included in the list."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/mcp/tools")
            data = response.json()
            tool_names = [t["name"] for t in data["tools"]]
            assert "weather.get_summary" in tool_names

    @pytest.mark.asyncio
    async def test_list_tools_schema_structure(self, app):
        """Test that each tool has correct schema structure."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/mcp/tools")
            data = response.json()
            for tool in data["tools"]:
                assert "name" in tool
                assert "description" in tool
                assert "args_schema" in tool
                assert "permissions" in tool


class TestGetResourcesEndpoint:
    """Tests for GET /api/mcp/resources endpoint."""

    @pytest.mark.asyncio
    async def test_get_resources_returns_ok(self, app):
        """Test that resources endpoint returns ok status."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/mcp/resources")
            assert response.status_code == 200
            data = response.json()
            assert data["ok"] is True
            assert "resources" in data

    @pytest.mark.asyncio
    async def test_get_resources_includes_config(self, app):
        """Test that resources include config."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/mcp/resources")
            data = response.json()
            assert "config" in data["resources"]
            assert "mcp_standalone" in data["resources"]["config"]
            assert "mcp_port" in data["resources"]["config"]

    @pytest.mark.asyncio
    async def test_get_resources_includes_stats(self, app):
        """Test that resources include stats."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/mcp/resources")
            data = response.json()
            assert "stats" in data["resources"]
            assert "total_tools" in data["resources"]["stats"]


class TestInvokeToolEndpoint:
    """Tests for POST /api/mcp/tools/invoke endpoint."""

    @pytest.mark.asyncio
    async def test_invoke_missing_tool_name(self, app):
        """Test invoking without tool name returns 400."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/mcp/tools/invoke", json={})
            assert response.status_code == 400
            data = response.json()
            assert data["ok"] is False
            assert "Missing 'tool'" in data["error"]

    @pytest.mark.asyncio
    async def test_invoke_nonexistent_tool(self, app):
        """Test invoking nonexistent tool returns 404."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/mcp/tools/invoke", json={"tool": "nonexistent.tool"})
            assert response.status_code == 404
            data = response.json()
            assert data["ok"] is False
            assert "not found" in data["error"]

    @pytest.mark.asyncio
    async def test_invoke_system_get_time(self, app):
        """Test invoking system.get_time returns time."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/mcp/tools/invoke", json={"tool": "system.get_time"})
            assert response.status_code == 200
            data = response.json()
            assert data["ok"] is True
            assert data["tool"] == "system.get_time"
            assert "time" in data["result"]
            assert "timezone" in data["result"]
            assert "timestamp" in data["result"]

    @pytest.mark.asyncio
    async def test_invoke_system_get_status(self, app):
        """Test invoking system.get_status returns system info."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/mcp/tools/invoke", json={"tool": "system.get_status"})
            assert response.status_code == 200
            data = response.json()
            assert data["ok"] is True
            assert "platform" in data["result"]
            assert "hostname" in data["result"]

    @pytest.mark.asyncio
    async def test_invoke_robot_status(self, app):
        """Test invoking robot.status returns robot info."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/mcp/tools/invoke", json={"tool": "robot.status"})
            assert response.status_code == 200
            data = response.json()
            assert data["ok"] is True
            assert "connected" in data["result"]
            assert "battery" in data["result"]

    @pytest.mark.asyncio
    async def test_invoke_robot_move_requires_confirm(self, app):
        """Test invoking robot.move without confirm fails."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/mcp/tools/invoke",
                json={"tool": "robot.move", "arguments": {"command": "forward"}},
            )
            assert response.status_code == 400
            data = response.json()
            assert data["ok"] is False
            assert "confirmation" in data["error"].lower()

    @pytest.mark.asyncio
    async def test_invoke_robot_move_with_confirm(self, app):
        """Test invoking robot.move with confirm succeeds."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/mcp/tools/invoke",
                json={
                    "tool": "robot.move",
                    "arguments": {"command": "forward", "speed": 50},
                    "confirm": True,
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert data["ok"] is True
            assert data["result"]["executed"] is True
            assert data["result"]["command"] == "forward"

    @pytest.mark.asyncio
    async def test_invoke_weather_get_summary(self, app):
        """Test invoking weather.get_summary returns weather data."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/mcp/tools/invoke",
                json={"tool": "weather.get_summary"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["ok"] is True
            assert "temperature" in data["result"]
            assert "location" in data["result"]

    @pytest.mark.asyncio
    async def test_invoke_returns_meta(self, app):
        """Test that invoke returns meta information."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/mcp/tools/invoke", json={"tool": "system.get_time"})
            data = response.json()
            assert "meta" in data
            assert "duration_ms" in data["meta"]
            assert "host" in data["meta"]


class TestStatsEndpoint:
    """Tests for GET /api/mcp/stats endpoint."""

    @pytest.mark.asyncio
    async def test_get_stats_returns_ok(self, app):
        """Test that stats endpoint returns ok status."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/mcp/stats")
            assert response.status_code == 200
            data = response.json()
            assert data["ok"] is True
            assert "stats" in data

    @pytest.mark.asyncio
    async def test_get_stats_structure(self, app):
        """Test that stats have correct structure."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/mcp/stats")
            data = response.json()
            stats = data["stats"]
            assert "total_tools" in stats
            assert "invocation_count" in stats
            assert "last_invoked_tool" in stats
