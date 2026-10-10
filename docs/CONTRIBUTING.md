# Contributing to Rider-PC

This reference collects the rules we follow when working on the repository (including Copilot coding agents).

## Tooling & Environment

- **Python 3.11** – use the existing local venv; `requirements-ci.txt` describes test dependencies.
- **pre-commit** – use the existing tools in the project venv.
- **Copilot / agents** – `.github/workflows/copilot-setup-steps.yml` together with `./config/agent/run_tests.sh` reproduce the minimal test setup used by Copilot coding agent.
- **`.env` files** remain local. If you need a new key, update `/.env.example` instead of committing secrets.

## Minimal runtime and WSL tests

Rider-PC runtime includes its API, transports, and enabled providers. Install
heavy ML packages only for a selected backend. The broad `requirements.txt`
does not mean every feature must run on the robot. `requirements-ci.txt` also
contains test tools and serves local tests/CI.

Use the existing project `.venv` in WSL. A worktree can use its interpreter and
tools without another copy of the same packages. Rider-PC, Rider-Pi, and Venom
have separate stacks; do not install packages globally or into another
project's environment. Update a dependency only for an identified missing
package or version conflict.

The physical Rider-Pi keeps its own minimal runtime. The full test suite runs
in a local WSL venv. A missing WSL package describes WSL; it does not prove a
missing Pi package or a hardware limitation. Client tests do not require test
or development packages on the robot.

## Physical robot and test categories

- Automated software tests use isolated mocks/simulation, without the real
  Pi, its BUS or UART. WSL can reach the device; the environment or TEST_MODE
  label alone does not prove isolation.
- Hardware checks without movement, such as camera/LCD/telemetry, have a
  separate scope and must not start autonomy or actuators.
- Tests of driving, turning, height, balance, actions or any task capable
  of moving the robot run only manually after explicit operator consent
  for a specific plan. Never through automated pytest/E2E/CI, general
  diagnostics, deployment, scheduling or opening the panel. Permission for
  camera/services does not authorize movement; one attempt does not permit
  subsequent automated tests.
- Before an attempt, the operator confirms space, surface, cable and stopping.
  Diagnostics do not arm the robot or clear E-Stop. Motion button checks
  using a completely isolated mock remain software tests.

This is a working rule, not proof that every current backend/script is protected.
Read the effects of any test/diagnostic script before running it.

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

- **Quick Checks** – triggered on every push to `main`; include `ruff check` and a short `pytest pc_client/tests` run (without `tests/test_project_issues.py`). Contract/issue tests stay reserved for the PR pipeline and the Copilot agent script.
- **CI Pipeline (PR)** – the full suite (`unit-tests`, `e2e-tests`, `css-ui-audit`) now runs only for pull requests. Both humans and Copilot agents go through this path.
- **Copilot Setup Steps** – the agent-specific workflow is also PR-only, keeping merges to `main` quick.
- **Quality / ruff** – linting runs twice: Quick Checks cover push-to-main, while the Quality workflow handles pull requests, so code style is enforced everywhere.

Sticking to this checklist keeps CI predictable and collaboration with Copilot agents smooth.
