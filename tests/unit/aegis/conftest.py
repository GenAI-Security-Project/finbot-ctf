"""Shared fixtures for AEGIS unit tests."""

import pytest

from finbot.config import settings


@pytest.fixture(autouse=True)
def chain_secret(monkeypatch):
    """AuditChain needs a configured secret; give each test a throwaway one."""
    monkeypatch.setattr(settings, "AEGIS_CHAIN_SECRET", "unit-test-only-secret")
