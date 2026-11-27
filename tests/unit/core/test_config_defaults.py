"""Unit tests for security configuration defaults."""

from finbot.config import Settings


def test_security_config_defaults_when_env_missing(monkeypatch, tmp_path):
    """Verify safe defaults when security env vars are absent.

    SESSION_COOKIE_SECURE remains False by default so local HTTP dev and HTTP
    test clients work out of the box (production enforcement is tracked in #295).
    TRUSTED_PROXY_IPS defaults to None (zero-config PaaS fallback).
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SESSION_COOKIE_SECURE", raising=False)
    monkeypatch.delenv("TRUSTED_PROXY_IPS", raising=False)

    test_settings = Settings(_env_file=None)

    assert test_settings.SESSION_COOKIE_SECURE is False
    assert test_settings.TRUSTED_PROXY_IPS is None


def test_security_config_env_overrides(monkeypatch, tmp_path):
    """Verify security settings can be explicitly enabled via environment variables."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "true")
    monkeypatch.setenv("TRUSTED_PROXY_IPS", "10.0.0.1,127.0.0.1")

    test_settings = Settings(_env_file=None)

    assert test_settings.SESSION_COOKIE_SECURE is True
    assert test_settings.TRUSTED_PROXY_IPS == "10.0.0.1,127.0.0.1"
