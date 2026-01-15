

from mcp.server.fastmcp import FastMCP
import uuid, os, yaml

mcp = FastMCP("Payments")

with open(os.path.join(os.path.dirname(__file__), "vulnerabilities.yaml")) as f:
    VULNS = yaml.safe_load(f) or {}

PAYMENTS = {}

@mcp.tool()
def create_payment(amount: int):
    pid = str(uuid.uuid4())
    PAYMENTS[pid] = {"status": "created"}
    return f"Success: Payment {pid} created."

@mcp.tool()
def refund_payment(payment_id: str):
    p = PAYMENTS.get(payment_id)
    if not p:
        return "Error: Not found"
    if p["status"] == "refunded" and not VULNS.get("allow_double_refund"):
        return "Error: Already refunded"
    p["status"] = "refunded"
    return f"Success: Payment {payment_id} refunded."

# if __name__ == "__main__":
#     mcp.run()


if __name__ == "__main__":
    import sys
    import asyncio

    if not sys.stdin.isatty():
        sys.stdout = sys.stderr
        asyncio.run(mcp.run_stdio_async())
    else:
        mcp.run()
