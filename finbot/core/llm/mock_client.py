"""Mock LLM Client for testing"""

import json
import logging

from finbot.core.data.models import LLMRequest, LLMResponse

logger = logging.getLogger(__name__)


class MockLLMClient:
    """Mock LLM Client for testing"""

    def __init__(self):
        self.default_model = "mock-model"
        self.default_temperature = 1.0

    async def chat(
        self,
        request: LLMRequest,
    ) -> LLMResponse:
        """Mock chat with LLM"""
        try:
            logger.info(
                "Mock LLM chat called with messages: %s, model: %s, temperature: %s",
                request.messages,
                request.model,
                request.temperature,
            )
            
            # If JSON schema is requested, return mock data matching the schema
            if request.output_json_schema:
                schema_name = request.output_json_schema.get("name", "")
                
                # Mock fraud analysis response
                if schema_name == "FraudAnalysisResult":
                    mock_response = {
                        "risk": "low",
                        "risk_reasons": [
                            "Invoice amount is within normal range",
                            "Vendor information matches records",
                            "No duplicate invoice detected"
                        ]
                    }
                    return LLMResponse(
                        content=json.dumps(mock_response),
                        provider="mock",
                        success=True,
                    )
            
            # Default mock response
            return LLMResponse(
                content="This is a mock LLM response",
                provider="mock",
                success=True,
            )
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Mock LLM chat failed: %s", e)
            raise Exception(f"Mock LLM chat failed: {e}") from e  # pylint: disable=broad-exception-raised
