"""Tests for ServiceManager core module."""

import pytest
from pc_client.core.service_manager import ServiceManager, DEFAULT_LOCAL_SERVICES


class MockRestAdapter:
    """Mock adapter for testing remote service calls."""

    def __init__(self, services_response=None, action_response=None):
        self.services_response = services_response or {"services": []}
        self.action_response = action_response or {"ok": True}
        self.get_services_called = False
        self.service_action_calls = []

    async def get_services(self):
        self.get_services_called = True
        return self.services_response

    async def service_action(self, unit, payload):
        self.service_action_calls.append({"unit": unit, "payload": payload})
        return self.action_response


@pytest.mark.asyncio
async def test_get_local_services():
    """Test getting local services returns default services."""
    manager = ServiceManager()
    services = manager.get_local_services()

    assert len(services) == len(DEFAULT_LOCAL_SERVICES)
    for svc in services:
        assert "unit" in svc
        assert "is_local" in svc
        assert svc["is_local"] is True
        assert "ts" in svc


@pytest.mark.asyncio
async def test_get_all_services_without_adapter():
    """Test get_all_services without adapter returns only local services."""
    manager = ServiceManager()
    result = await manager.get_all_services()

    assert "services" in result
    assert "timestamp" in result
    assert len(result["services"]) == len(DEFAULT_LOCAL_SERVICES)


@pytest.mark.asyncio
async def test_get_all_services_with_adapter():
    """Test get_all_services with adapter merges remote services."""
    remote_services = [
        {"unit": "remote.service", "desc": "Remote service", "active": "active", "is_local": False}
    ]
    adapter = MockRestAdapter(services_response={"services": remote_services})
    manager = ServiceManager(rest_adapter=adapter)

    result = await manager.get_all_services()

    assert adapter.get_services_called
    services = result["services"]
    # Should have local + remote services
    assert len(services) > len(DEFAULT_LOCAL_SERVICES)
    # Check remote service is present
    remote = next((s for s in services if s["unit"] == "remote.service"), None)
    assert remote is not None


@pytest.mark.asyncio
async def test_get_service_graph():
    """Test service graph generation."""
    manager = ServiceManager()
    graph = await manager.get_service_graph()

    assert "generated_at" in graph
    assert "nodes" in graph
    assert "edges" in graph
    assert isinstance(graph["nodes"], list)
    assert isinstance(graph["edges"], list)
    assert len(graph["nodes"]) == len(DEFAULT_LOCAL_SERVICES)

    # Check node structure
    node = graph["nodes"][0]
    assert "label" in node
    assert "unit" in node
    assert "status" in node
    assert "group" in node
    assert "is_local" in node


@pytest.mark.asyncio
async def test_control_local_service_start():
    """Test starting a local service."""
    manager = ServiceManager()

    # Stop service first
    await manager.control_service("voice.provider", "stop")
    # Verify it's stopped
    services = manager.get_local_services()
    voice = next(s for s in services if s["unit"] == "voice.provider")
    assert voice["active"] == "inactive"

    # Start it
    result = await manager.control_service("voice.provider", "start")
    assert result["ok"] is True
    assert result["action"] == "start"

    # Verify it's running
    services = manager.get_local_services()
    voice = next(s for s in services if s["unit"] == "voice.provider")
    assert voice["active"] == "active"


@pytest.mark.asyncio
async def test_control_local_service_stop():
    """Test stopping a local service."""
    manager = ServiceManager()

    result = await manager.control_service("voice.provider", "stop")
    assert result["ok"] is True
    assert result["action"] == "stop"

    services = manager.get_local_services()
    voice = next(s for s in services if s["unit"] == "voice.provider")
    assert voice["active"] == "inactive"
    assert voice["sub"] == "dead"


@pytest.mark.asyncio
async def test_control_local_service_restart():
    """Test restarting a local service."""
    manager = ServiceManager()

    result = await manager.control_service("cache.service", "restart")
    assert result["ok"] is True
    assert result["action"] == "restart"

    services = manager.get_local_services()
    cache = next(s for s in services if s["unit"] == "cache.service")
    assert cache["active"] == "active"


@pytest.mark.asyncio
async def test_control_local_service_enable_disable():
    """Test enable/disable local service."""
    manager = ServiceManager()

    result = await manager.control_service("text.provider", "disable")
    assert result["ok"] is True

    services = manager.get_local_services()
    text = next(s for s in services if s["unit"] == "text.provider")
    assert text["enabled"] == "disabled"

    result = await manager.control_service("text.provider", "enable")
    assert result["ok"] is True

    services = manager.get_local_services()
    text = next(s for s in services if s["unit"] == "text.provider")
    assert text["enabled"] == "enabled"


@pytest.mark.asyncio
async def test_control_local_service_not_found():
    """Test controlling non-existent local service."""
    manager = ServiceManager()

    result = await manager.control_service("nonexistent.service", "start")
    assert result["ok"] is False
    assert "not found" in result["error"]


@pytest.mark.asyncio
async def test_control_local_service_invalid_action():
    """Test controlling local service with invalid action."""
    manager = ServiceManager()

    result = await manager.control_service("voice.provider", "invalid_action")
    assert result["ok"] is False
    assert "unsupported" in result["error"].lower()


@pytest.mark.asyncio
async def test_control_remote_service():
    """Test controlling a remote service through adapter."""
    adapter = MockRestAdapter(action_response={"ok": True, "unit": "remote.service", "action": "start"})
    manager = ServiceManager(rest_adapter=adapter)

    result = await manager.control_service("remote.service", "start")

    assert len(adapter.service_action_calls) == 1
    call = adapter.service_action_calls[0]
    assert call["unit"] == "remote.service"
    assert call["payload"]["action"] == "start"


@pytest.mark.asyncio
async def test_set_adapter():
    """Test setting adapter dynamically."""
    manager = ServiceManager()
    assert manager._rest_adapter is None

    adapter = MockRestAdapter()
    manager.set_adapter(adapter)
    assert manager._rest_adapter is adapter


@pytest.mark.asyncio
async def test_service_to_node_status_mapping():
    """Test status mapping in node generation."""
    manager = ServiceManager()

    # Test active status
    manager._local_services["test.service"] = {
        "unit": "test.service",
        "active": "active",
        "group": "test",
        "desc": "Test service",
    }
    graph = await manager.get_service_graph()
    test_node = next(n for n in graph["nodes"] if n["unit"] == "test.service")
    assert test_node["status"] == "active"

    # Test failed status
    manager._local_services["test.service"]["active"] = "failed"
    graph = await manager.get_service_graph()
    test_node = next(n for n in graph["nodes"] if n["unit"] == "test.service")
    assert test_node["status"] == "failed"

    # Test inactive status
    manager._local_services["test.service"]["active"] = "inactive"
    graph = await manager.get_service_graph()
    test_node = next(n for n in graph["nodes"] if n["unit"] == "test.service")
    assert test_node["status"] == "inactive"
