from finbot.mock_mcp_servers.payments_mcp.server import (
    create_payment,
    refund_payment,
    VULNS
)

def test_double_refund_allowed_when_vulnerable():
    VULNS["allow_double_refund"] = True

    pid = create_payment(100)["payment_id"]
    refund_payment(pid)
    result = refund_payment(pid)

    assert result["status"] == "success"


def test_double_refund_blocked_when_vuln_disabled(monkeypatch):
    monkeypatch.setitem(VULNS, "allow_double_refund", False)

    pid = create_payment(100)["payment_id"]
    refund_payment(pid)
    result = refund_payment(pid)

    assert result["status"] == "error"
