"""Tests for the REST adapter."""

import asyncio
import time
import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock
import logging

from pc_client.adapters import RestAdapter


@pytest.fixture
def rest_adapter():
    """Create a REST adapter for testing."""
    adapter = RestAdapter(base_url="http://test-robot:8080", secure_mode=False)
    adapter._contract_verified_at = time.monotonic()
    adapter._contract_supported = True  # Fixture testuje metody po potwierdzonym handshake.
    return adapter


@pytest.mark.asyncio
async def test_get_healthz_success(rest_adapter):
    """Test successful healthz request."""
    mock_response = {"ok": True, "status": "ok", "uptime_s": 3600}

    with patch.object(rest_adapter.client, "get", new_callable=AsyncMock) as mock_get:
        # Create a proper mock response object
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_response
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        result = await rest_adapter.get_healthz()

        assert isinstance(result.pop("received_at"), float)
        assert result == mock_response
        mock_get.assert_called_once_with(
            "http://test-robot:8080/healthz", headers={"Accept": "application/vnd.rider.api+json;version=1"}
        )


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
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_response
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        result = await rest_adapter.get_state()

        assert isinstance(result.pop("received_at"), float)
        assert result == mock_response
        mock_get.assert_called_once_with(
            "http://test-robot:8080/state", headers={"Accept": "application/vnd.rider.api+json;version=1"}
        )


@pytest.mark.asyncio
async def test_get_sysinfo(rest_adapter):
    """Test sysinfo request."""
    mock_response = {"cpu_percent": 45.2, "memory_percent": 68.5, "disk_percent": 32.1}

    with patch.object(rest_adapter.client, "get", new_callable=AsyncMock) as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_response
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        result = await rest_adapter.get_sysinfo()

        assert isinstance(result.pop("received_at"), float)
        assert result == mock_response
        mock_get.assert_called_once_with(
            "http://test-robot:8080/sysinfo", headers={"Accept": "application/vnd.rider.api+json;version=1"}
        )


@pytest.mark.asyncio
async def test_get_vision_snap_info(rest_adapter):
    """Test vision snap-info request."""
    mock_response = {"snap_count": 10, "last_snap_ts": 1234567890}

    with patch.object(rest_adapter.client, "get", new_callable=AsyncMock) as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_response
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        result = await rest_adapter.get_vision_snap_info()

        assert isinstance(result.pop("received_at"), float)
        assert result == mock_response
        mock_get.assert_called_once_with(
            "http://test-robot:8080/vision/snap-info", headers={"Accept": "application/vnd.rider.api+json;version=1"}
        )


@pytest.mark.asyncio
async def test_get_vision_obstacle(rest_adapter):
    """Test vision obstacle request."""
    mock_response = {"present": True, "confidence": 0.87, "edge_pct": 0.45}

    with patch.object(rest_adapter.client, "get", new_callable=AsyncMock) as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_response
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        result = await rest_adapter.get_vision_obstacle()

        assert isinstance(result.pop("received_at"), float)
        assert result == mock_response
        mock_get.assert_called_once_with(
            "http://test-robot:8080/vision/obstacle", headers={"Accept": "application/vnd.rider.api+json;version=1"}
        )


@pytest.mark.asyncio
async def test_get_app_metrics(rest_adapter):
    """Test app metrics request."""
    mock_response = {"ok": True, "metrics": {"control": {"ok": 42, "error": 3}}, "total_errors": 3}

    with patch.object(rest_adapter.client, "get", new_callable=AsyncMock) as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_response
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        result = await rest_adapter.get_app_metrics()

        assert isinstance(result.pop("received_at"), float)
        assert result == mock_response
        mock_get.assert_called_once_with(
            "http://test-robot:8080/api/app-metrics", headers={"Accept": "application/vnd.rider.api+json;version=1"}
        )


@pytest.mark.asyncio
async def test_get_resource_success(rest_adapter):
    """Test fetching a specific resource."""
    mock_response = {"name": "mic", "free": True}

    with patch.object(rest_adapter.client, "get", new_callable=AsyncMock) as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_response
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        result = await rest_adapter.get_resource("mic")

        assert isinstance(result.pop("received_at"), float)
        assert result == mock_response
        mock_get.assert_called_once_with(
            "http://test-robot:8080/api/resource/mic", headers={"Accept": "application/vnd.rider.api+json;version=1"}
        )


