"""Weather tools for MCP.

Narzędzie do pobierania prognozy pogody z OpenWeather API.
Wymaga klucza API w zmiennej środowiskowej OPENWEATHER_API_KEY.
"""

import logging
import threading
import time
from typing import NotRequired, Optional, Required, TypedDict

from pc_client.mcp.registry import mcp_tool

logger = logging.getLogger(__name__)


# Thread-safe cache dla prognozy pogody
class WeatherData(TypedDict, total=False):
    location: Required[str]
    description: Required[str]
    source: Required[str]
    temperature: NotRequired[Optional[float]]
    feels_like: NotRequired[Optional[float]]
    humidity: NotRequired[Optional[int]]
    wind_speed: NotRequired[Optional[float]]
    pressure: NotRequired[Optional[int]]
    clouds: NotRequired[Optional[int]]
    visibility: NotRequired[Optional[int]]
    api_error: NotRequired[str]


class WeatherSummary(WeatherData, total=False):
    cached: bool
    cache_age_seconds: int


class WeatherCacheEntry(TypedDict):
    data: Optional[WeatherData]
    timestamp: float
    location: Optional[str]


_weather_cache: WeatherCacheEntry = {
    "data": None,
    "timestamp": 0,
    "location": None,
}
_weather_cache_lock = threading.Lock()


def _get_settings():
    """Lazy import settings to avoid circular imports."""
    from pc_client.config.settings import settings

    return settings


def _get_mock_weather(location: str) -> WeatherData:
    """Zwróć mock danych pogodowych (dla trybu bez API)."""
    return {
        "location": location,
        "temperature": 12.5,
        "feels_like": 10.2,
        "humidity": 65,
        "description": "Częściowe zachmurzenie",
        "wind_speed": 15,
        "pressure": 1013,
        "source": "mock",
    }


def _fetch_openweather_data(api_key: str, location: str) -> WeatherData:
    """Pobierz dane pogodowe z OpenWeather API.

    Args:
        api_key: Klucz API OpenWeather.
        location: Lokalizacja w formacie "miasto,kod_kraju" (np. "Warsaw,PL").

    Returns:
        Słownik z danymi pogodowymi.

    Raises:
        Exception: Jeśli nie udało się pobrać danych.
    """
    import urllib.request
    import urllib.error
    import urllib.parse
    import json

    # Buduj URL API z poprawnym URL encoding
    # UWAGA: Nie loguj pełnego URL, ponieważ zawiera klucz API!
    base_url = "https://api.openweathermap.org/data/2.5/weather"
    params = urllib.parse.urlencode({"q": location, "appid": api_key, "units": "metric", "lang": "pl"})
    url = f"{base_url}?{params}"

    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))

        # Parsuj odpowiedź API
        return {
            "location": f"{data.get('name', location)}, {data.get('sys', {}).get('country', '')}",
            "temperature": data.get("main", {}).get("temp"),
            "feels_like": data.get("main", {}).get("feels_like"),
            "humidity": data.get("main", {}).get("humidity"),
            "pressure": data.get("main", {}).get("pressure"),
            "description": data.get("weather", [{}])[0].get("description", ""),
            "wind_speed": data.get("wind", {}).get("speed"),
            "clouds": data.get("clouds", {}).get("all"),
            "visibility": data.get("visibility"),
            "source": "openweather",
        }

    except urllib.error.HTTPError as e:
        logger.error("OpenWeather API HTTP error: %s", e.code)
        if e.code == 401:
            raise Exception("Invalid OpenWeather API key")
        elif e.code == 404:
            raise Exception(f"Location not found: {location}")
        else:
            raise Exception(f"OpenWeather API error: HTTP {e.code}")
    except urllib.error.URLError as e:
        logger.error("OpenWeather API connection error: %s", e.reason)
        raise Exception(f"Failed to connect to OpenWeather API: {e.reason}")
    except json.JSONDecodeError as e:
        logger.error("OpenWeather API response parse error: %s", e)
        raise Exception("Invalid response from OpenWeather API")


@mcp_tool(
    name="weather.get_summary",
    description="Pobiera krótką prognozę pogody dla lokalizacji Rider-PC.",
    args_schema={
        "type": "object",
        "properties": {
            "location": {
                "type": "string",
                "description": "Lokalizacja (miasto,kod_kraju). Domyślnie: Warsaw,PL.",
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
) -> WeatherSummary:
    """Pobierz krótką prognozę pogody.

    Args:
        location: Lokalizacja (miasto,kod_kraju). Domyślnie z konfiguracji.
        use_cache: Czy używać cache.

    Returns:
        Słownik z danymi pogodowymi.

    Note:
        Wymaga skonfigurowanego klucza API OpenWeather w zmiennej
        środowiskowej OPENWEATHER_API_KEY. Bez klucza zwraca dane mock.
    """
    settings = _get_settings()
    current_time = time.time()
    cache_ttl = settings.weather_cache_ttl_seconds

    # Domyślna lokalizacja z konfiguracji
    if not location:
        location = settings.weather_default_location

    with _weather_cache_lock:
        cached_data = _weather_cache["data"]
        # Sprawdź cache
        if use_cache and cached_data and _weather_cache["location"] == location:
            cache_age = current_time - _weather_cache["timestamp"]
            if cache_age < cache_ttl:
                cached_result: WeatherSummary = {
                    **cached_data,
                    "cached": True,
                    "cache_age_seconds": int(cache_age),
                }
                return cached_result

        # Sprawdź czy mamy klucz API
        api_key = settings.openweather_api_key
        if api_key:
            try:
                weather_data = _fetch_openweather_data(api_key, location)
                logger.info("Fetched weather data from OpenWeather API for %s", location)
            except Exception as e:
                logger.warning("OpenWeather API failed, using mock data: %s", e)
                weather_data = _get_mock_weather(location)
                weather_data["api_error"] = str(e)
        else:
            # Brak klucza API - użyj mock
            logger.debug("No OpenWeather API key configured, using mock data")
            weather_data = _get_mock_weather(location)

        # Zapisz do cache
        _weather_cache["data"] = weather_data
        _weather_cache["timestamp"] = current_time
        _weather_cache["location"] = location

        summary: WeatherSummary = {
            **weather_data,
            "cached": False,
            "cache_age_seconds": 0,
        }
        return summary
