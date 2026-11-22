# ============================================================
# File: finbot/aegis/__init__.py
# Purpose: Public exports for FinBot-AEGIS runtime security layer
# Author: Jean Francois Regis MUKIZA
# GSoC Week: 1
# OWASP Category: ASI01–ASI10 (platform-wide)
# ============================================================
"""FinBot-AEGIS: runtime security layer for OWASP FinBot CTF."""

# Only the subpackages shipped in this change are imported here. The runtime
# enforcement modules (IntentGate, SentinelStream, AegisEnforcementService, ...)
# come with the AEGIS phase-1 work and are exported once they are on main.
from finbot.aegis import harness, telemetry

__all__ = ["harness", "telemetry"]
