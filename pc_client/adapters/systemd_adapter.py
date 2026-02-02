"""Local system adapter for systemd service management.

This module provides async wrappers for systemctl commands to manage
systemd services. It's designed to work within the FastAPI async environment.
"""

import asyncio
import logging
import platform
import shutil
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)


def is_systemd_available() -> bool:
    """
    Check if the system supports systemd.

    Returns:
        True if running on Linux with systemd, False otherwise.
    """
    if platform.system() != "Linux":
        logger.debug("Systemd not available: not running on Linux (platform=%s)", platform.system())
        return False

    # Check if systemctl binary exists
    if shutil.which("systemctl") is None:
        logger.debug("Systemd not available: systemctl binary not found")
        return False

    return True


class SystemdAdapter:
    """
    Async adapter for systemd service management.

    This adapter executes systemctl commands asynchronously to avoid
    blocking the FastAPI event loop during service operations.
    """

    def __init__(self, use_sudo: bool = True):
        """
        Initialize the SystemdAdapter.

        Args:
            use_sudo: Whether to prefix commands with sudo for privileged operations.
                     Defaults to True. Set to False if running as root.
        """
        self._use_sudo = use_sudo
        self._available = is_systemd_available()

    @property
    def available(self) -> bool:
        """Return whether systemd is available on this system."""
        return self._available

    async def _run_command(self, *args: str, check: bool = False) -> Tuple[Optional[int], str, str]:
        """
        Run an async subprocess command.

        Args:
            *args: Command and arguments to execute.
            check: If True, raise exception on non-zero return code.

        Returns:
            Tuple of (return_code, stdout, stderr).
        """
        try:
            process = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()
            stdout_str = stdout.decode("utf-8", errors="replace").strip()
            stderr_str = stderr.decode("utf-8", errors="replace").strip()

            if check and process.returncode != 0:
                logger.error(
                    "Command failed: %s (rc=%d, stderr=%s)",
                    " ".join(args),
                    process.returncode,
                    stderr_str,
                )

            return process.returncode, stdout_str, stderr_str
        except Exception as e:
            logger.error("Failed to execute command %s: %s", " ".join(args), e)
            return -1, "", str(e)

    @staticmethod
    def _normalize_returncode(returncode: Optional[int]) -> int:
        """Normalize subprocess return codes (None -> -1)."""
        return returncode if returncode is not None else -1

    async def get_unit_status(self, unit: str) -> str:
        """
        Get the active status of a systemd unit.

        Args:
            unit: The systemd unit name (e.g., 'rider-task-queue.service').

        Returns:
            Status string: 'active', 'inactive', 'failed', or 'unknown'.
        """
        if not self._available:
            return "unknown"

        # systemctl is-active doesn't require sudo
        returncode, stdout, _ = await self._run_command("systemctl", "is-active", unit)
        sanitized_rc = self._normalize_returncode(returncode)

        # Normalize output - prioritize stdout content when valid
        status = stdout.lower().strip()

        # Check for valid status strings first
        valid_statuses = ("active", "inactive", "failed", "activating", "deactivating")
        if status in valid_statuses:
            return status

        # If stdout didn't give a valid status, interpret return codes
        # Return code 4 means no such unit
        if sanitized_rc == 4:
            return "unknown"
        # Return code 3 typically means inactive/dead when stdout is empty
        if sanitized_rc == 3:
            return "inactive"

        return status or "unknown"

    async def get_unit_details(self, unit: str) -> Dict[str, Any]:
        """
        Get detailed status information for a systemd unit.

        Args:
            unit: The systemd unit name.

        Returns:
            Dictionary with unit details including active state, sub-state,
            description, and enabled status.
        """
        if not self._available:
            return {
                "active": "unknown",
                "sub": "unknown",
                "enabled": "unknown",
                "desc": "",
            }

        # Use systemctl show to get structured data
        returncode, stdout, stderr = await self._run_command(
            "systemctl",
            "show",
            unit,
            "--property=ActiveState,SubState,Description,UnitFileState",
            "--no-pager",
        )

        sanitized_rc = self._normalize_returncode(returncode)

        if sanitized_rc != 0:
            logger.warning("Failed to get unit details for %s: %s", unit, stderr)
            return {
                "active": "unknown",
                "sub": "unknown",
                "enabled": "unknown",
                "desc": "",
            }

        # Parse key=value output
        details: Dict[str, str] = {}
        for line in stdout.split("\n"):
            if "=" in line:
                key, value = line.split("=", 1)
                details[key.strip()] = value.strip()

        return {
            "active": details.get("ActiveState", "unknown"),
            "sub": details.get("SubState", "unknown"),
            "enabled": details.get("UnitFileState", "unknown"),
            "desc": details.get("Description", ""),
        }

    async def manage_service(self, unit: str, action: str) -> Dict[str, Any]:
        """
        Manage a systemd service (start/stop/restart/enable/disable).

        Args:
            unit: The systemd unit name.
            action: The action to perform (start, stop, restart, enable, disable).

        Returns:
            Dictionary with 'ok' boolean, 'unit', 'action', and optionally 'error'.
        """
        if not self._available:
            return {
                "ok": False,
                "unit": unit,
                "action": action,
                "error": "Systemd not available on this system",
            }

        # Validate unit name to prevent command injection
        if not unit or any(c in unit for c in [';', '&', '|', '`', '$', '\n', '\r']):
            return {
                "ok": False,
                "unit": unit,
                "action": action,
                "error": "Invalid unit name",
            }

        valid_actions = {"start", "stop", "restart", "enable", "disable"}
        if action not in valid_actions:
            return {
                "ok": False,
                "unit": unit,
                "action": action,
                "error": f"Invalid action '{action}'. Valid actions: {', '.join(valid_actions)}",
            }

        # Build command with optional sudo
        cmd = ["sudo", "systemctl", action, unit] if self._use_sudo else ["systemctl", action, unit]

        returncode, stdout, stderr = await self._run_command(*cmd)
        sanitized_rc = self._normalize_returncode(returncode)

        if sanitized_rc != 0:
            error_msg = stderr or stdout or f"systemctl {action} {unit} failed with return code {sanitized_rc}"
            # Check for common permission errors
            if "permission denied" in error_msg.lower() or "authentication required" in error_msg.lower():
                error_msg = (
                    f"Permission denied. Ensure the user has passwordless sudo access "
                    f"for 'systemctl {action} {unit}'. See documentation for sudoers configuration."
                )
            logger.error("Failed to %s service %s: %s", action, unit, error_msg)
            return {
                "ok": False,
                "unit": unit,
                "action": action,
                "error": error_msg,
            }

        logger.info("Successfully executed %s on service %s", action, unit)
        return {
            "ok": True,
            "unit": unit,
            "action": action,
        }


