import pytest
from finbot.mcp.registry import MCPRegistry


def test_register_and_has_server():
    registry = MCPRegistry()

    registry.register_server("payments", {"endpoint": "mock"})
    assert registry.has_server("payments") is True
    assert registry.has_server("drive") is False


def test_get_server_success():
    registry = MCPRegistry()
    config = {"endpoint": "mock-payments"}

    registry.register_server("payments", config)
    server = registry.get_server("payments")

    assert server == config


def test_get_server_not_found():
    registry = MCPRegistry()

    with pytest.raises(KeyError):
        registry.get_server("unknown")
