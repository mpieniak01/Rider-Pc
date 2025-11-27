"""Tests for network utilities."""

import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from pc_client.api.server import create_app
from pc_client.cache import CacheManager
from pc_client.config import Settings
from pc_client.utils.network import get_local_ip, check_connectivity, _parse_ping_latency, _build_ping_command


class TestGetLocalIp:
    """Tests for get_local_ip function."""

    def test_returns_string(self):
        """get_local_ip should return a string."""
        result = get_local_ip()
        assert isinstance(result, str)

    def test_returns_valid_ip_format(self):
        """get_local_ip should return a valid IP address format."""
        result = get_local_ip()
        # Should match IP pattern or be localhost fallback
        parts = result.split('.')
        assert len(parts) == 4
        for part in parts:
            assert part.isdigit()
            assert 0 <= int(part) <= 255

    @patch('socket.socket')
    def test_fallback_on_error(self, mock_socket):
        """get_local_ip should return 127.0.0.1 on socket error."""
        mock_socket.return_value.__enter__.return_value.connect.side_effect = OSError("Network error")
        result = get_local_ip()
        assert result == "127.0.0.1"


class TestBuildPingCommand:
    """Tests for _build_ping_command function."""

    @patch('platform.system')
    def test_linux_command(self, mock_system):
        """Should build correct command for Linux."""
        mock_system.return_value = 'Linux'
        cmd = _build_ping_command('192.168.1.1')
        assert cmd == ['ping', '-c', '1', '-W', '1', '192.168.1.1']

    @patch('platform.system')
    def test_windows_command(self, mock_system):
        """Should build correct command for Windows."""
        mock_system.return_value = 'Windows'
        cmd = _build_ping_command('192.168.1.1')
        assert cmd == ['ping', '-n', '1', '-w', '1000', '192.168.1.1']

    @patch('platform.system')
    def test_macos_command(self, mock_system):
        """Should build correct command for macOS (same as Linux)."""
        mock_system.return_value = 'Darwin'
        cmd = _build_ping_command('192.168.1.1')
        assert cmd == ['ping', '-c', '1', '-W', '1', '192.168.1.1']


class TestParsePingLatency:
    """Tests for _parse_ping_latency function."""

    def test_parse_linux_output(self):
        """Should parse latency from Linux ping output."""
        output = "64 bytes from 8.8.8.8: icmp_seq=1 ttl=118 time=15.3 ms"
        latency = _parse_ping_latency(output)
        assert latency == 15.3

    def test_parse_windows_output(self):
        """Should parse latency from Windows ping output."""
        output = "Reply from 8.8.8.8: bytes=32 time=12ms TTL=118"
        latency = _parse_ping_latency(output)
        assert latency == 12.0

    def test_parse_windows_less_than_1ms(self):
        """Should parse latency from Windows ping when time<1ms."""
        output = "Reply from 192.168.1.1: bytes=32 time<1ms TTL=64"
        latency = _parse_ping_latency(output)
        assert latency == 1.0

    def test_parse_no_latency(self):
        """Should return None when no latency found."""
        output = "Request timed out."
        latency = _parse_ping_latency(output)
        assert latency is None