class MockSystemdAdapter:
    """
    Mock adapter for testing and non-Linux environments.

    Simulates systemd behavior without executing real commands.
    """

    def __init__(self, services: Optional[Dict[str, Dict[str, Any]]] = None):
        """
        Initialize the mock adapter.

        Args:
            services: Optional dictionary mapping unit names to their state.
        """
        self._services: Dict[str, Dict[str, Any]] = services or {}
        self._available = True  # Mock is always "available" for testing

    @property
    def available(self) -> bool:
        """Return True as mock is always available."""
        return self._available

    def add_service(
        self, unit: str, active: str = "active", sub: str = "running", enabled: str = "enabled", desc: str = ""
    ) -> None:
        """Add a mock service to the adapter."""
        self._services[unit] = {
            "active": active,
            "sub": sub,
            "enabled": enabled,
            "desc": desc,
        }

    async def get_unit_status(self, unit: str) -> str:
        """Get the mock status of a unit."""
        if unit in self._services:
            return self._services[unit].get("active", "unknown")
        return "unknown"

    async def get_unit_details(self, unit: str) -> Dict[str, Any]:
        """Get mock details for a unit."""
        if unit in self._services:
            return dict(self._services[unit])
        return {
            "active": "unknown",
            "sub": "unknown",
            "enabled": "unknown",
            "desc": "",
        }

    async def manage_service(self, unit: str, action: str) -> Dict[str, Any]:
        """Manage a mock service."""
        valid_actions = {"start", "stop", "restart", "enable", "disable"}
        if action not in valid_actions:
            return {
                "ok": False,
                "unit": unit,
                "action": action,
                "error": f"Invalid action '{action}'",
            }

        if unit not in self._services:
            return {
                "ok": False,
                "unit": unit,
                "action": action,
                "error": f"Service {unit} not found",
            }

        # Simulate state changes
        if action == "start":
            self._services[unit]["active"] = "active"
            self._services[unit]["sub"] = "running"
        elif action == "stop":
            self._services[unit]["active"] = "inactive"
            self._services[unit]["sub"] = "dead"
        elif action == "restart":
            self._services[unit]["active"] = "active"
            self._services[unit]["sub"] = "running"
        elif action == "enable":
            self._services[unit]["enabled"] = "enabled"
        elif action == "disable":
            self._services[unit]["enabled"] = "disabled"

        return {"ok": True, "unit": unit, "action": action}
