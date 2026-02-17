import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from datetime import datetime, timedelta, UTC
from finbot.agents.specialized.fraud_detection import RiskAnalyzerAgent
from finbot.core.auth.session import SessionContext

@pytest.fixture
def session_context():
    return SessionContext(
        session_id="test-session",
        user_id="test-user",
        is_temporary=True,
        namespace="test-ns",
        created_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )

@pytest.mark.asyncio
async def test_risk_analyzer_high_risk(session_context):
    # Patch the LLM client to return a high risk result
    with patch("finbot.core.llm.contextual_client.ContextualLLMClient.chat", new_callable=AsyncMock) as mock_chat:
        mock_chat.return_value.content = '{"risk": "high", "risk_reasons": ["Duplicate invoice", "Urgent language"]}'
        agent = RiskAnalyzerAgent(session_context=session_context)
        context = {
            "invoice_id": "INV-001",
            "invoice": {"vendor": "AcmeCorp", "amount": 12000, "currency": "USD", "account": "123-456", "payment_method": "wire", "created_at": "2026-02-03T10:00:00Z"},
            "historical": {}
        }
        result = await agent.run(context.copy())
        assert result["risk"] == "high"
        assert "Duplicate invoice" in result["risk_reasons"]
        agent.rollback(result)
        assert result["risk"] is None
        assert result["risk_reasons"] == []

@pytest.mark.asyncio
async def test_risk_analyzer_low_risk(session_context):
    with patch("finbot.core.llm.contextual_client.ContextualLLMClient.chat", new_callable=AsyncMock) as mock_chat:
        mock_chat.return_value.content = '{"risk": "low", "risk_reasons": []}'
        agent = RiskAnalyzerAgent(session_context=session_context)
        context = {
            "invoice_id": "INV-002",
            "invoice": {"vendor": "AcmeCorp", "amount": 4000, "currency": "USD", "account": "123-456", "payment_method": "wire", "created_at": "2026-02-03T10:00:00Z"},
            "historical": {}
        }
        result = await agent.run(context.copy())
        assert result["risk"] == "low"
        assert result["risk_reasons"] == []
        agent.rollback(result)
        assert result["risk"] is None
        assert result["risk_reasons"] == []
