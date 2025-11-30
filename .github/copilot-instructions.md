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

## Testy obowiązkowe
1. `./config/agent/run_tests.sh` – buduje dedykowaną wirtualkę, instaluje zależności i uruchamia `pytest pc_client/tests tests/test_project_issues.py`.
2. Jeśli modyfikujesz frontend/CSS, uruchom `npm run lint:css` oraz `npm run css:size`. E2E (`tests/e2e`) jest opcjonalne i wykonujemy je tylko przy zmianach Playwrighta.
3. Każda zmiana w kodzie Pythona wymaga **`ruff check .`** (np. `make lint`) – oddawanie niesformatowanego kodu blokuje merge, bo CI zatrzyma się na lintach.
4. W przypadku zmian w docs/web możesz ograniczyć się do lintów, ale backend zawsze trzeba zweryfikować testami + `ruff`.

## Dobre praktyki
- Resetuj singletony/adapters w testach (tak jak robią to istniejące testy) aby unikać przecieków stanu.
- Przy dodawaniu endpointów pamiętaj o mockach (`MockGitHubAdapter`, `MockGitAdapter`) zamiast prawdziwych integracji.
- Gdy wprowadzisz nową konfigurację, dodaj klucz do `Settings` (`pc_client/config/settings.py`) oraz ustaw domyślne wartości w `.env.example`.
- Zainstaluj `pre-commit` i przed PR uruchom `pre-commit run --all-files` – hooki (`ruff` + `ruff-format` z `--fix`) muszą przejść lokalnie, żeby uniknąć poprawek “na ślepo”.
- W CI obowiązuje `ruff` – uruchom `make lint` jeśli dotykasz stylu.
- Każda zmiana powinna zawierać krótkie uzasadnienie w opisie PR oraz kroki reprodukcji/regresji.

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
