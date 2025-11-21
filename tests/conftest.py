"""Global pytest hooks for test categorization."""

from pathlib import Path

import pytest


@pytest.hookimpl
def pytest_collection_modifyitems(config, items):
    """
    Automatically tag tests with markers based on their location.

    - tests under tests/e2e → ui
    - all other collected tests → api
    """
    root = Path(config.rootpath)
    for item in items:
        rel = Path(item.fspath).resolve().relative_to(root)
        if "e2e" in rel.parts:
            item.add_marker("ui")
        else:
            item.add_marker("api")
