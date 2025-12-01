"""System tools for MCP.

Narzędzia systemowe: czas, status systemu.
"""

from datetime import datetime, timezone
import platform
import os

from pc_client.mcp.registry import mcp_tool


@mcp_tool(
    name="system.get_time",
    description="Zwraca aktualny czas gospodarza Rider-PC w formacie ISO 8601 ze strefą czasową.",
    args_schema={"type": "object", "properties": {}, "required": []},
    permissions=["low"],
)
def get_time() -> dict:
    """Zwróć aktualny czas systemowy.

    Returns:
        Słownik z czasem w formacie ISO 8601 i informacją o strefie czasowej.
    """
    now = datetime.now(timezone.utc).astimezone()
    return {
        "time": now.isoformat(),
        "timezone": str(now.tzinfo),
        "timestamp": int(now.timestamp()),
    }


@mcp_tool(
    name="system.get_status",
    description="Zwraca podstawowy status systemu Rider-PC.",
    args_schema={"type": "object", "properties": {}, "required": []},
    permissions=["low"],
)
def get_system_status() -> dict:
    """Zwróć status systemu.

    Returns:
        Słownik z informacjami o systemie.
    """
    return {
        "platform": platform.system(),
        "platform_release": platform.release(),
        "hostname": platform.node(),
        "python_version": platform.python_version(),
        "cpu_count": os.cpu_count(),
    }
