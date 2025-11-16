.PHONY: start stop reload lint format test
VENV_BIN ?= .venv/bin
PY ?= $(if $(wildcard $(VENV_BIN)/python),$(VENV_BIN)/python,python3)

start:
	@bash scripts/start_local_stack.sh

stop:
	@bash scripts/stop_local_stack.sh

reload: stop start
	@echo "Reloaded local service stack."

lint:
	@$(PY) -m ruff check .

format:
	@$(PY) -m ruff format .

test:
	@PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTEST_ASYNCIO_MODE=auto \
		$(PY) -m pytest pc_client/tests/ \
		-q --maxfail=1 --tb=short \
		-p pytest_asyncio.plugin \
		-p pytest_timeout \
		--timeout=30 --timeout-method=thread