class TestCheckConnectivity:
    """Tests for check_connectivity function."""

    @pytest.mark.asyncio
    async def test_empty_host_returns_offline(self):
        """Should return offline for empty host."""
        result = await check_connectivity("")
        assert result == {"status": "offline"}

    @pytest.mark.asyncio
    async def test_none_host_returns_offline(self):
        """Should return offline for None host."""
        result = await check_connectivity(None)
        assert result == {"status": "offline"}

    @pytest.mark.asyncio
    async def test_successful_ping(self):
        """Should return online with latency for successful ping."""
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(
            b"64 bytes from 8.8.8.8: icmp_seq=1 ttl=118 time=10.5 ms",
            b""
        ))

        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            result = await check_connectivity("8.8.8.8")

        assert result["status"] == "online"
        assert result["latency_ms"] == 10.5

    @pytest.mark.asyncio
    async def test_failed_ping(self):
        """Should return offline for failed ping."""
        mock_process = AsyncMock()
        mock_process.returncode = 1
        mock_process.communicate = AsyncMock(return_value=(
            b"Request timed out.",
            b""
        ))

        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            result = await check_connectivity("192.168.1.254")

        assert result["status"] == "offline"
        assert "latency_ms" not in result

    @pytest.mark.asyncio
    async def test_timeout_handling(self):
        """Should return offline on timeout."""
        async def slow_communicate():
            await asyncio.sleep(10)  # Will be cancelled by timeout
            return b"", b""

        mock_process = MagicMock()
        mock_process.communicate = slow_communicate
        mock_process.kill = MagicMock()
        mock_process.wait = AsyncMock()

        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            result = await check_connectivity("8.8.8.8")

        assert result["status"] == "offline"

    @pytest.mark.asyncio
    async def test_ping_not_found(self):
        """Should return offline when ping command not found."""
        with patch('asyncio.create_subprocess_exec', side_effect=FileNotFoundError):
            result = await check_connectivity("8.8.8.8")

        assert result["status"] == "offline"


class TestNetworkStatusEndpoint:
    """Tests for /api/status/network endpoint."""

    def test_network_status_endpoint_returns_correct_structure(self, tmp_path):
        """Network status endpoint should return expected structure."""
        settings = Settings()
        cache = CacheManager(db_path=str(tmp_path / "cache.db"))
        app = create_app(settings, cache)
        client = TestClient(app)

        # Mock the network functions to avoid actual network calls
        with patch('pc_client.api.routers.status_router.get_local_ip') as mock_ip, \
             patch('pc_client.api.routers.status_router.check_connectivity') as mock_check:

            mock_ip.return_value = "192.168.0.15"
            mock_check.return_value = {"status": "online", "latency_ms": 10}

            resp = client.get("/api/status/network")

        assert resp.status_code == 200
        data = resp.json()

        # Check required fields
        assert "local_ip" in data
        assert "rider_pi" in data
        assert "internet" in data
        assert "timestamp" in data

        # Check nested structure
        assert "host" in data["rider_pi"]
        assert "status" in data["rider_pi"]
        assert "host" in data["internet"]
        assert "status" in data["internet"]

    def test_network_status_endpoint_includes_latency_when_online(self, tmp_path):
        """Network status endpoint should include latency when host is online."""
        settings = Settings()
        cache = CacheManager(db_path=str(tmp_path / "cache.db"))
        app = create_app(settings, cache)
        client = TestClient(app)

        async def mock_check(host, port=80):
            return {"status": "online", "latency_ms": 15.5}

        with patch('pc_client.api.routers.status_router.get_local_ip', return_value="192.168.0.15"), \
             patch('pc_client.api.routers.status_router.check_connectivity', mock_check):

            resp = client.get("/api/status/network")

        assert resp.status_code == 200
        data = resp.json()

        assert data["rider_pi"]["latency"] == 15
        assert data["internet"]["latency"] == 15

    def test_network_status_endpoint_offline(self, tmp_path):
        """Network status endpoint should handle offline hosts."""
        settings = Settings()
        cache = CacheManager(db_path=str(tmp_path / "cache.db"))
        app = create_app(settings, cache)
        client = TestClient(app)

        async def mock_check(host, port=80):
            return {"status": "offline"}

        with patch('pc_client.api.routers.status_router.get_local_ip', return_value="127.0.0.1"), \
             patch('pc_client.api.routers.status_router.check_connectivity', mock_check):

            resp = client.get("/api/status/network")

        assert resp.status_code == 200
        data = resp.json()

        assert data["rider_pi"]["status"] == "offline"
        assert "latency" not in data["rider_pi"]
        assert data["internet"]["status"] == "offline"
        assert "latency" not in data["internet"]
