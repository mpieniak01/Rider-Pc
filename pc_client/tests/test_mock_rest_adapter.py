"""Tests for MockRestAdapter."""

import pytest
from pc_client.adapters.mock_rest_adapter import MockRestAdapter


@pytest.fixture
def mock_adapter():
    """Create a MockRestAdapter instance."""
    return MockRestAdapter()


@pytest.mark.asyncio
async def test_mock_adapter_get_healthz(mock_adapter):
    """Test that healthz returns mock data."""
    result = await mock_adapter.get_healthz()
    assert result["ok"] is True
    assert result["status"] == "healthy"
    assert "timestamp" in result


@pytest.mark.asyncio
async def test_mock_adapter_get_state(mock_adapter):
    """Test that state returns mock data."""
    result = await mock_adapter.get_state()
    assert result["present"] is True
    assert result["mode"] == "auto"
    assert "tracking" in result
    assert "navigator" in result


@pytest.mark.asyncio
async def test_mock_adapter_get_sysinfo(mock_adapter):
    """Test that sysinfo returns mock data."""
    result = await mock_adapter.get_sysinfo()
    assert result["hostname"] == "mock-rider-pi"
    assert "uptime" in result
    assert "cpu_percent" in result
    assert "memory_percent" in result


@pytest.mark.asyncio
async def test_mock_adapter_fetch_binary(mock_adapter):
    """Test that binary fetch returns mock image."""
    content, media_type, headers = await mock_adapter.fetch_binary("/camera/last")
    assert len(content) > 0
    assert media_type == "image/png"
    assert headers["content-type"] == "image/png"
    assert "last-modified" in headers


@pytest.mark.asyncio
async def test_mock_adapter_post_control(mock_adapter):
    """Test that control commands return success."""
    result = await mock_adapter.post_control({"cmd": "move", "dir": "forward"})
    assert result["ok"] is True
    assert result["command"] == "move"
    assert "timestamp" in result


@pytest.mark.asyncio
async def test_mock_adapter_get_services(mock_adapter):
    """Test that services returns mock service list."""
    result = await mock_adapter.get_services()
    assert "services" in result
    assert len(result["services"]) > 0
    assert result["services"][0]["unit"] == "rider-cam-preview.service"


@pytest.mark.asyncio
async def test_mock_adapter_get_resource(mock_adapter):
    """Test that resource status returns mock data."""
    result = await mock_adapter.get_resource("camera")
    assert result["name"] == "camera"
    assert "free" in result
    assert "holders" in result


@pytest.mark.asyncio
async def test_mock_adapter_get_providers_state(mock_adapter):
    """Test that provider state returns mock data."""
    result = await mock_adapter.get_providers_state()
    assert "vision" in result
    assert "voice" in result
    assert "text" in result
    assert result["vision"]["status"] == "ready"


@pytest.mark.asyncio
async def test_mock_adapter_close(mock_adapter):
    """Test that close completes without error."""
    await mock_adapter.close()
    # Should complete without raising an exception
