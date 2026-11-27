"""GuardrailHookService — passive webhook hook runner for FinBot Labs.

Loads config, calls user webhook (sync-wait up to deadline), parses verdict,
emits events via emit_agent_event(agent_name="guardrail"). Never gates
execution on the verdict.
"""

import hashlib
import hmac
import logging
import time
from datetime import UTC, datetime
from typing import Any

import httpx
from pydantic import ValidationError

from finbot.config import settings
from finbot.core.auth.session import SessionContext
from finbot.core.data.database import db_session
from finbot.core.data.models import LabsGuardrailConfig
from finbot.core.data.repositories import LabsGuardrailConfigRepository
from finbot.core.messaging import event_bus
from finbot.guardrails.schemas import (
    HookEnvelope,
    HookKind,
    HookOutcome,
    WebhookVerdict,
)

logger = logging.getLogger(__name__)


class GuardrailHookService:
    """Passive guardrail hook runner.

    One instance per chat session (ChatAssistantBase). Caches the user's
    LabsGuardrailConfig for the session lifetime so we don't hit the DB
    on every hook invocation.
    """

    def __init__(
        self,
        session_context: SessionContext,
        workflow_id: str | None = None,
    ):
        self._session_context = session_context
        self._workflow_id = workflow_id or ""
        self._config: LabsGuardrailConfig | None = None
        self._config_loaded = False

    def _load_config(self) -> LabsGuardrailConfig | None:
        """Load and cache config from DB (once per session)."""
        if self._config_loaded:
            return self._config
        with db_session() as db:
            repo = LabsGuardrailConfigRepository(db, self._session_context)
            config = repo.get_for_current_user()
            if config:
                # Detach from session so we can read attrs after close
                db.expunge(config)
            self._config = config
        self._config_loaded = True
        return self._config

    def _is_hook_enabled(self, kind: HookKind) -> bool:
        config = self._load_config()
        if not config or not config.enabled:
            return False
        hooks = config.get_hooks()
        return hooks.get(kind.value, False)

    @staticmethod
    def _sign_payload(body: bytes, secret: str, timestamp: str) -> str:
        """HMAC-SHA256 of 'timestamp.body' using the stored secret."""
        message = f"{timestamp}.".encode() + body
        return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()

    @staticmethod
    def _truncate_payload(envelope: HookEnvelope, max_bytes: int) -> bytes:
        """Truncate envelope fields while preserving valid JSON output."""
        body_bytes = envelope.model_dump_json().encode()
        if len(body_bytes) <= max_bytes:
            return body_bytes

        # Truncate largest text fields first
        for field in ("tool_result", "model_output", "user_message"):
            val = getattr(envelope, field, None)
            if val and isinstance(val, str):
                excess = len(body_bytes) - max_bytes
                suffix = "...[truncated]"
                allowed = max(0, len(val) - excess - len(suffix) - 16)
                setattr(envelope, field, val[:allowed] + suffix if allowed > 0 else suffix)
                body_bytes = envelope.model_dump_json().encode()
                if len(body_bytes) <= max_bytes:
                    return body_bytes

        # Truncate string values in tool_arguments if still over
        if envelope.tool_arguments and isinstance(envelope.tool_arguments, dict):
            excess = len(body_bytes) - max_bytes
            truncated_args = {}
            for k, v in envelope.tool_arguments.items():
                if isinstance(v, str) and len(v) > 50:
                    allowed = max(0, len(v) - excess - 20)
                    truncated_args[k] = v[:allowed] + "...[truncated]"
                else:
                    truncated_args[k] = v
            envelope.tool_arguments = truncated_args
            body_bytes = envelope.model_dump_json().encode()
            if len(body_bytes) <= max_bytes:
                return body_bytes

        # Fallback to minimal envelope if still over max_bytes
        if len(body_bytes) > max_bytes:
            fallback = HookEnvelope(
                schema_version=envelope.schema_version,
                hook_kind=envelope.hook_kind,
                session_id=envelope.session_id,
                workflow_id=envelope.workflow_id,
                tool_name=envelope.tool_name,
                tool_source=envelope.tool_source,
                timestamp=envelope.timestamp,
                tool_result="[truncated]" if envelope.tool_result else None,
                model_output="[truncated]" if envelope.model_output else None,
                user_message="[truncated]" if envelope.user_message else None,
            )
            return fallback.model_dump_json().encode()

        return body_bytes

    async def invoke(
        self,
        kind: HookKind,
        *,
        tool_name: str | None = None,
        tool_source: str | None = None,
        tool_arguments: dict[str, Any] | None = None,
        tool_result: str | None = None,
        model: str | None = None,
        user_message: str | None = None,
        model_output: str | None = None,
    ) -> HookOutcome:
        """Fire a passive guardrail hook.

        Returns the outcome for informational purposes — callers must
        NOT branch on the outcome (execution always proceeds).
        """
        if not self._is_hook_enabled(kind):
            return (
                HookOutcome.no_config if not self._config else HookOutcome.hook_disabled
            )

        config = self._config
        assert config is not None  # _is_hook_enabled guarantees this

        timestamp = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        envelope = HookEnvelope(
            hook_kind=kind,
            session_id=self._session_context.session_id,
            workflow_id=self._workflow_id,
            tool_name=tool_name,
            tool_source=tool_source,
            tool_arguments=tool_arguments,
            tool_result=tool_result,
            model=model,
            user_message=user_message,
            model_output=model_output,
            timestamp=timestamp,
        )

        max_payload = settings.LABS_GUARDRAIL_MAX_PAYLOAD_BYTES
        initial_bytes = envelope.model_dump_json().encode()
        if len(initial_bytes) > max_payload:
            body_bytes = self._truncate_payload(envelope, max_payload)
            logger.info(
                "guardrail payload truncated: %d -> %d bytes, hook=%s tool=%s",
                len(initial_bytes),
                len(body_bytes),
                kind.value,
                tool_name,
            )
        else:
            body_bytes = initial_bytes

        signature = self._sign_payload(body_bytes, config.signing_secret, timestamp)

        headers = {
            "Content-Type": "application/json",
            "X-Guardrail-Signature": signature,
            "X-Guardrail-Timestamp": timestamp,
        }

        start = time.monotonic()
        outcome: HookOutcome
        verdict_str: str | None = None
        reason: str | None = None
        http_status: int | None = None
        error_detail: str | None = None

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    config.webhook_url,
                    content=body_bytes,
                    headers=headers,
                    timeout=config.timeout_seconds,
                )
            http_status = resp.status_code
            if resp.status_code == 200:
                try:
                    parsed = WebhookVerdict.model_validate_json(resp.content)
                    verdict_str = parsed.verdict
                    reason = parsed.reason
                    outcome = HookOutcome.completed
                except (ValidationError, ValueError) as exc:
                    outcome = HookOutcome.invalid_verdict
                    error_detail = str(exc)
            else:
                outcome = HookOutcome.error
                error_detail = f"HTTP {resp.status_code}"

        except httpx.TimeoutException:
            outcome = HookOutcome.timeout
            error_detail = f"Timeout after {config.timeout_seconds}s"
        except Exception as exc:  # pylint: disable=broad-exception-caught
            outcome = HookOutcome.error
            error_detail = str(exc)

        latency_ms = int((time.monotonic() - start) * 1000)

        logger.info(
            "guardrail hook=%s outcome=%s verdict=%s latency_ms=%d tool=%s user=%s",
            kind.value,
            outcome.value,
            verdict_str,
            latency_ms,
            tool_name,
            self._session_context.user_id[:8],
        )

        await self._emit_event(
            kind=kind,
            outcome=outcome,
            verdict=verdict_str,
            reason=reason,
            latency_ms=latency_ms,
            http_status=http_status,
            error_detail=error_detail,
            tool_name=tool_name,
            tool_source=tool_source,
            tool_arguments=tool_arguments,
            model=model,
        )

        return outcome

    async def _emit_event(
        self,
        *,
        kind: HookKind,
        outcome: HookOutcome,
        verdict: str | None,
        reason: str | None,
        latency_ms: int,
        http_status: int | None,
        error_detail: str | None,
        tool_name: str | None,
        tool_source: str | None,
        tool_arguments: dict[str, Any] | None,
        model: str | None,
    ) -> None:
        """Emit guardrail event via the existing agent event stream."""
        event_type = f"webhook_{outcome.value}"

        event_data: dict[str, Any] = {
            "hook_kind": kind.value,
            "outcome": outcome.value,
            "latency_ms": latency_ms,
        }
        if verdict is not None:
            event_data["verdict"] = verdict
        if reason is not None:
            event_data["reason"] = reason
        if http_status is not None:
            event_data["http_status"] = http_status
        if error_detail is not None:
            event_data["error_detail"] = error_detail
        if tool_name is not None:
            event_data["tool_name"] = tool_name
        if tool_source is not None:
            event_data["tool_source"] = tool_source
        if tool_arguments is not None:
            event_data["tool_arguments"] = tool_arguments
        if model is not None:
            event_data["model"] = model

        summary_parts = [f"Guardrail {kind.value}"]
        if verdict:
            summary_parts.append(f"→ {verdict}")
        elif outcome != HookOutcome.completed:
            summary_parts.append(f"→ {outcome.value}")
        summary_parts.append(f"({latency_ms}ms)")

        try:
            await event_bus.emit_agent_event(
                agent_name="guardrail",
                event_type=event_type,
                event_subtype="guardrail",
                event_data=event_data,
                session_context=self._session_context,
                workflow_id=self._workflow_id,
                summary=" ".join(summary_parts),
            )
        except Exception:  # pylint: disable=broad-exception-caught
            logger.warning("Failed to emit guardrail event", exc_info=True)
