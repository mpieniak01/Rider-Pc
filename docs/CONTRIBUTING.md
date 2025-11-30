# Contributing to Rider-PC

This reference collects the rules we follow when working on the repository (including Copilot coding agents).

## Tooling & Environment

- **Python 3.11** – install dependencies from `requirements-ci.txt`; heavy ML packages stay optional.
- **pre-commit** – run `pip install -r requirements-ci.txt && pre-commit install`.
- **Copilot / agents** – `.github/workflows/copilot-setup-steps.yml` together with `./config/agent/run_tests.sh` reproduce the minimal test setup used by Copilot coding agent.
- **`.env` files** remain local. If you need a new key, update `/.env.example` instead of committing secrets.

## Pull Request Checklist

1. `pre-commit run --all-files` (runs `ruff` + `ruff-format` with auto-fixes).
2. `./config/agent/run_tests.sh` (executes pytest for `pc_client/tests` + `tests/test_project_issues.py`, just like Copilot).
3. When touching frontend assets:
   ```bash
   npm ci
   npm run lint:css
   npm run css:size
   ```
   optionally `npm run css:audit` for layout changes.
4. Describe manual verification steps (visual checks, watchdog runs, etc.) inside the PR.

## Documentation & References

- Copilot-specific tips live in `.github/copilot-instructions.md`.
- The README “Development Workflow” section highlights the key Make targets (`make lint`, `make test`, …).
- Whenever you introduce new endpoints/configs, mention them in the appropriate `docs/*.md`.

## CI Pipelines

- **Quick Checks** – triggered on every push to `main`; include `ruff check` and a short `pytest pc_client/tests`. Even doc-only commits keep formatting enforced.
- **CI Pipeline (PR)** – the full suite (`unit-tests`, `e2e-tests`, `css-ui-audit`) now runs only for pull requests. Both humans and Copilot agents go through this path.
- **Copilot Setup Steps** – the agent-specific workflow is also PR-only, keeping merges to `main` quick.
- **Quality / ruff** – linting jobs run in both Quick Checks and the PR pipeline, so code style is enforced everywhere.

Sticking to this checklist keeps CI predictable and collaboration with Copilot agents smooth.
