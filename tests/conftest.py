"""
Global test configuration for FinBot CTF.
"""

import pytest
from fastapi.testclient import TestClient

from finbot.main import app

# Load the Google Sheets pytest plugin
pytest_plugins = ["tests.plugins.google_sheets_reporter.pytest_google_sheets"]


@pytest.fixture
def client():
    """Test client for the Main FinBot app."""
    with TestClient(app) as test_client:
        yield test_client


def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "smoke: Critical functionality tests")
    config.addinivalue_line("markers", "web: Web application tests")


def pytest_collection_modifyitems(config, items):
    """Auto-mark tests based on location."""
    _ = config

    for item in items:
        test_path = str(item.fspath)

        if "/unit/" in test_path or "\\unit\\" in test_path:
            item.add_marker(pytest.mark.unit)
        elif "/integration/" in test_path or "\\integration\\" in test_path:
            item.add_marker(pytest.mark.integration)

        if "/web/" in test_path or "\\web\\" in test_path:
            item.add_marker(pytest.mark.web)

@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Create all tables before running tests"""
    from finbot.core.data.database import create_tables
    create_tables()
    yield