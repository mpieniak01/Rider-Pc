# Wskazówki dla GitHub Copilot Coding Agent

Repozytorium Rider-PC ma rozbudowany backend FastAPI oraz pakiet testów jednostkowych (`pc_client/tests`) i kontraktowych (`tests/test_project_issues.py`). Poniższe zasady opisują oczekiwania względem agenta:

## Styl i komunikacja
- **Komunikacja po polsku** – commit/pull request summary oraz komentarze w kodzie prowadź w języku polskim (chyba że plik wymaga innego języka).
- Unikaj dodatkowych frameworków – trzymamy się standardu FastAPI + httpx + asyncio; po stronie frontu stosujemy istniejące arkusze CSS.
- Stosuj czytelne nazewnictwo i minimalne komentarze wyjaśniające jedynie złożone fragmenty logiki.

## Środowisko developerskie
- Bazowa wersja Pythona: **3.11**. Do szybkich prac tworzymy osobne wirtualne środowisko (`.venv-agent`) – patrz `config/agent/run_tests.sh`.
- Do instalacji zależności używamy zestawu CI (`requirements-ci.txt`) z ograniczeniami w `config/agent/constraints.txt`. Nie pobieramy ciężkich modeli (torch/whisper/ollama).
- W zadaniach front-endowych wymagamy Node.js 20 i komend `npm ci`, `npm run lint:css`, `npm run css:size`, `npm run css:audit`.
- Plik `.env` nigdy nie trafia do repo – jeśli trzeba dopisać nowy klucz, zmodyfikuj `/.env.example` i zostaw instrukcję w opisie zmiany, a prywatne wartości trzymaj lokalnie.

## Testy obowiązkowe (z optymalizacją czasu)
1. Preferuj szybkie, ukierunkowane testy. Pełne `./config/agent/run_tests.sh` (instalacja + `pytest pc_client/tests tests/test_project_issues.py`) odpalaj tylko wtedy, gdy faktycznie modyfikujesz backend lub kluczową logikę. Przy zadaniach dokumentacyjnych/planistycznych czy drobnych poprawkach frontu wystarczy `ruff check` + odpowiednie linty.
2. Jeśli modyfikujesz frontend/CSS, uruchom `npm run lint:css` oraz `npm run css:size`. `npm ci` i testy E2E (`tests/e2e`) odpalamy wyłącznie, gdy dotykamy Playwrighta albo kluczowych layoutów wymagających screenshotów.
3. Każda zmiana w kodzie Pythona nadal wymaga **`ruff check .`**. Gdy zakres jest mały, możesz uruchomić tylko powiązane moduły `pytest` (np. `pytest tests/test_chat_router.py`) zamiast całego pakietu – ważne, by pokryć zmodyfikowaną logikę i zmieścić się w limitach czasowych.
4. W zmianach dotyczących dokumentów (`docs_pl`, `README`, plany) unikaj instalowania całego stosu – wystarczy formatowanie (`ruff`, `markdownlint`). Dzięki temu agent nie traci czasu na instalacje, a główne prace developerskie nie są przerywane przez timeouty.

## Dobre praktyki
- Resetuj singletony/adapters w testach (tak jak robią to istniejące testy) aby unikać przecieków stanu.
- Przy dodawaniu endpointów pamiętaj o mockach (`MockGitHubAdapter`, `MockGitAdapter`) zamiast prawdziwych integracji.
- Gdy wprowadzisz nową konfigurację, dodaj klucz do `Settings` (`pc_client/config/settings.py`) oraz ustaw domyślne wartości w `.env.example`.
- Zainstaluj `pre-commit` i przed PR uruchom `pre-commit run --all-files` – hooki (`ruff` + `ruff-format` z `--fix`) muszą przejść lokalnie, żeby uniknąć poprawek “na ślepo”.
- W CI obowiązuje `ruff` – uruchom `make lint` jeśli dotykasz stylu.
- Kazda zmiana powinna byc udokumentowana postaci planu zmian w wersji polskiej w katalogu /dosc_pl/_to_do w nazwie {numer_PR}, na zakonczenie prac plan powinien byc zaktualizowany o wykonane zmiany i pozostawiony w repozytorium.
- Agent na zakonczenie pracy musi zamknac swoja sesje i zwolnic srodowisko o ile z niego korzystal podczas pracy.

## Szybkie komendy
```bash
# instalacja zależności dla agenta
./config/agent/run_tests.sh  # tworzy .venv-agent i odpala pytest

# manualne sprawdzenie UI/CSS
npm ci
npm run lint:css
npm run css:size
```

Stosowanie powyższych zasad pozwala agentom Copilot utrzymać spójny standard pracy i szybciej dostarczać poprawki.
