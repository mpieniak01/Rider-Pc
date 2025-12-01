# 212 – Lokalny moduł MCP w Rider-PC

## Cel
Zapewnić wewnętrzny serwer MCP (Model Context Protocol) jako moduł FastAPI Rider-PC bez dodatkowych usług/portów. Umożliwi to lokalnemu Chat PC i przyszłym agentom korzystanie z jednolitego zestawu narzędzi (czas, status robotów, smart home, automatyzacje) bez pośredników.

## Zakres
1. **API MCP** – endpointy `POST /api/mcp/tools/invoke`, `GET /api/mcp/resources`, `GET /api/mcp/tools`.
2. **Rejestr narzędzi** – pythonowy katalog z opisami JSON-schema (wejście/wyjście) i oznaczeniem uprawnień.
3. **Integracja z TextProviderem** – obsługa tool-call (LLM -> MCP -> odpowiedź) w trybie Chat PC.
4. **Bezpieczeństwo** – logowanie wywołań, walidacja parametrów, limity i opcjonalne potwierdzenia w UI.
5. **Monitoring** – metryki użycia narzędzi + log `logs/mcp-tools.log`.
6. **Tryb pracy** – domyślnie moduł działa w ramach głównego API Rider-PC (ten sam port), ale konfiguracja powinna pozwolić przełączyć go w tryb „standalone” (np. `MCP_STANDALONE=true`, `MCP_PORT=8210`) i wystartować jako osobna aplikacja Uvicorn/FastAPI z tym samym rejestrem narzędzi (skalowalność / integracje zewnętrzne).

## Architektura
### 1. Warstwa MCP (FastAPI)
```
pc_client/api/routers/mcp_router.py
  - GET /api/mcp/tools      -> lista narzędzi (name, title, schema)
  - GET /api/mcp/resources  -> zasoby (np. config bieżący)
  - POST /api/mcp/tools/invoke -> { tool, arguments } -> wynik/err
```

### 2. Rejestr narzędzi
- `pc_client/mcp/tools/__init__.py` – rejestr + dekorator.
- `pc_client/mcp/tools/system.py` – `get_local_time`, `get_system_status`.
- `pc_client/mcp/tools/robot.py` – `robot_move`, `robot_status`.
- `pc_client/mcp/tools/smart_home.py` – `toggle_light`, `set_scene`.
- `pc_client/mcp/tools/git.py` – `get_changed_files`, `run_tests` (read-only na start).
- Pierwsze narzędzia do wdrożenia (z krótkimi opisami):
  - `system.get_time` – zwraca lokalny czas Rider-PC (ISO 8601 + strefa).
  - `robot.status` – odczytuje aktualny stan robota (połączenie, bateria, tryb).
  - `robot.move` – wysyła prostą komendę ruchu (np. `forward`, `stop`) z walidacją parametrów.
  - `weather.get_summary` – podaje krótką prognozę pogody (lokalna integracja np. z OpenWeather, przechowywana w cache).
    - **Uwaga:** Wymaga dodania klucza API do `.env.example` (`OPENWEATHER_API_KEY`) oraz opcjonalnie czasu cache (`WEATHER_CACHE_TTL_SECONDS`). Należy uwzględnić te zmienne w module konfiguracyjnym (`Settings` w `pc_client/config/settings.py`) zgodnie ze standardem Rider-PC.
- Uproszczona architektura:
  - `registry.py` trzyma całą wiedzę (lista narzędzi, ich schema, handlery).
  - `mcp_router.py` tylko mapuje HTTP → registry (walidacja, logi). Dzięki temu łatwo podmienić transport (np. STDIO) bez zmian w logice.

Każde narzędzie zawiera:
```python
Tool(
  name="system.get_time",
  description="Zwraca aktualny czas gospodarza Rider-PC.",
  args_schema={"type":"object","properties":{},"required":[]},
  handler=callable,
  permissions=["low"]
)
```

### 3. TextProvider + MCP
- TextProvider podczas inicjalizacji wczytuje katalog MCP.
- Jeśli model zwróci `tool_call`, `TextProvider` wykonuje MCP i wstrzykuje wynik jako kolejną wiadomość.
- Fallback: brak narzędzi => standardowy prompt.
- Format odpowiedzi MCP ujednolicamy, np.:
```json
{
  "ok": true,
  "tool": "system.get_time",
  "result": { "time": "2025-12-01T12:34:56" },
  "error": null,
  "meta": {
    "duration_ms": 12,
    "host": "rider-pc"
  }
}
```
`handler` zwraca tylko `result`, resztę (ok/error/meta) dokleja router – TextProvider i UI zawsze mają przewidywalny kształt JSON.

### 4. UI
- Chat PC: log narzędzi (`[tool] system.get_time -> 12:54`).
- View/System: nowy kafel „MCP” z liczbą wywołań, ostatnim narzędziem, statusem.

## Plan implementacji
1. **Spec MCP**: spisać minimalny kontrakt JSON (kompatybilny z Model Context Protocol).
2. **Rejestr**: moduł `pc_client/mcp/registry.py` + pierwsze narzędzia (`system.get_time`, `robot.status`, `robot.move`, `weather.get_summary`).
3. **Router**: `mcp_router.py` + walidacja + logowanie.
4. **TextProvider**: wsparcie tool-call (parsowanie JSON, konwersja do MCP).
5. **UI**: log narzędzi + kafel w `view.html`.
6. **Bezpieczeństwo**: progi (np. `robot_move` wymaga `confirm=true`), log `logs/mcp-tools.log`.
7. **Dokumentacja/testy**: opis w `docs_pl`, testy jednostkowe i integracyjne:
   - `tests/test_mcp_tools.py` – testy jednostkowe narzędzi MCP (poprawność handlerów, walidacja schematów, przypadki brzegowe).
   - `tests/test_mcp_router.py` – testy routera MCP (walidacja endpointów, odpowiedzi JSON, logowanie, obsługa błędów).
   - `tests/test_mcp_registry.py` – testy rejestru narzędzi (rejestracja, uprawnienia, dostępność narzędzi).
   - testy integracyjne endpointów API (wywołania HTTP, scenariusze sukces/błąd, zgodność ze spec MCP).

## Ryzyka
- LLM musi wspierać tool-calling (Mixtral, Llama3.2 Tool); dla innych modeli fallback do makr.
- Zachowanie kontroli nad „niebezpiecznymi” komendami – potrzebny whitelist i tryb potwierdzania w UI.
- Utrzymanie zgodności ze spec MCP – planujemy minimalny subset, ale dokumentacja powinna jasno określić różnice.