@pytest.mark.asyncio
async def test_get_resource_error(rest_adapter):
    """Test error while fetching resource."""
    with patch.object(rest_adapter.client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = httpx.RequestError("boom")

        result = await rest_adapter.get_resource("mic")

        assert "error" in result


@pytest.mark.asyncio
async def test_post_resource_action(rest_adapter):
    """Test posting a resource action."""
    payload = {"action": "release"}
    mock_response = {"ok": True}

    with patch.object(rest_adapter.client, "post", new_callable=AsyncMock) as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_response
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        result = await rest_adapter.post_resource_action("mic", payload)

        assert isinstance(result.pop("received_at"), float)
        assert result == mock_response
        mock_post.assert_called_once_with(
            "http://test-robot:8080/api/resource/mic",
            json=payload,
            headers={"Accept": "application/vnd.rider.api+json;version=1"},
        )


@pytest.mark.asyncio
async def test_post_control(rest_adapter):
    """Test control command post."""
    command = {"type": "drive", "lx": 0.5, "az": 0.0}
    mock_response = {"ok": True}

    with patch.object(rest_adapter.client, "post", new_callable=AsyncMock) as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_response
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        result = await rest_adapter.post_control(command)

        assert isinstance(result.pop("received_at"), float)
        assert result == mock_response
        mock_post.assert_called_once_with(
            "http://test-robot:8080/api/control",
            json=command,
            headers={"Accept": "application/vnd.rider.api+json;version=1"},
        )


@pytest.mark.asyncio
async def test_ai_mode_methods(rest_adapter):
    """Test AI mode getter and setter."""
    with patch.object(rest_adapter.client, "get", new_callable=AsyncMock) as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"mode": "local", "changed_ts": 123}
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp
        data = await rest_adapter.get_ai_mode()
        assert data["mode"] == "local"
        mock_get.assert_called_once_with(
            "http://test-robot:8080/api/system/ai-mode", headers={"Accept": "application/vnd.rider.api+json;version=1"}
        )

    with patch.object(rest_adapter.client, "put", new_callable=AsyncMock) as mock_put:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"mode": "pc_offload"}
        mock_resp.raise_for_status.return_value = None
        mock_put.return_value = mock_resp
        data = await rest_adapter.set_ai_mode("pc_offload")
        assert data["mode"] == "pc_offload"
        mock_put.assert_called_once_with(
            "http://test-robot:8080/api/system/ai-mode",
            json={"mode": "pc_offload"},
            headers={"Accept": "application/vnd.rider.api+json;version=1"},
        )


