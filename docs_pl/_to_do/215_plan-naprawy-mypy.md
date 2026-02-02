# Plan naprawy wymagań mypy dla Rider-PC

## 1. Priorytetowe przyczyny błędów
- **Niepewne typy `pc_client/core/service_manager.py`**: `asyncio.gather(..., return_exceptions=True)` może zwrócić wyjątek, przez co kolejne użycia `.get()` są niepoprawne dla `BaseException`. Potrzebujemy precyzyjnych typów dla `details`.
- **Adaptery REST/systemd/git**: metody zwracają `object`/`Any`, a kod zakłada słowniki lub listy. Trzeba dodać typy wejścia/wyjścia i użyć bezpiecznych odszyfrowań.
- **Providerzy (`vision_provider`, `voice_provider`, `text_provider`)**: funkcje oczekują `dict[str, Any]`, ale domyślne `None` lub `object` powodują błędy. Wprowadzić `Optional` i konkretną logikę walidującą.
- **MCP/tools / core helpers**: zapisywanie w `dict` bez adnotacji, zwracanie `BaseException`, `None` bez obsługi, brak importów typu (np. `Mapping`, `ModelInfo`).
- **Obsługa `tomli`/`tomllib`**: powtarzające się importy z różnymi aliasami blokują `no-redef`.

## 2. Plan naprawczy
1. **Poprawa `service_manager` i odczyty systemd** – zaktualizowano pętlę `results` tak, by `details` zawsze było `Mapping[str, Any]` z fallbackiem; dalsza weryfikacja mypy pokazuje, że kolejne moduły nadal wymagają pracy, więc krok przechodzi do etapu **pierwszy moduł zakończony, blokady zewnętrzne**.
2. **Ujednolicenie typów adapterów** – dodać aliasy typów (`RESTResponse`, `ServiceDetails`), wyraźnie rzutować `get_unit_details` i `get_project_status` w adapterach; po tym mypy przestanie zgłaszać brak `.items()` w `object` (status: planowane).
3. **Providerzy + usługi** – przydzielić `Optional[dict[str, Any]]` tam, gdzie wcześniej `None` był akceptowany, i zabezpieczyć kod tak, żeby mypy zauważył `dict` zanim użyje `.get` (status: planowane).
4. **MCP/tools (smart_home, robot)** – narzucić `Mapping`/`Sequence`, przetestować parsing payloadów, wykryć `object` i zastąpić `dict[str, Any]`. (status: planowane)
5. **Model manager / knowledge store** – dodać docstringi typów, usunąć wielokrotne importy `tomli`, zdefiniować helpery `Optional[...]` tam, gdzie `None` jest możliwe; w razie potrzeby dodać `typing.cast`. (status: planowane)
6. **Weryfikacja i rozciągnięcie zestawu** – po czyszczeniu uruchomić `make typecheck`, odblokować katalog `tests` lub włączyć `--check-untyped-defs` jeśli zajdzie potrzeba (status: planowane).

## 3. Pierwsze działania
- [x] Dodano `mypy.ini`, `requirements`, `typecheck` w Makefile.
- [x] Zaktualizowano `pc_client/core/service_manager.py`, ale `mypy --config-file mypy.ini pc_client/core/service_manager.py` nadal zgłasza błędy w adapterach/model_managerze (42 błędy), więc kolejne moduły nadal wymagają pracy.
- [x] Wprowadzono dokładne typy w `pc_client/mcp/tools/*`, `pc_client/queue/redis_queue.py`, `pc_client/api/routers/provider_router.py`, `pc_client/services/google_assistant.py` i skryptach pomocniczych, dzięki czemu `make typecheck` przebiega (uwaga: jedynie standardowe notyfikacje o niepełnym typowaniu w skryptach pomocniczych).
- [x] Uruchomiono zestaw regresyjny selekcji testów (`tests/test_assistant_router.py ... pc_client/tests/test_system_log_events.py`); wynik: `132 passed, 27 skipped` w `.venv`.

## 4. Stan do publikacji na gałąź `215` (wydanie zbiorcze z #214)
- **Mypy:** `make typecheck` wykonuje się bez błędów (poza wspomnianymi notacjami `annotation-unchecked` w `scripts/css_coverage.py` i `pc_client/api/lifecycle.py`, które nie wpływają na stabilność).
- **Testy:** tak jak wyżej, wszystkie wskazane testy przechodzą pod `.venv/bin/pytest`.
- **Czystość:** nie wyrzucano żadnych plików ani importów nieużywanych; zmiany w `pc_client/mcp/tools/__init__.py` dodają eksport `GitCommandResult`, więc testy widzą go bezpośrednio.
- **Zakres #214:** uzupełnione tłumaczenia EN w `web/*.html`, `web/templates/dashboard_base.html` i `web/assets/i18n.js`, plus skrypt `scripts/check_i18n.mjs` do walidacji brakujących kluczy.
- **Next steps przed PR:** przyciąć historię lokalnych zmian do krytycznych plików, ewentualnie przygotować branch `215` (przykład `git checkout -b 215` + commit tylko tym plikom). Jeśli potrzebujesz pomocy przy tworzeniu PR lub weryfikacji reszty zmian z `git status`, daj znać.

## 5. Notatka do recenzji (do wklejenia w PR)
Poniżej znajduje się gotowy opis do recenzji. Odnosi się do sekcji „Stan do publikacji na gałąź `215`”.

```
Zakres: poprawa typów dla mypy (narzędzia MCP, redis_queue, google_assistant, provider_router) + uzupełnienie tłumaczeń EN (web/*.html, dashboard_base.html, i18n.js) w ramach wydania zbiorczego #214/#215.
Status: make typecheck przechodzi; testy z listy regresyjnej (m.in. test_assistant_router, test_mcp_tools, test_project_issues) zakończone wynikiem 132 passed / 27 skipped.
Szczegóły i kontekst: docs_pl/_to_do/215_plan-naprawy-mypy.md (sekcja „Stan do publikacji na gałąź `215`”).
```
