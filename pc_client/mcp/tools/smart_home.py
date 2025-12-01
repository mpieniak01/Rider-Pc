"""Smart Home tools for MCP.

Narzędzia do zarządzania urządzeniami smart home: światła, sceny.
"""

import threading
from typing import Optional

from pc_client.mcp.registry import mcp_tool


# Thread-safe symulowany stan urządzeń smart home
_smart_home_state = {
    "lights": {
        "living_room": {"on": True, "brightness": 80, "color": "#FFFFFF"},
        "bedroom": {"on": False, "brightness": 50, "color": "#FFCC00"},
        "kitchen": {"on": True, "brightness": 100, "color": "#FFFFFF"},
        "bathroom": {"on": False, "brightness": 70, "color": "#FFFFFF"},
    },
    "scenes": {
        "morning": {"lights": {"living_room": True, "kitchen": True}},
        "evening": {"lights": {"living_room": True, "bedroom": True}, "brightness": 60},
        "night": {"lights": {}},
        "movie": {"lights": {"living_room": True}, "brightness": 20},
    },
    "active_scene": None,
}
_smart_home_lock = threading.Lock()


@mcp_tool(
    name="smart_home.toggle_light",
    description="Włącza lub wyłącza światło w danym pomieszczeniu.",
    args_schema={
        "type": "object",
        "properties": {
            "room": {
                "type": "string",
                "enum": ["living_room", "bedroom", "kitchen", "bathroom"],
                "description": "Nazwa pomieszczenia.",
            },
            "state": {
                "type": "boolean",
                "description": "True = włącz, False = wyłącz.",
            },
        },
        "required": ["room", "state"],
    },
    permissions=["low"],
)
def toggle_light(room: str, state: bool) -> dict:
    """Przełącz światło w pomieszczeniu.

    Args:
        room: Nazwa pomieszczenia.
        state: True = włącz, False = wyłącz.

    Returns:
        Słownik z potwierdzeniem operacji.

    Raises:
        ValueError: Jeśli pomieszczenie nie istnieje.
    """
    with _smart_home_lock:
        if room not in _smart_home_state["lights"]:
            raise ValueError(f"Unknown room: {room}")

        _smart_home_state["lights"][room]["on"] = state

        return {
            "room": room,
            "light_on": state,
            "brightness": _smart_home_state["lights"][room]["brightness"],
        }


@mcp_tool(
    name="smart_home.set_brightness",
    description="Ustawia jasność światła w danym pomieszczeniu.",
    args_schema={
        "type": "object",
        "properties": {
            "room": {
                "type": "string",
                "enum": ["living_room", "bedroom", "kitchen", "bathroom"],
                "description": "Nazwa pomieszczenia.",
            },
            "brightness": {
                "type": "integer",
                "minimum": 0,
                "maximum": 100,
                "description": "Jasność (0-100).",
            },
        },
        "required": ["room", "brightness"],
    },
    permissions=["low"],
)
def set_brightness(room: str, brightness: int) -> dict:
    """Ustaw jasność światła.

    Args:
        room: Nazwa pomieszczenia.
        brightness: Jasność 0-100.

    Returns:
        Słownik z potwierdzeniem operacji.

    Raises:
        ValueError: Jeśli pomieszczenie nie istnieje lub jasność poza zakresem.
    """
    with _smart_home_lock:
        if room not in _smart_home_state["lights"]:
            raise ValueError(f"Unknown room: {room}")
        if not 0 <= brightness <= 100:
            raise ValueError(f"Brightness must be 0-100, got: {brightness}")

        _smart_home_state["lights"][room]["brightness"] = brightness
        if brightness > 0:
            _smart_home_state["lights"][room]["on"] = True

        return {
            "room": room,
            "brightness": brightness,
            "light_on": _smart_home_state["lights"][room]["on"],
        }


@mcp_tool(
    name="smart_home.set_scene",
    description="Aktywuje scenę oświetleniową (np. 'morning', 'evening', 'night', 'movie').",
    args_schema={
        "type": "object",
        "properties": {
            "scene": {
                "type": "string",
                "enum": ["morning", "evening", "night", "movie"],
                "description": "Nazwa sceny do aktywacji.",
            },
        },
        "required": ["scene"],
    },
    permissions=["low"],
)
def set_scene(scene: str) -> dict:
    """Aktywuj scenę oświetleniową.

    Args:
        scene: Nazwa sceny.

    Returns:
        Słownik z potwierdzeniem aktywacji sceny.

    Raises:
        ValueError: Jeśli scena nie istnieje.
    """
    with _smart_home_lock:
        if scene not in _smart_home_state["scenes"]:
            raise ValueError(f"Unknown scene: {scene}")

        scene_config = _smart_home_state["scenes"][scene]
        affected_rooms = []

        for room_name in _smart_home_state["lights"]:
            _smart_home_state["lights"][room_name]["on"] = False

        if "lights" in scene_config:
            for room_name, should_be_on in scene_config["lights"].items():
                if room_name in _smart_home_state["lights"]:
                    _smart_home_state["lights"][room_name]["on"] = should_be_on
                    if should_be_on:
                        affected_rooms.append(room_name)

        if "brightness" in scene_config:
            for room_name in _smart_home_state["lights"]:
                _smart_home_state["lights"][room_name]["brightness"] = scene_config["brightness"]

        _smart_home_state["active_scene"] = scene

        return {
            "scene": scene,
            "activated": True,
            "affected_rooms": affected_rooms,
        }


@mcp_tool(
    name="smart_home.get_status",
    description="Zwraca aktualny stan wszystkich urządzeń smart home.",
    args_schema={
        "type": "object",
        "properties": {
            "room": {
                "type": "string",
                "description": "Opcjonalnie: nazwa konkretnego pomieszczenia.",
            },
        },
        "required": [],
    },
    permissions=["low"],
)
def get_smart_home_status(room: Optional[str] = None) -> dict:
    """Pobierz status urządzeń smart home.

    Args:
        room: Opcjonalnie nazwa konkretnego pomieszczenia.

    Returns:
        Słownik ze stanem urządzeń.
    """
    with _smart_home_lock:
        if room:
            if room not in _smart_home_state["lights"]:
                raise ValueError(f"Unknown room: {room}")
            return {
                "room": room,
                "light": _smart_home_state["lights"][room].copy(),
            }

        return {
            "lights": {k: v.copy() for k, v in _smart_home_state["lights"].items()},
            "active_scene": _smart_home_state["active_scene"],
            "available_scenes": list(_smart_home_state["scenes"].keys()),
        }
