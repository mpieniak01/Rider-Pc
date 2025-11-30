# Wkład w Rider-PC

Ten dokument zbiera praktyczne wskazówki dla osób (i agentów) pracujących nad repozytorium.

## Narzędzia i środowisko

- **Python 3.11** – instaluj dependencies z `requirements-ci.txt`, ciężkie modele są opcjonalne.
- **pre-commit** – `pip install -r requirements-ci.txt && pre-commit install`.
- **Copilot / agenty** – workflow `.github/workflows/copilot-setup-steps.yml` oraz skrypt `./config/agent/run_tests.sh` odtwarzają minimalne środowisko testowe.
- **Pliki `.env`** są prywatne. Jeżeli potrzebujesz nowej zmiennej, zaktualizuj `/.env.example`, nie commituj realnych wartości.

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

Zastosowanie checklisty pozwala utrzymać spójność z CI oraz ułatwia współpracę z agentami Copilot.
