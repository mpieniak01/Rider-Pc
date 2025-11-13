"""Tests for the REST adapter."""

import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock
import logging

from pc_client.adapters import RestAdapter


@pytest.fixture
def rest_adapter():
    """Create a REST adapter for testing."""
    adapter = RestAdapter(base_url="http://test-robot:8080", secure_mode=False)
    return adapter


@pytest.mark.asyncio
async def test_get_healthz_success(rest_adapter):
    """Test successful healthz request."""
    mock_response = {"ok": True, "status": "ok", "uptime_s": 3600}
    
    with patch.object(rest_adapter.client, "get", new_callable=AsyncMock) as mock_get:
        # Create a proper mock response object
        mock_resp = MagicMock()
        mock_resp.json.return_value = mock_response
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp
        
        result = await rest_adapter.get_healthz()
        
        assert result == mock_response
        mock_get.assert_called_once_with("http://test-robot:8080/healthz")


@pytest.mark.asyncio
async def test_get_healthz_error(rest_adapter):
    """Test healthz request with error."""
    with patch.object(rest_adapter.client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = httpx.RequestError("Connection failed")
        
        result = await rest_adapter.get_healthz()
        
        assert result["ok"] is False
        assert "error" in result


@pytest.mark.asyncio
async def test_get_state(rest_adapter):
    """Test state request."""
    mock_response = {"present": True, "confidence": 0.95, "mode": "active"}
    
    with patch.object(rest_adapter.client, "get", new_callable=AsyncMock) as mock_get:
        mock_resp = MagicMock()
        mock_resp.json.return_value = mock_response
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp
        
        result = await rest_adapter.get_state()
        
        assert result == mock_response
        mock_get.assert_called_once_with("http://test-robot:8080/state")


@pytest.mark.asyncio
async def test_get_sysinfo(rest_adapter):
    """Test sysinfo request."""
    mock_response = {
        "cpu_percent": 45.2,
        "memory_percent": 68.5,
        "disk_percent": 32.1
    }
    
    with patch.object(rest_adapter.client, "get", new_callable=AsyncMock) as mock_get:
        mock_resp = MagicMock()
        mock_resp.json.return_value = mock_response
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp
        
        result = await rest_adapter.get_sysinfo()
        
        assert result == mock_response
        mock_get.assert_called_once_with("http://test-robot:8080/sysinfo")


@pytest.mark.asyncio
async def test_get_vision_snap_info(rest_adapter):
    """Test vision snap-info request."""
    mock_response = {"snap_count": 10, "last_snap_ts": 1234567890}
    
    with patch.object(rest_adapter.client, "get", new_callable=AsyncMock) as mock_get:
        mock_resp = MagicMock()
        mock_resp.json.return_value = mock_response
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp
        
        result = await rest_adapter.get_vision_snap_info()
        
        assert result == mock_response
        mock_get.assert_called_once_with("http://test-robot:8080/vision/snap-info")


@pytest.mark.asyncio
async def test_get_vision_obstacle(rest_adapter):
    """Test vision obstacle request."""
    mock_response = {
        "present": True,
        "confidence": 0.87,
        "edge_pct": 0.45
    }
    
    with patch.object(rest_adapter.client, "get", new_callable=AsyncMock) as mock_get:
        mock_resp = MagicMock()
        mock_resp.json.return_value = mock_response
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp
        
        result = await rest_adapter.get_vision_obstacle()
        
        assert result == mock_response
        mock_get.assert_called_once_with("http://test-robot:8080/vision/obstacle")


@pytest.mark.asyncio
async def test_get_app_metrics(rest_adapter):
    """Test app metrics request."""
    mock_response = {
        "ok": True,
        "metrics": {
            "control": {"ok": 42, "error": 3}
        },
        "total_errors": 3
    }
    
    with patch.object(rest_adapter.client, "get", new_callable=AsyncMock) as mock_get:
        mock_resp = MagicMock()
        mock_resp.json.return_value = mock_response
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp
        
        result = await rest_adapter.get_app_metrics()
        
        assert result == mock_response
        mock_get.assert_called_once_with("http://test-robot:8080/api/app-metrics")


@pytest.mark.asyncio
async def test_post_control(rest_adapter):
    """Test control command post."""
    command = {"type": "drive", "lx": 0.5, "az": 0.0}
    mock_response = {"ok": True}
    
    with patch.object(rest_adapter.client, "post", new_callable=AsyncMock) as mock_post:
        mock_resp = MagicMock()
        mock_resp.json.return_value = mock_response
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp
        
        result = await rest_adapter.post_control(command)
        
        assert result == mock_response
        mock_post.assert_called_once_with(
            "http://test-robot:8080/api/control",
            json=command
        )


@pytest.mark.asyncio
async def test_close(rest_adapter):
    """Test closing the REST adapter."""
    with patch.object(rest_adapter.client, "aclose", new_callable=AsyncMock) as mock_close:
        await rest_adapter.close()
        mock_close.assert_called_once()


@pytest.mark.asyncio
async def test_insecure_mode_initialization(caplog):
    """Test REST adapter initializes correctly in insecure mode."""
    with caplog.at_level(logging.INFO):
        adapter = RestAdapter(
            base_url="http://test-robot:8080",
            secure_mode=False
        )
        
        assert adapter.client is not None
        assert "DEVELOPMENT mode (Insecure)" in caplog.text
        
        await adapter.close()


@pytest.mark.asyncio
async def test_secure_mode_initialization_with_certificates(caplog):
    """Test REST adapter initializes correctly in secure mode with certificates."""
    with caplog.at_level(logging.INFO):
        with patch('pc_client.adapters.rest_adapter.httpx.AsyncClient') as mock_client:
            adapter = RestAdapter(
                base_url="https://test-robot:8443",
                secure_mode=True,
                mtls_cert_path="/path/to/cert.pem",
                mtls_key_path="/path/to/key.pem",
                mtls_ca_path="/path/to/ca.pem"
            )
            
            assert adapter.client is not None
            assert "SECURE mode (Production) with mTLS" in caplog.text
            
            # Verify that AsyncClient was called with cert and verify parameters
            mock_client.assert_called_once()
            call_kwargs = mock_client.call_args[1]
            assert 'cert' in call_kwargs
            assert call_kwargs['cert'] == ("/path/to/cert.pem", "/path/to/key.pem")
            assert call_kwargs['verify'] == "/path/to/ca.pem"


@pytest.mark.asyncio
async def test_secure_mode_warning_without_certificates(caplog):
    """Test REST adapter warns and falls back to insecure mode when certificates are missing."""
    with caplog.at_level(logging.WARNING):
        adapter = RestAdapter(
            base_url="http://test-robot:8080",
            secure_mode=True
            # Missing certificate paths
        )
        
        assert adapter.client is not None
        assert "SECURE_MODE=true but mTLS certificates not fully configured" in caplog.text
        assert "Falling back to insecure mode" in caplog.text
        
        await adapter.close()


@pytest.mark.asyncio
async def test_secure_mode_partial_certificates_warning(caplog):
    """Test REST adapter warns when only some certificate paths are provided."""
    with caplog.at_level(logging.WARNING):
        # Only cert path provided
        adapter = RestAdapter(
            base_url="http://test-robot:8080",
            secure_mode=True,
            mtls_cert_path="/path/to/cert.pem"
        )
        
        assert adapter.client is not None
        assert "SECURE_MODE=true but mTLS certificates not fully configured" in caplog.text
        
        await adapter.close()
