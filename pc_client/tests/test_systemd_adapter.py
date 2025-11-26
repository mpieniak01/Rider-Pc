"""Tests for the SystemdAdapter and MockSystemdAdapter."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from pc_client.adapters.systemd_adapter import (
    SystemdAdapter,
    MockSystemdAdapter,
    is_systemd_available,
)


class TestIsSystemdAvailable:
    """Tests for is_systemd_available function."""

    @patch("pc_client.adapters.systemd_adapter.platform.system")
    @patch("pc_client.adapters.systemd_adapter.shutil.which")
    def test_returns_true_on_linux_with_systemctl(self, mock_which, mock_system):
        """Should return True on Linux with systemctl available."""
        mock_system.return_value = "Linux"
        mock_which.return_value = "/usr/bin/systemctl"
        assert is_systemd_available() is True

    @patch("pc_client.adapters.systemd_adapter.platform.system")
    def test_returns_false_on_windows(self, mock_system):
        """Should return False on Windows."""
        mock_system.return_value = "Windows"
        assert is_systemd_available() is False

    @patch("pc_client.adapters.systemd_adapter.platform.system")
    def test_returns_false_on_darwin(self, mock_system):
        """Should return False on macOS."""
        mock_system.return_value = "Darwin"
        assert is_systemd_available() is False

    @patch("pc_client.adapters.systemd_adapter.platform.system")
    @patch("pc_client.adapters.systemd_adapter.shutil.which")
    def test_returns_false_when_systemctl_not_found(self, mock_which, mock_system):
        """Should return False on Linux without systemctl."""
        mock_system.return_value = "Linux"
        mock_which.return_value = None
        assert is_systemd_available() is False


class TestMockSystemdAdapter:
    """Tests for MockSystemdAdapter."""

    @pytest.mark.asyncio
    async def test_get_unit_status_unknown_service(self):
        """Should return 'unknown' for non-existent service."""
        adapter = MockSystemdAdapter()
        status = await adapter.get_unit_status("nonexistent.service")
        assert status == "unknown"

    @pytest.mark.asyncio
    async def test_get_unit_status_existing_service(self):
        """Should return correct status for existing service."""
        adapter = MockSystemdAdapter()
        adapter.add_service("test.service", active="active")
        status = await adapter.get_unit_status("test.service")
        assert status == "active"

    @pytest.mark.asyncio
    async def test_get_unit_details_unknown_service(self):
        """Should return default details for non-existent service."""
        adapter = MockSystemdAdapter()
        details = await adapter.get_unit_details("nonexistent.service")
        assert details["active"] == "unknown"
        assert details["sub"] == "unknown"

    @pytest.mark.asyncio
    async def test_get_unit_details_existing_service(self):
        """Should return correct details for existing service."""
        adapter = MockSystemdAdapter()
        adapter.add_service("test.service", active="active", sub="running", enabled="enabled", desc="Test service")
        details = await adapter.get_unit_details("test.service")
        assert details["active"] == "active"
        assert details["sub"] == "running"
        assert details["enabled"] == "enabled"
        assert details["desc"] == "Test service"

    @pytest.mark.asyncio
    async def test_manage_service_start(self):
        """Should simulate starting a service."""
        adapter = MockSystemdAdapter()
        adapter.add_service("test.service", active="inactive", sub="dead")

        result = await adapter.manage_service("test.service", "start")
        assert result["ok"] is True
        assert result["action"] == "start"

        status = await adapter.get_unit_status("test.service")
        assert status == "active"

    @pytest.mark.asyncio
    async def test_manage_service_stop(self):
        """Should simulate stopping a service."""
        adapter = MockSystemdAdapter()
        adapter.add_service("test.service", active="active", sub="running")

        result = await adapter.manage_service("test.service", "stop")
        assert result["ok"] is True
        assert result["action"] == "stop"

        status = await adapter.get_unit_status("test.service")
        assert status == "inactive"

    @pytest.mark.asyncio
    async def test_manage_service_restart(self):
        """Should simulate restarting a service."""
        adapter = MockSystemdAdapter()
        adapter.add_service("test.service", active="active", sub="running")

        result = await adapter.manage_service("test.service", "restart")
        assert result["ok"] is True
        assert result["action"] == "restart"

        status = await adapter.get_unit_status("test.service")
        assert status == "active"

    @pytest.mark.asyncio
    async def test_manage_service_enable(self):
        """Should simulate enabling a service."""
        adapter = MockSystemdAdapter()
        adapter.add_service("test.service", enabled="disabled")

        result = await adapter.manage_service("test.service", "enable")
        assert result["ok"] is True

        details = await adapter.get_unit_details("test.service")
        assert details["enabled"] == "enabled"

    @pytest.mark.asyncio
    async def test_manage_service_disable(self):
        """Should simulate disabling a service."""
        adapter = MockSystemdAdapter()
        adapter.add_service("test.service", enabled="enabled")

        result = await adapter.manage_service("test.service", "disable")
        assert result["ok"] is True

        details = await adapter.get_unit_details("test.service")
        assert details["enabled"] == "disabled"

    @pytest.mark.asyncio
    async def test_manage_service_invalid_action(self):
        """Should return error for invalid action."""
        adapter = MockSystemdAdapter()
        adapter.add_service("test.service")

        result = await adapter.manage_service("test.service", "invalid")
        assert result["ok"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_manage_service_not_found(self):
        """Should return error for non-existent service."""
        adapter = MockSystemdAdapter()

        result = await adapter.manage_service("nonexistent.service", "start")
        assert result["ok"] is False
        assert "not found" in result["error"]

    def test_available_property(self):
        """Mock adapter should always report as available."""
        adapter = MockSystemdAdapter()
        assert adapter.available is True


class TestSystemdAdapter:
    """Tests for SystemdAdapter with mocked subprocess."""

    @patch("pc_client.adapters.systemd_adapter.is_systemd_available")
    def test_adapter_unavailable_when_systemd_not_present(self, mock_available):
        """Adapter should be unavailable when systemd is not present."""
        mock_available.return_value = False
        adapter = SystemdAdapter()
        assert adapter.available is False

    @patch("pc_client.adapters.systemd_adapter.is_systemd_available")
    @pytest.mark.asyncio
    async def test_get_unit_status_when_unavailable(self, mock_available):
        """Should return 'unknown' when systemd unavailable."""
        mock_available.return_value = False
        adapter = SystemdAdapter()
        status = await adapter.get_unit_status("test.service")
        assert status == "unknown"

    @patch("pc_client.adapters.systemd_adapter.is_systemd_available")
    @pytest.mark.asyncio
    async def test_get_unit_details_when_unavailable(self, mock_available):
        """Should return default details when systemd unavailable."""
        mock_available.return_value = False
        adapter = SystemdAdapter()
        details = await adapter.get_unit_details("test.service")
        assert details["active"] == "unknown"

    @patch("pc_client.adapters.systemd_adapter.is_systemd_available")
    @pytest.mark.asyncio
    async def test_manage_service_when_unavailable(self, mock_available):
        """Should return error when systemd unavailable."""
        mock_available.return_value = False
        adapter = SystemdAdapter()
        result = await adapter.manage_service("test.service", "start")
        assert result["ok"] is False
        assert "not available" in result["error"]

    @patch("pc_client.adapters.systemd_adapter.is_systemd_available")
    @patch("pc_client.adapters.systemd_adapter.asyncio.create_subprocess_exec")
    @pytest.mark.asyncio
    async def test_get_unit_status_parses_active(self, mock_subprocess, mock_available):
        """Should correctly parse 'active' status."""
        mock_available.return_value = True
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"active", b""))
        mock_subprocess.return_value = mock_process

        adapter = SystemdAdapter()
        status = await adapter.get_unit_status("test.service")
        assert status == "active"

    @patch("pc_client.adapters.systemd_adapter.is_systemd_available")
    @patch("pc_client.adapters.systemd_adapter.asyncio.create_subprocess_exec")
    @pytest.mark.asyncio
    async def test_get_unit_status_parses_inactive(self, mock_subprocess, mock_available):
        """Should correctly parse 'inactive' status."""
        mock_available.return_value = True
        mock_process = AsyncMock()
        mock_process.returncode = 3
        mock_process.communicate = AsyncMock(return_value=(b"inactive", b""))
        mock_subprocess.return_value = mock_process

        adapter = SystemdAdapter()
        status = await adapter.get_unit_status("test.service")
        assert status == "inactive"

    @patch("pc_client.adapters.systemd_adapter.is_systemd_available")
    @patch("pc_client.adapters.systemd_adapter.asyncio.create_subprocess_exec")
    @pytest.mark.asyncio
    async def test_get_unit_status_parses_failed(self, mock_subprocess, mock_available):
        """Should correctly parse 'failed' status."""
        mock_available.return_value = True
        mock_process = AsyncMock()
        mock_process.returncode = 3
        mock_process.communicate = AsyncMock(return_value=(b"failed", b""))
        mock_subprocess.return_value = mock_process

        adapter = SystemdAdapter()
        status = await adapter.get_unit_status("test.service")
        assert status == "failed"

    @patch("pc_client.adapters.systemd_adapter.is_systemd_available")
    @patch("pc_client.adapters.systemd_adapter.asyncio.create_subprocess_exec")
    @pytest.mark.asyncio
    async def test_get_unit_details_parses_properties(self, mock_subprocess, mock_available):
        """Should correctly parse systemctl show output."""
        mock_available.return_value = True
        mock_process = AsyncMock()
        mock_process.returncode = 0
        output = b"ActiveState=active\nSubState=running\nDescription=Test Service\nUnitFileState=enabled"
        mock_process.communicate = AsyncMock(return_value=(output, b""))
        mock_subprocess.return_value = mock_process

        adapter = SystemdAdapter()
        details = await adapter.get_unit_details("test.service")
        assert details["active"] == "active"
        assert details["sub"] == "running"
        assert details["enabled"] == "enabled"
        assert details["desc"] == "Test Service"

    @patch("pc_client.adapters.systemd_adapter.is_systemd_available")
    @patch("pc_client.adapters.systemd_adapter.asyncio.create_subprocess_exec")
    @pytest.mark.asyncio
    async def test_manage_service_success(self, mock_subprocess, mock_available):
        """Should return success when systemctl command succeeds."""
        mock_available.return_value = True
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"", b""))
        mock_subprocess.return_value = mock_process

        adapter = SystemdAdapter()
        result = await adapter.manage_service("test.service", "start")
        assert result["ok"] is True
        assert result["action"] == "start"

    @patch("pc_client.adapters.systemd_adapter.is_systemd_available")
    @patch("pc_client.adapters.systemd_adapter.asyncio.create_subprocess_exec")
    @pytest.mark.asyncio
    async def test_manage_service_permission_denied(self, mock_subprocess, mock_available):
        """Should return permission error message."""
        mock_available.return_value = True
        mock_process = AsyncMock()
        mock_process.returncode = 1
        mock_process.communicate = AsyncMock(return_value=(b"", b"permission denied"))
        mock_subprocess.return_value = mock_process

        adapter = SystemdAdapter()
        result = await adapter.manage_service("test.service", "start")
        assert result["ok"] is False
        assert "Permission denied" in result["error"]

    @patch("pc_client.adapters.systemd_adapter.is_systemd_available")
    @pytest.mark.asyncio
    async def test_manage_service_invalid_action(self, mock_available):
        """Should return error for invalid action."""
        mock_available.return_value = True
        adapter = SystemdAdapter()
        result = await adapter.manage_service("test.service", "invalid_action")
        assert result["ok"] is False
        assert "Invalid action" in result["error"]

    @patch("pc_client.adapters.systemd_adapter.is_systemd_available")
    @patch("pc_client.adapters.systemd_adapter.asyncio.create_subprocess_exec")
    @pytest.mark.asyncio
    async def test_manage_service_uses_sudo_by_default(self, mock_subprocess, mock_available):
        """Should use sudo by default for manage_service."""
        mock_available.return_value = True
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"", b""))
        mock_subprocess.return_value = mock_process

        adapter = SystemdAdapter(use_sudo=True)
        await adapter.manage_service("test.service", "start")

        # Check that sudo was used
        call_args = mock_subprocess.call_args[0]
        assert call_args[0] == "sudo"

    @patch("pc_client.adapters.systemd_adapter.is_systemd_available")
    @patch("pc_client.adapters.systemd_adapter.asyncio.create_subprocess_exec")
    @pytest.mark.asyncio
    async def test_manage_service_without_sudo(self, mock_subprocess, mock_available):
        """Should not use sudo when use_sudo=False."""
        mock_available.return_value = True
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"", b""))
        mock_subprocess.return_value = mock_process

        adapter = SystemdAdapter(use_sudo=False)
        await adapter.manage_service("test.service", "start")

        # Check that sudo was not used
        call_args = mock_subprocess.call_args[0]
        assert call_args[0] == "systemctl"
