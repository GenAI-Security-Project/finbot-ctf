"""LLM Judge - Uses an LLM to evaluate text against criteria and return structured scores.

Reusable component for CTF detectors and evaluators that need
semantic analysis beyond pattern matching.
"""

import json
import logging
from typing import Any

from pydantic import BaseModel

from finbot.core.data.models import LLMRequest
from finbot.core.llm.client import get_llm_client

logger = logging.getLogger(__name__)


class JudgeVerdict(BaseModel):
    """Structured result from an LLM judge evaluation."""

    score: float
    reasoning: str
    raw_response: str | None = None


JUDGE_VERDICT_SCHEMA = {
    "name": "judge_verdict",
    "schema": {
        "type": "object",
        "properties": {
            "score": {
                "type": "number",
                "description": "Score between 0 and 100",
            },
            "reasoning": {
                "type": "string",
                "description": "Explanation for the score",
            },
        },
        "required": ["score", "reasoning"],
        "additionalProperties": False,
    },
}


class LLMJudge:
    """Async LLM-based judge for semantic evaluation.

    Uses structured output (JSON schema) to get reliable score + reasoning
    from the LLM, avoiding brittle response parsing.
    """

    def __init__(
        self,
        system_prompt: str,
        model: str | None = None,
        temperature: float = 0.0,
    ):
        self.system_prompt = system_prompt
        self.model = model
        self.temperature = temperature
        self._client = get_llm_client()

    async def evaluate(
        self,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> JudgeVerdict:
        """Evaluate content using the LLM judge.

        Args:
            content: The text to evaluate (will be sent as a user message).
            metadata: Optional metadata passed to the LLM request.

        Returns:
            JudgeVerdict with score (0-100), reasoning, and raw response.

        Raises:
            ValueError: If the LLM response cannot be parsed.
        """
        request = LLMRequest(
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": content},
            ],
            model=self.model,
            temperature=self.temperature,
            output_json_schema=JUDGE_VERDICT_SCHEMA,
            metadata=metadata,
        )

        response = await self._client.chat(request)

        if not response.success or not response.content:
            logger.error("LLM judge call failed: %s", response.content)
            raise ValueError(f"LLM judge call failed: {response.content}")

        try:
            parsed = json.loads(response.content)
            return JudgeVerdict(
                score=float(parsed["score"]),
                reasoning=parsed["reasoning"],
                raw_response=response.content,
            )
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.error(
                "Failed to parse LLM judge response: %s (raw: %s)",
                e,
                response.content[:200],
            )
            raise ValueError(f"Failed to parse LLM judge response: {e}") from e
