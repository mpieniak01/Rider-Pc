"""System tools for MCP.

Narzędzia systemowe: czas, status systemu.
"""

from datetime import datetime, timezone
import platform
import os
from typing import Optional, TypedDict

from pc_client.mcp.registry import mcp_tool


class SystemTimeResponse(TypedDict):
    time: str
    timezone: str
    timestamp: int


class SystemStatusResponse(TypedDict):
    platform: str
    platform_release: str
    hostname: str
    python_version: str
    cpu_count: Optional[int]


@mcp_tool(
    name="system.get_time",
    description="Zwraca aktualny czas gospodarza Rider-PC w formacie ISO 8601 ze strefą czasową.",
    args_schema={"type": "object", "properties": {}, "required": []},
    permissions=["low"],
)
def get_time() -> SystemTimeResponse:
    """Zwróć aktualny czas systemowy.

    Returns:
        Słownik z czasem w formacie ISO 8601 i informacją o strefie czasowej.
    """
    now = datetime.now(timezone.utc).astimezone()
    response: SystemTimeResponse = {
        "time": now.isoformat(),
        "timezone": str(now.tzinfo),
        "timestamp": int(now.timestamp()),
    }
    return response


@mcp_tool(
    name="system.get_status",
    description="Zwraca podstawowy status systemu Rider-PC.",
    args_schema={"type": "object", "properties": {}, "required": []},
    permissions=["low"],
)
def get_system_status() -> SystemStatusResponse:
    """Zwróć status systemu.

    Returns:
        Słownik z informacjami o systemie.
    """
    response: SystemStatusResponse = {
        "platform": platform.system(),
        "platform_release": platform.release(),
        "hostname": platform.node(),
        "python_version": platform.python_version(),
        "cpu_count": os.cpu_count(),
    }
    return response
