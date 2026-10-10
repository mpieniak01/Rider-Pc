# Development

Rider-Pi and Rider-PC are separate repositories. A shared VS Code workspace
does not change the terminal directory or the selected Python interpreter.
Run commands from the intended repository and select its environment.

```bash
pwd
git status --short --branch
git fetch origin
git log --oneline HEAD..origin/main
.venv/bin/python --version
.venv/bin/python -m pip check
```

Check uncommitted changes and stashes before updating a checkout. Use
`git pull --ff-only` on a clean main branch; preserve earlier work rather than
resetting it. Use a separate feature branch for application changes and a
focused PR with relevant checks and review. Documentation-only changes can
be committed directly to main when the repository owner requests it.

## Configuration and local notes

Use ordinary local env files. `.env`, private `.env.*`, `evn.ssh.local` and
`config/local/` contain developer configuration and credentials. Keep them
out of Git, PR attachments, logs and deployment packages. Public
`.env.example` and `.env.*.example` templates contain placeholders only.
Preserve an existing `.env`; do not overwrite it with a template.

The private SSH file should have mode `600`. Edit credentials locally;
do not put passwords in command arguments or documentation. Standard SSH
does not load `evn.ssh.local` automatically.

Task plans belong in ignored `_to_do/`; completed notes and session audits
belong in ignored `_done/` or `done/`. Publish maintained guides and their
required images according to the [documentation policy](DOCUMENTATION_POLICY.md).
Before committing, review `git diff --cached --name-status` and
`git diff --cached --check`. Do not force-add local files.

## PC environment, checks and panel

Use Python 3.11. Read [contributing](CONTRIBUTING.md) and the
[configuration guide](CONFIGURATION.md). Keep model data and logs local.
Inspection does not require reinstalling the ML stack or downloading models.

```bash
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
.venv/bin/python -m pytest pc_client/tests/ -q --maxfail=1
```

Select related contract or browser tests when changing an API or UI.
For CSS changes use `npm run lint:css` and `npm run css:size` with the existing
Node environment. Documentation changes need link and publication checks.
Record individual results locally. Mocks and cached telemetry do not verify
real models or physical robot commands.

Start the application from the repository with its configured environment:

```bash
.venv/bin/python -m pc_client.main
```

The panel defaults to `http://localhost:8000`; `SERVER_PORT` controls its port.
Starting the application can load models and connect to configured services.
The robot API is a separate service on the Pi, normally port `8080`.
Read [Pi integration](PC_OFFLOAD_INTEGRATION.md) before exercising motion.

## Task wizard and local plans

The task wizard can create GitHub issues and branches. Plans in
`docs_pl/_to_do/` stay local. Set `TASK_AUTO_INIT_ENABLED=false` in the local
`.env` and leave automatic initialization unchecked: the legacy initializer
also tries to commit the plan. A regular Git add rejects this ignored path;
do not override that protection. Create the plan locally and commit only
the resulting public documentation and implementation.
