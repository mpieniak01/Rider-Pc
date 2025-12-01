"""Robot tools for MCP.

Narzędzia do zarządzania robotem: status, ruch.
"""

from typing import Literal

from pc_client.mcp.registry import mcp_tool


# Symulowany stan robota (w rzeczywistości pobierany z Rider-PI)
_robot_state = {
    "connected": True,
    "battery": 85,
    "mode": "idle",
    "position": {"x": 0.0, "y": 0.0, "theta": 0.0},
}


@mcp_tool(
    name="robot.status",
    description="Odczytuje aktualny stan robota (połączenie, bateria, tryb).",
    args_schema={"type": "object", "properties": {}, "required": []},
    permissions=["low"],
)
def get_robot_status() -> dict:
    """Zwróć status robota.

    Returns:
        Słownik z informacjami o stanie robota.
    """
    return {
        "connected": _robot_state["connected"],
        "battery": _robot_state["battery"],
        "mode": _robot_state["mode"],
        "position": _robot_state["position"],
    }


VALID_COMMANDS = ["forward", "backward", "left", "right", "stop"]


@mcp_tool(
    name="robot.move",
    description="Wysyła komendę ruchu do robota. Obsługiwane komendy: forward, backward, left, right, stop.",
    args_schema={
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "enum": VALID_COMMANDS,
                "description": "Komenda ruchu do wykonania.",
            },
            "speed": {
                "type": "number",
                "minimum": 0,
                "maximum": 100,
                "description": "Prędkość ruchu (0-100, domyślnie 50).",
            },
        },
        "required": ["command"],
    },
    permissions=["high", "confirm"],
)
def robot_move(
    command: Literal["forward", "backward", "left", "right", "stop"],
    speed: float = 50.0,
) -> dict:
    """Wykonaj komendę ruchu robota.

    Args:
        command: Komenda ruchu (forward, backward, left, right, stop).
        speed: Prędkość ruchu 0-100.

    Returns:
        Słownik z potwierdzeniem wykonania komendy.

    Raises:
        ValueError: Jeśli komenda jest nieprawidłowa.
    """
    if command not in VALID_COMMANDS:
        raise ValueError(f"Invalid command: {command}. Must be one of: {VALID_COMMANDS}")

    if not 0 <= speed <= 100:
        raise ValueError(f"Speed must be between 0 and 100, got: {speed}")

    # Symulacja wykonania komendy
    _robot_state["mode"] = "moving" if command != "stop" else "idle"

    return {
        "executed": True,
        "command": command,
        "speed": speed,
        "mode": _robot_state["mode"],
    }
