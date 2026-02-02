"""Robot tools for MCP.

Narzędzia do zarządzania robotem: status, ruch.
"""

import threading
from typing import Literal, TypedDict

from pc_client.mcp.registry import mcp_tool


# Thread-safe symulowany stan robota (w rzeczywistości pobierany z Rider-PI)
class RobotPosition(TypedDict):
    x: float
    y: float
    theta: float


class RobotState(TypedDict):
    connected: bool
    battery: int
    mode: str
    position: RobotPosition


RobotStatusResponse = RobotState


class RobotCommandResponse(TypedDict):
    executed: bool
    command: str
    speed: float
    mode: str


_robot_state: RobotState = {
    "connected": True,
    "battery": 85,
    "mode": "idle",
    "position": {"x": 0.0, "y": 0.0, "theta": 0.0},
}
_robot_state_lock = threading.Lock()


@mcp_tool(
    name="robot.status",
    description="Odczytuje aktualny stan robota (połączenie, bateria, tryb).",
    args_schema={"type": "object", "properties": {}, "required": []},
    permissions=["low"],
)
def get_robot_status() -> RobotStatusResponse:
    """Zwróć status robota.

    Returns:
        Słownik z informacjami o stanie robota.
    """
    with _robot_state_lock:
        position_snapshot: RobotPosition = {
            "x": _robot_state["position"]["x"],
            "y": _robot_state["position"]["y"],
            "theta": _robot_state["position"]["theta"],
        }
        status: RobotStatusResponse = {
            "connected": _robot_state["connected"],
            "battery": _robot_state["battery"],
            "mode": _robot_state["mode"],
            "position": position_snapshot,
        }
        return status


VALID_COMMANDS: list[str] = ["forward", "backward", "left", "right", "stop"]


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
) -> RobotCommandResponse:
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

    # Symulacja wykonania komendy z thread-safe aktualizacją stanu
    with _robot_state_lock:
        _robot_state["mode"] = "moving" if command != "stop" else "idle"
        current_mode: str = _robot_state["mode"]

    result: RobotCommandResponse = {
        "executed": True,
        "command": command,
        "speed": speed,
        "mode": current_mode,
    }
    return result
