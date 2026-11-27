"""GuardrailHookService — passive webhook hook runner for FinBot Labs.

Loads config, calls user webhook (sync-wait up to deadline), parses verdict,
emits events via emit_agent_event(agent_name="guardrail"). Never gates
execution on the verdict.
"""

import hashlib
import hmac
import json
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
    def _truncate_str_field(
        envelope: HookEnvelope,
        envelope_data: dict[str, Any],
        assign: Any,
        value: str,
        budget: int,
    ) -> bytes:
        """Binary-search the longest prefix of `value` whose serialized envelope fits `budget`."""
        lo, hi = 0, len(value)
        best: bytes | None = None
        while lo <= hi:
            mid = (lo + hi) // 2
            assign(value[:mid])
            candidate = envelope.model_copy(update=envelope_data).model_dump_json().encode()
            if len(candidate) <= budget:
                best = candidate
                lo = mid + 1
            else:
                hi = mid - 1
        if best is not None:
            assign(value[:hi])
            return best
        assign("")
        return envelope.model_copy(update=envelope_data).model_dump_json().encode()

    @classmethod
    def _serialize_bounded_envelope(
        cls, envelope: HookEnvelope, max_payload: int
    ) -> tuple[bytes, bool, int]:
        """Serialize `envelope` as valid JSON fitting within `max_payload` bytes."""
        body_bytes = envelope.model_dump_json().encode()
        original_size = len(body_bytes)
        if original_size <= max_payload:
            return body_bytes, False, original_size

        envelope_data = envelope.model_dump()

        # 1. Shrink large string fields (response / result / prompt).
        for field in ("model_output", "tool_result", "user_message"):
            val = envelope_data.get(field)
            if isinstance(val, str) and val and len(body_bytes) > max_payload:
                body_bytes = cls._truncate_str_field(
                    envelope,
                    envelope_data,
                    lambda s, f=field: envelope_data.__setitem__(f, s),
                    val,
                    max_payload,
                )

        # 2. Shrink tool_arguments (before_tool / after_tool payloads).
        tool_args = envelope_data.get("tool_arguments")
        if isinstance(tool_args, dict) and tool_args and len(body_bytes) > max_payload:
            args = dict(tool_args)
            envelope_data["tool_arguments"] = args
            # Trim largest string values first so small metadata keys stay intact.
            str_keys = sorted(
                (k for k, v in args.items() if isinstance(v, str) and v),
                key=lambda k: len(args[k]),
                reverse=True,
            )
            for key in str_keys:
                if len(body_bytes) <= max_payload:
                    break
                body_bytes = cls._truncate_str_field(
                    envelope,
                    envelope_data,
                    lambda s, k=key: args.__setitem__(k, s),
                    args[key],
                    max_payload,
                )

            if len(body_bytes) > max_payload:
                for marker in ({"_truncated": True}, {}, None):
                    envelope_data["tool_arguments"] = marker
                    body_bytes = (
                        envelope.model_copy(update=envelope_data).model_dump_json().encode()
                    )
                    if len(body_bytes) <= max_payload:
                        break

        # 3. Minimal valid JSON fallback if envelope metadata itself exceeds max_payload.
        if len(body_bytes) > max_payload:
            for field in (
                "model_output",
                "tool_result",
                "user_message",
                "tool_arguments",
                "model",
                "tool_source",
                "tool_name",
            ):
                envelope_data[field] = None
            body_bytes = envelope.model_copy(update=envelope_data).model_dump_json().encode()

        if len(body_bytes) > max_payload:
            minimal = json.dumps(
                {"hook_kind": envelope.hook_kind.value, "truncated": True}
            ).encode()
            if len(minimal) <= max_payload:
                body_bytes = minimal
            else:
                body_bytes = b'{"truncated":true}'

        return body_bytes, True, original_size

    @staticmethod
    def _sign_payload(body: bytes, secret: str, timestamp: str) -> str:
        """HMAC-SHA256 of 'timestamp.body' using the stored secret."""
        message = f"{timestamp}.".encode() + body
        return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()

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
            return HookOutcome.no_config if not self._config else HookOutcome.hook_disabled

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
        body_bytes, was_truncated, original_size = self._serialize_bounded_envelope(
            envelope, max_payload
        )
        if was_truncated:
            logger.info(
                "guardrail payload truncated (field-level): %d -> %d bytes, hook=%s tool=%s",
                original_size,
                len(body_bytes),
                kind.value,
                tool_name,
            )

        signature = self._sign_payload(body_bytes, config.signing_secret, timestamp)

        headers = {
            "Content-Type": "application/json",
            "X-Guardrail-Signature": signature,
            "X-Guardrail-Timestamp": timestamp,
        }
        if was_truncated:
            headers["X-Guardrail-Truncated"] = "true"
            headers["X-Guardrail-Full-Size"] = str(original_size)

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
