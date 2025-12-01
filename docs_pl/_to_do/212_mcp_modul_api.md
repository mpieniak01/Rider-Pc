# 212 – Lokalny moduł MCP w Rider-PC

## Cel
Zapewnić wewnętrzny serwer MCP (Model Context Protocol) jako moduł FastAPI Rider-PC bez dodatkowych usług/portów. Umożliwi to lokalnemu Chat PC i przyszłym agentom korzystanie z jednolitego zestawu narzędzi (czas, status robotów, smart home, automatyzacje) bez pośredników.

## Status implementacji

### ✅ Zrealizowane
1. **API MCP** – endpointy `POST /api/mcp/tools/invoke`, `GET /api/mcp/resources`, `GET /api/mcp/tools`, `GET /api/mcp/stats`, `GET /api/mcp/history`.
2. **Rejestr narzędzi** – `pc_client/mcp/registry.py` z dekoratorem `@mcp_tool`.
3. **Narzędzia MCP**:
   - `system.get_time` – zwraca lokalny czas (ISO 8601 + strefa).
   - `system.get_status` – status systemu Rider-PC.
   - `robot.status` – stan robota (połączenie, bateria, tryb).
   - `robot.move` – komenda ruchu (wymaga confirm=true).
   - `weather.get_summary` – prognoza pogody (mock + cache).
   - `smart_home.toggle_light` – sterowanie światłem.
   - `smart_home.set_brightness` – jasność światła.
   - `smart_home.set_scene` – sceny oświetleniowe.
   - `smart_home.get_status` – status urządzeń.
   - `git.get_changed_files` – lista zmian w repo.
   - `git.get_status` – status repozytorium.
   - `git.get_diff` – diff zmian.
   - `git.get_log` – historia commitów.
4. **Integracja z TextProviderem**:
   - Obsługa tool-call w `text_provider.py`.
   - Wstrzykiwanie narzędzi MCP do system prompt.
   - Parsowanie odpowiedzi LLM i wykonywanie narzędzi.
   - Historia wywołań w `get_mcp_call_history()`.
   - Endpoint `/api/chat/pc/mcp-history` do pobierania historii.
5. **Logowanie**:
   - Dedykowany logger `mcp.tools` zapisujący do `logs/mcp-tools.log`.
   - Endpoint `/api/mcp/history` do przeglądania logów.
6. **UI / Monitoring**:
   - Kafel „MCP Tools" w `view.html` z liczbą narzędzi, wywołań, ostatnim narzędziem.
   - Lista narzędzi i konfiguracja MCP w panelu.
7. **Tryb standalone**:
   - Zmienne `MCP_STANDALONE` i `MCP_PORT` w `.env.example` i Settings.
   - Moduł `pc_client/mcp/standalone.py` do uruchomienia osobnego serwera.
8. **Testy**:
   - `tests/test_mcp_tools.py` – testy narzędzi i integracji z TextProvider.
   - `tests/test_mcp_router.py` – testy endpointów API.
   - `tests/test_mcp_registry.py` – testy rejestru.

### 🔄 Do rozważenia w przyszłości
- Rozszerzone UI do potwierdzania narzędzi wymagających `confirm` (modal w czacie).
- Pełna integracja z OpenWeather API (obecnie mock).
- Więcej narzędzi git (np. `run_tests`).

## Zakres
1. **API MCP** – endpointy `POST /api/mcp/tools/invoke`, `GET /api/mcp/resources`, `GET /api/mcp/tools`.
2. **Rejestr narzędzi** – pythonowy katalog z opisami JSON-schema (wejście/wyjście) i oznaczeniem uprawnień.
3. **Integracja z TextProviderem** – obsługa tool-call (LLM -> MCP -> odpowiedź) w trybie Chat PC.
4. **Bezpieczeństwo** – logowanie wywołań, walidacja parametrów, limity i opcjonalne potwierdzenia w UI.
5. **Monitoring** – metryki użycia narzędzi + log `logs/mcp-tools.log`.
6. **Tryb pracy** – domyślnie moduł działa w ramach głównego API Rider-PC (ten sam port), ale konfiguracja powinna pozwolić przełączyć go w tryb „standalone" (np. `MCP_STANDALONE=true`, `MCP_PORT=8210`) i wystartować jako osobna aplikacja Uvicorn/FastAPI z tym samym rejestrem narzędzi (skalowalność / integracje zewnętrzne).
7. **Aktualizacja `.env.example`** – dodać nowe zmienne środowiskowe `MCP_STANDALONE` i `MCP_PORT` z domyślnymi wartościami zgodnie z wytycznymi projektu.

## Architektura
### 1. Warstwa MCP (FastAPI)
```
pc_client/api/routers/mcp_router.py
  - GET /api/mcp/tools      -> lista narzędzi (name, title, schema)
  - GET /api/mcp/resources  -> zasoby (np. config bieżący)
  - POST /api/mcp/tools/invoke -> { tool, arguments } -> wynik/err
  - GET /api/mcp/stats      -> statystyki wywołań
  - GET /api/mcp/history    -> historia wywołań z logu
```

### 2. Rejestr narzędzi
- `pc_client/mcp/tools/__init__.py` – rejestr + dekorator.
- `pc_client/mcp/tools/system.py` – `get_local_time`, `get_system_status`.
- `pc_client/mcp/tools/robot.py` – `robot_move`, `robot_status`.
- `pc_client/mcp/tools/smart_home.py` – `toggle_light`, `set_scene`.
- `pc_client/mcp/tools/git.py` – `get_changed_files`, `get_status`, `get_diff`, `get_log`.
- `pc_client/mcp/tools/weather.py` – `get_summary` (mock + cache).

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

### 4. UI
- Chat PC: log narzędzi (`[tool] system.get_time -> 12:54`).
- View/System: kafel „MCP Tools" z liczbą wywołań, ostatnim narzędziem, statusem.

## Plan implementacji
1. ✅ **Spec MCP**: spisać minimalny kontrakt JSON (kompatybilny z Model Context Protocol).
2. ✅ **Rejestr**: moduł `pc_client/mcp/registry.py` + pierwsze narzędzia.
3. ✅ **Router**: `mcp_router.py` + walidacja + logowanie.
4. ✅ **TextProvider**: wsparcie tool-call (parsowanie JSON, konwersja do MCP).
5. ✅ **UI**: log narzędzi + kafel w `view.html`.
6. ✅ **Bezpieczeństwo**: progi (np. `robot_move` wymaga `confirm=true`), log `logs/mcp-tools.log`.
7. ✅ **Dokumentacja/testy**: opis w `docs_pl`, testy jednostkowe i integracyjne.

## Ryzyka
- LLM musi wspierać tool-calling (Mixtral, Llama3.2 Tool); dla innych modeli fallback do makr.
- Zachowanie kontroli nad „niebezpiecznymi" komendami – potrzebny whitelist i tryb potwierdzania w UI.
- Utrzymanie zgodności ze spec MCP – planujemy minimalny subset, ale dokumentacja powinna jasno określić różnice.
