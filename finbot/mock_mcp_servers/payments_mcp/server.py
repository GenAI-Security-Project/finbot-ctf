from mcp.server.fastmcp import FastMCP
import uuid
import os
import yaml


mcp = FastMCP("Payments")

with open(os.path.join(os.path.dirname(__file__), "vulnerabilities.yaml")) as f:
    VULNS = yaml.safe_load(f) or {}

PAYMENTS = {}


@mcp.tool()
def create_payment(amount: int):
    payment_id = str(uuid.uuid4())
    PAYMENTS[payment_id] = {
        "status": "created",
        "amount": amount,
    }

    return {
        "status": "success",
        "payment_id": payment_id,
        "amount": amount,
        "message": "Payment created",
    }


@mcp.tool()
def refund_payment(payment_id: str):
    payment = PAYMENTS.get(payment_id)

    if not payment:
        return {
            "status": "error",
            "message": "Payment not found",
        }

    if payment["status"] == "refunded" and not VULNS.get("allow_double_refund"):
        return {
            "status": "error",
            "message": "Payment already refunded",
        }

    payment["status"] = "refunded"

    return {
        "status": "success",
        "payment_id": payment_id,
        "message": "Payment refunded",
    }


if __name__ == "__main__":
    import sys
    import asyncio

    if not sys.stdin.isatty():
        sys.stdout = sys.stderr
        asyncio.run(mcp.run_stdio_async())
    else:
        mcp.run()
