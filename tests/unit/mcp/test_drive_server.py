from finbot.mock_mcp_servers.drive_mcp.server import read_file, VULNS

def test_unauthorized_read_allowed_when_vulnerable():
    VULNS["allow_unauthorized_read"] = True
    result = read_file("guest", "secret.txt")
    assert "Success" in result
    assert "CTF{" in result


def test_unauthorized_read_blocked_when_vuln_disabled(monkeypatch):
    monkeypatch.setitem(VULNS, "allow_unauthorized_read", False)
    result = read_file("guest", "secret.txt")
    assert "Access denied" in result