@pytest.mark.asyncio
async def test_provider_methods(rest_adapter):
    """Test provider state and health helpers."""
    with patch.object(rest_adapter.client, "get", new_callable=AsyncMock) as mock_get_state:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"domains": {}}
        mock_resp.raise_for_status.return_value = None
        mock_get_state.return_value = mock_resp
        data = await rest_adapter.get_providers_state()
        assert "domains" in data
        mock_get_state.assert_called_once_with(
            "http://test-robot:8080/api/providers/state", headers={"Accept": "application/vnd.rider.api+json;version=1"}
        )

    with patch.object(rest_adapter.client, "patch", new_callable=AsyncMock) as mock_patch:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"success": True}
        mock_resp.raise_for_status.return_value = None
        mock_patch.return_value = mock_resp
        result = await rest_adapter.patch_provider("voice", {"target": "pc"})
        assert result["success"] is True
        mock_patch.assert_called_once_with(
            "http://test-robot:8080/api/providers/voice",
            json={"target": "pc"},
            headers={"Accept": "application/vnd.rider.api+json;version=1"},
        )

    with patch.object(rest_adapter.client, "get", new_callable=AsyncMock) as mock_get_health:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"voice": {"status": "online"}}
        mock_resp.raise_for_status.return_value = None
        mock_get_health.return_value = mock_resp
        data = await rest_adapter.get_providers_health()
        assert "voice" in data
        mock_get_health.assert_called_once_with(
            "http://test-robot:8080/api/providers/health",
            headers={"Accept": "application/vnd.rider.api+json;version=1"},
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
        adapter = RestAdapter(base_url="http://test-robot:8080", secure_mode=False)

        assert adapter.client is not None
        assert "DEVELOPMENT mode (Insecure)" in caplog.text

        await adapter.close()


@pytest.mark.asyncio
async def test_secure_mode_initialization_with_certificates(caplog):
    """Test REST adapter initializes correctly in secure mode with certificates."""
    with caplog.at_level(logging.INFO):
        with patch('pc_client.adapters.rest_adapter.httpx.AsyncClient') as mock_client:
            with patch('pc_client.adapters.rest_adapter.Path') as mock_path:
                # Mock Path.exists() to return True for all certificate files
                mock_path.return_value.exists.return_value = True

                adapter = RestAdapter(
                    base_url="https://test-robot:8443",
                    secure_mode=True,
                    mtls_cert_path="/path/to/cert.pem",
                    mtls_key_path="/path/to/key.pem",
                    mtls_ca_path="/path/to/ca.pem",
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
            secure_mode=True,
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
        adapter = RestAdapter(base_url="http://test-robot:8080", secure_mode=True, mtls_cert_path="/path/to/cert.pem")

        assert adapter.client is not None
        assert "SECURE_MODE=true but mTLS certificates not fully configured" in caplog.text

        await adapter.close()


@pytest.mark.asyncio
async def test_secure_mode_nonexistent_certificate_files(caplog):
    """Test REST adapter warns when certificate files don't exist."""
    with caplog.at_level(logging.WARNING):
        with patch('pc_client.adapters.rest_adapter.Path') as mock_path:
            # Mock Path.exists() to return False for certificate files
            mock_path.return_value.exists.return_value = False

            adapter = RestAdapter(
                base_url="http://test-robot:8080",
                secure_mode=True,
                mtls_cert_path="/path/to/cert.pem",
                mtls_key_path="/path/to/key.pem",
                mtls_ca_path="/path/to/ca.pem",
            )

            assert adapter.client is not None
            assert "one or more certificate files not found" in caplog.text
            assert "Falling back to insecure mode" in caplog.text

            await adapter.close()


@pytest.mark.asyncio
async def test_concurrent_reads_share_transfer_without_reusing_safety_clock(rest_adapter):
    entered, release = asyncio.Event(), asyncio.Event()

    async def response(*args, **kwargs):
        entered.set()
        await release.wait()
        result = MagicMock()
        result.status_code = 200
        result.json.return_value = {"server_time": 123, "safety": {"generation": "g", "observed_at": 122}}
        return result

    with patch.object(rest_adapter.client, "get", new_callable=AsyncMock, side_effect=response) as upstream:
        first = asyncio.create_task(rest_adapter.get_control_state())
        await entered.wait()
        second = asyncio.create_task(rest_adapter.get_control_state())
        await asyncio.sleep(0)
        release.set()
        a, b = await asyncio.gather(first, second)
        assert upstream.await_count == 1
        a["safety"]["generation"] = "changed"
        assert b["safety"]["generation"] == "g"
        assert a["received_at"] == b["received_at"]
        assert b["server_time"] == 123
        await rest_adapter.get_control_state()
        assert upstream.await_count == 2  # Subsequent permission reads remain fresh.


@pytest.mark.asyncio
async def test_cancelling_one_read_does_not_cancel_other_consumers(rest_adapter):
    entered, release = asyncio.Event(), asyncio.Event()

    async def response(*args, **kwargs):
        entered.set()
        await release.wait()
        result = MagicMock()
        result.status_code = 200
        result.json.return_value = {"safety": {"generation": "g"}}
        return result

    with patch.object(rest_adapter.client, "get", new_callable=AsyncMock, side_effect=response) as upstream:
        first = asyncio.create_task(rest_adapter.get_control_state())
        await entered.wait()
        second = asyncio.create_task(rest_adapter.get_control_state())
        await asyncio.sleep(0)
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first
        release.set()
        assert (await second)["safety"]["generation"] == "g"
        assert upstream.await_count == 1


@pytest.mark.asyncio
async def test_shutdown_cancels_detached_reads_after_mutation_invalidation(rest_adapter):
    entered, release = asyncio.Event(), asyncio.Event()

    async def response(*args, **kwargs):
        entered.set()
        await release.wait()

    with patch.object(rest_adapter.client, "get", new_callable=AsyncMock, side_effect=response):
        reader = asyncio.create_task(rest_adapter.get_control_state())
        await entered.wait()
        rest_adapter._read_flights.clear()  # A write invalidates sharing, not the running read.
        await rest_adapter.close()
        with pytest.raises(asyncio.CancelledError):
            await reader
        assert not rest_adapter._read_tasks
