"""
Root pytest configuration.

Marks Playwright/Streamlit browser tests with the ``e2e`` marker based on
filename so individual test files do not need to be edited.
"""
from pathlib import Path

import pytest


def pytest_collection_modifyitems(config, items):
    """Auto-mark E2E tests by filename (test_e2e*.py)."""
    e2e_marker = pytest.mark.e2e
    for item in items:
        path = Path(str(item.fspath)).name
        if path.startswith("test_e2e"):
            item.add_marker(e2e_marker)
