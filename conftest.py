"""Root test guard: no real robot, BUS, device or remote service access."""

from pc_client.testing.isolation import install_automation_isolation


def pytest_configure(config):
    config._robot_isolation_guard = install_automation_isolation()


def pytest_unconfigure(config):
    guard = getattr(config, "_robot_isolation_guard", None)
    if guard:
        guard.undo()
