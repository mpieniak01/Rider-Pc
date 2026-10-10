# Wkład w Rider-PC

Ten dokument zbiera praktyczne wskazówki dla osób (i agentów) pracujących nad repozytorium.

## Narzędzia i środowisko

- **Python 3.11** – używaj istniejącego lokalnego venv; zależności testowe opisuje `requirements-ci.txt`.
- **pre-commit** – uruchamiaj istniejące narzędzia z lokalnego venv projektu.
- **Copilot / agenty** – workflow `.github/workflows/copilot-setup-steps.yml` oraz skrypt `./config/agent/run_tests.sh` odtwarzają minimalne środowisko testowe.
- **Pliki `.env`** są prywatne. Jeżeli potrzebujesz nowej zmiennej, zaktualizuj `/.env.example`, nie commituj realnych wartości.

## Minimalny runtime i testy w WSL

Runtime Rider-PC obejmuje API, transport i włączone providery. Ciężkie pakiety
ML instaluje się tylko dla rzeczywiście wybranego backendu; szeroki
`requirements.txt` nie oznacza, że wszystkie funkcje muszą działać na robocie.
`requirements-ci.txt` zawiera też narzędzia testowe i służy lokalnym testom/CI.

Korzystaj z istniejącego `.venv` projektu w WSL. Worktree może używać jego
interpretera i narzędzi, bez kolejnej instalacji tych samych pakietów.
Rider-PC, Rider-Pi i Venom mają oddzielne stosy; nie instaluj pakietów globalnie
ani do środowiska innego projektu. Aktualizuj zależność dopiero przy konkretnym
braku lub konflikcie wersji.

Rider-Pi ma własny minimalny runtime na fizycznym urządzeniu. Pełny zestaw
testowy uruchamia się w lokalnym venv WSL. Brak pakietu w WSL opisuje stan WSL;
nie jest dowodem braku tego pakietu ani ograniczeniem sprzętu Pi. Zależności
testowe/dev nie trafiają na robota z powodu lokalnego testu klienta.

## Fizyczny robot i kategorie testów

- Automatyczne testy programowe używają izolowanych mocków/symulatora,
  bez prawdziwego Pi, jego BUS i UART. WSL może łączyć się z urządzeniem;
  samo środowisko ani etykieta TEST_MODE nie potwierdzają izolacji.
- Test sprzętu bez ruchu, np. kamery/LCD/telemetrii, ma odrębny zakres
  i nie może uruchamiać autonomii ani napędów.
- Test jazdy, skrętu, wysokości, balansu, akcji lub zadania mogącego poruszyć
  robotem wykonuje się wyłącznie ręcznie po wyraźnej zgodzie operatora na
  konkretny plan. Nigdy przez automatyczne pytest/E2E/CI, ogólną diagnostykę,
  deploy, harmonogram lub otwarcie panelu. Zgoda na kamerę/start usług nie
  jest zgodą na ruch; jedna próba nie dopuszcza kolejnych automatycznych testów.
- Przed próbą operator potwierdza przestrzeń, podłoże, kabel i zatrzymanie.
  Diagnostyka nie uzbraja robota ani nie kasuje E-Stop. Przy zmianie panelu
  test przycisków ruchu na całkowicie izolowanym mocku pozostaje programowy.

To reguła pracy; nie stanowi potwierdzenia zabezpieczenia wszystkich aktualnych
ścieżek backendu i skryptów. Nie uruchamiaj skryptu test/diag bez odczytania skutków.

## Checklist przed PR

1. `pre-commit run --all-files` – uruchomi `ruff` i `ruff-format` z automatycznymi poprawkami.
2. `./config/agent/run_tests.sh` – replikuje to, co uruchamiane jest przez Copilot coding agent (pytest dla `pc_client/tests` + `tests/test_project_issues.py`).
3. Jeżeli dotykasz frontendu:
   ```bash
   npm ci
   npm run lint:css
   npm run css:size
   ```
   (opcjonalnie `npm run css:audit`, gdy zmieniasz layout/menu).
4. Ręcznie opisz w PR wszystkie kroki manualne (np. test wizualny, watchdog, integracje).

## Dokumentacja i odniesienia

- Szczegółowe wytyczne dla Copilot coding agent znajdują się w `.github/copilot-instructions.md`.
- README posiada sekcję “Development Workflow” z najważniejszymi komendami Make (`make lint`, `make test`, itd.).
- W przypadku dodania nowych endpointów/configów dopisz krótką notkę w odpowiednim pliku `docs/*.md`.

## Przepływy CI

- **Quick Checks** – uruchamiane przy każdym `push` na `main`. Zawierają `ruff check` oraz skrócony pakiet testów (`pytest pc_client/tests` z limitem czasu, bez kontraktowego `tests/test_project_issues.py`). Pełny zestaw testów kontraktowych odpala się wyłącznie w CI Pipeline (PR) oraz przez skrypt agenta (`./config/agent/run_tests.sh`).
- **CI Pipeline (PR)** – pełny zestaw (`unit-tests`, `e2e-tests`, `css-ui-audit`) od teraz odpala się tylko dla pull requestów. To tutaj trafiają wszystkie zmiany tworzone przez ludzi i Copilot coding agent.
- **Copilot Setup Steps** – workflow przygotowujący środowisko agenta również działa tylko dla PR-ów, więc nie spowalnia prostych merge’y do `main`.
- **Quality / ruff** – niezależny job lintujący działa zarówno w Quick Checks (push do `main`), jak i w Quality workflow (PR), więc format kodu jest pilnowany w obu scenariuszach.

Zastosowanie checklisty pozwala utrzymać spójność z CI oraz ułatwia współpracę z agentami Copilot.
