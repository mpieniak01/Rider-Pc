.PHONY: start stop reload

start:
	@bash scripts/start_local_stack.sh

stop:
	@bash scripts/stop_local_stack.sh

reload: stop start
	@echo "Reloaded local service stack."
