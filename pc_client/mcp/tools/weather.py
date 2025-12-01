"""Weather tools for MCP.

Narzędzie do pobierania prognozy pogody.
Uwaga: W pełnej implementacji wymaga klucza API OpenWeather.
"""

import threading
import time
from typing import Optional

from pc_client.mcp.registry import mcp_tool


# Thread-safe cache dla prognozy pogody
_weather_cache: dict = {
    "data": None,
    "timestamp": 0,
}
_weather_cache_lock = threading.Lock()

# Domyślny czas cache (5 minut)
DEFAULT_CACHE_TTL = 300


def _get_mock_weather() -> dict:
    """Zwróć mock danych pogodowych (dla trybu bez API)."""
    return {
        "location": "Warszawa, PL",
        "temperature": 12.5,
        "feels_like": 10.2,
        "humidity": 65,
        "description": "Częściowe zachmurzenie",
        "wind_speed": 15,
        "source": "mock",
    }


@mcp_tool(
    name="weather.get_summary",
    description="Pobiera krótką prognozę pogody dla lokalizacji Rider-PC.",
    args_schema={
        "type": "object",
        "properties": {
            "location": {
                "type": "string",
                "description": "Lokalizacja (miasto, kraj). Domyślnie: Warszawa, PL.",
            },
            "use_cache": {
                "type": "boolean",
                "description": "Czy używać cache. Domyślnie: true.",
            },
        },
        "required": [],
    },
    permissions=["low"],
)
def get_weather_summary(
    location: Optional[str] = None,
    use_cache: bool = True,
) -> dict:
    """Pobierz krótką prognozę pogody.

    Args:
        location: Lokalizacja (miasto, kraj). Domyślnie Warszawa.
        use_cache: Czy używać cache.

    Returns:
        Słownik z danymi pogodowymi.

    Note:
        W pełnej implementacji wymaga skonfigurowanego klucza API OpenWeather
        w zmiennej środowiskowej OPENWEATHER_API_KEY.
    """
    current_time = time.time()

    with _weather_cache_lock:
        # Sprawdź cache
        if use_cache and _weather_cache["data"]:
            cache_age = current_time - _weather_cache["timestamp"]
            if cache_age < DEFAULT_CACHE_TTL:
                return {
                    **_weather_cache["data"],
                    "cached": True,
                    "cache_age_seconds": int(cache_age),
                }

        # W trybie mock zwróć dane symulowane
        # W pełnej implementacji tutaj byłoby zapytanie do OpenWeather API
        weather_data = _get_mock_weather()
        if location:
            weather_data["location"] = location

        # Zapisz do cache
        _weather_cache["data"] = weather_data
        _weather_cache["timestamp"] = current_time

        return {
            **weather_data,
            "cached": False,
            "cache_age_seconds": 0,
    }
