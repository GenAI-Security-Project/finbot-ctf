# ============================================================
# File: finbot/aegis/harness/plugin.py
# Purpose: pytest-aegis plugin + attack fixtures
# Author: Jean Francois Regis MUKIZA
# GSoC Week: 8
# OWASP Category: -
# ============================================================
"""Pytest plugin for AEGIS red-team testing framework."""

import pytest

# Fixtures that need the AEGIS enforcement service (mock_enforcement_service,
# sample_tool_context) are added together with that service; they cannot import yet.


@pytest.fixture
def attack_fixtures() -> dict[str, dict[str, str]]:
    """Provide common attack payloads for testing."""
    return {
        "rce_attempt": {"script": "rm -rf /"},
        "sql_injection": {"query": "SELECT * FROM users WHERE id = 1 OR 1=1"},
        "path_traversal": {"path": "../../../etc/passwd"},
        "command_injection": {"cmd": "ls; cat /etc/passwd"},
    }


def pytest_configure(config: pytest.Config) -> None:
    """Register AEGIS-specific markers."""
    config.addinivalue_line("markers", "asi: mark test as related to specific ASI category")
    config.addinivalue_line("markers", "attack: mark test as simulating an attack scenario")
    config.addinivalue_line("markers", "defense: mark test as verifying defensive measures")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Automatically mark tests based on their location or content."""
    for item in items:
        # Mark tests in asi directories
        if "asi" in str(item.fspath).lower():
            item.add_marker(pytest.mark.asi)
        # Mark tests that mention attack/defense in their name
        if "attack" in item.name.lower():
            item.add_marker(pytest.mark.attack)
        if "defense" in item.name.lower() or "defend" in item.name.lower():
            item.add_marker(pytest.mark.defense)
