"""Tool Call Detector

Detects specific tool calls with optional parameter matching.
"""

import json
import logging
import re
from typing import Any

from sqlalchemy.orm import Session

from finbot.ctf.detectors.base import BaseDetector
from finbot.ctf.detectors.registry import register_detector
from finbot.ctf.detectors.result import DetectionResult

logger = logging.getLogger(__name__)


@register_detector("ToolCallDetector")
class ToolCallDetector(BaseDetector):
    """Detects tool calls matching specified criteria.

    Works with both native tool calls (tool_args) and MCP tool calls
    (tool_arguments). Default event_types cover both; override via config
    to restrict to one or the other.

    Configuration:
        tool_name: str - Tool name to match (required)
        parameters: dict - Optional parameter conditions
            Each key is a parameter name, value is a condition:
            - Direct value: exact match
            - Dict with operator: {"gt": 100}, {"in": ["a", "b"]}, {"exists": true}
        require_success: bool - Only match successful calls (default: False)
        event_types: list[str] - Override default event types

    Supported operators for parameters:
        equals (or direct value), gt, gte, lt, lte, in, not_in,
        contains, exists, matches (regex)

    Example YAML (native tool):
        detector_class: ToolCallDetector
        detector_config:
          tool_name: "update_vendor"
          parameters:
            trust_level:
              in: ["high", "critical"]
          require_success: true

    Example YAML (MCP tool):
        detector_class: ToolCallDetector
        detector_config:
          tool_name: "execute_script"
          event_types: ["agent.*.mcp_tool_call_success"]
          parameters:
            script_content:
              matches: "/dev/tcp|reverse.shell"
          require_success: true
    """

    SUPPORTED_OPERATORS: set[str] = {
        "equals",
        "eq",
        "gt",
        "gte",
        "lt",
        "lte",
        "in",
        "not_in",
        "contains",
        "exists",
        "matches",
    }

    def _validate_config(self) -> None:
        if "tool_name" not in self.config:
            raise ValueError("ToolCallDetector requires 'tool_name' config")

        tool_name = self.config["tool_name"]
        if not isinstance(tool_name, str) or not tool_name.strip():
            raise ValueError("tool_name must be a non-empty string")

        if "parameters" in self.config and self.config["parameters"] is not None:
            params = self.config["parameters"]
            if not isinstance(params, dict):
                raise ValueError("parameters must be a dict")
            for param_name, condition in params.items():
                if isinstance(condition, dict):
                    for operator in condition.keys():
                        if (
                            not isinstance(operator, str)
                            or operator.lower() not in self.SUPPORTED_OPERATORS
                        ):
                            raise ValueError(
                                f"Unsupported operator '{operator}' for parameter '{param_name}'. "
                                f"Supported operators: {sorted(self.SUPPORTED_OPERATORS)}"
                            )

        if "require_success" in self.config and self.config["require_success"] is not None:
            if not isinstance(self.config["require_success"], bool):
                raise ValueError("require_success must be a boolean")

        if "event_types" in self.config and self.config["event_types"] is not None:
            event_types = self.config["event_types"]
            if not isinstance(event_types, list) or not all(
                isinstance(et, str) for et in event_types
            ):
                raise ValueError("event_types must be a list of strings")

    def get_relevant_event_types(self) -> list[str]:
        """Listen to both native and MCP tool call events."""
        return self.config.get(
            "event_types",
            [
                "agent.*.tool_call_success",
                "agent.*.tool_call_start",
                "agent.*.tool_call_failure",
                "agent.*.mcp_tool_call_success",
                "agent.*.mcp_tool_call_start",
                "agent.*.mcp_tool_call_failure",
            ],
        )

    async def check_event(self, event: dict[str, Any], db: Session) -> DetectionResult:
        """Check if event is a matching tool call.
        Only needs the current event, db is unused.
        """
        target_tool = self.config["tool_name"]
        param_conditions = self.config.get("parameters", {})
        require_success = self.config.get("require_success", False)

        # Check tool name
        event_tool = event.get("tool_name")
        if event_tool != target_tool:
            return DetectionResult(
                detected=False,
                message=f"Tool mismatch: expected '{target_tool}', got '{event_tool}'",
            )

        # Check success requirement
        if require_success:
            event_type = event.get("event_type", "")
            if "success" not in event_type:
                return DetectionResult(
                    detected=False,
                    message=f"Tool call not successful: {event_type}",
                )

        # Check parameter conditions
        if param_conditions:
            tool_args = self._extract_tool_args(event)

            param_results = self._check_parameters(tool_args, param_conditions)

            if not param_results["all_matched"]:
                return DetectionResult(
                    detected=False,
                    confidence=param_results["match_ratio"],
                    message=f"Parameter conditions not met: {param_results['failed']}",
                    evidence={"checked": param_results},
                )

        return DetectionResult(
            detected=True,
            confidence=1.0,
            message=f"Tool call detected: {target_tool}",
            evidence={
                "tool_name": target_tool,
                "tool_args": self._extract_tool_args(event),
                "event_type": event.get("event_type"),
            },
        )

    @staticmethod
    def _extract_tool_args(event: dict[str, Any]) -> dict:
        """Extract tool arguments from native (tool_args) or MCP (tool_arguments) events."""
        raw = event.get("tool_args") or event.get("tool_arguments") or {}
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except (json.JSONDecodeError, ValueError):
                raw = {}
        return raw if isinstance(raw, dict) else {}

    def _check_parameters(self, tool_args: dict, conditions: dict) -> dict[str, Any]:
        """Check if tool arguments match conditions."""
        matched = []
        failed = []

        for param_name, condition in conditions.items():
            actual_value = tool_args.get(param_name)

            if self._check_condition(actual_value, condition):
                matched.append(param_name)
            else:
                failed.append(
                    {
                        "param": param_name,
                        "expected": condition,
                        "actual": actual_value,
                    }
                )

        total = len(conditions)
        return {
            "all_matched": len(failed) == 0,
            "matched": matched,
            "failed": failed,
            "match_ratio": len(matched) / total if total > 0 else 1.0,
        }

    @staticmethod
    def _compare_numeric(actual: Any, expected: Any, op: str) -> bool:
        """Safely compare numeric values for gt, gte, lt, lte operators."""
        try:
            act_num = float(actual)
            exp_num = float(expected)
        except (ValueError, TypeError):
            return False

        if op == "gt":
            return act_num > exp_num
        if op == "gte":
            return act_num >= exp_num
        if op == "lt":
            return act_num < exp_num
        if op == "lte":
            return act_num <= exp_num
        return False

    def _check_condition(self, actual: Any, condition: Any) -> bool:
        """Check if actual value matches condition."""
        # Direct value comparison
        if not isinstance(condition, dict):
            return actual == condition

        # Operator-based condition
        for operator, expected in condition.items():
            op = operator.lower()

            if op == "exists":
                if (actual is not None) != bool(expected):
                    return False
                continue

            if actual is None:
                return False

            if op in ("equals", "eq"):
                if actual != expected:
                    return False
            elif op == "in":
                try:
                    if actual not in expected:
                        return False
                except TypeError:
                    return False
            elif op == "not_in":
                try:
                    if actual in expected:
                        return False
                except TypeError:
                    return False
            elif op == "contains":
                if str(expected).lower() not in str(actual).lower():
                    return False
            elif op in ("gt", "gte", "lt", "lte"):
                if not self._compare_numeric(actual, expected, op):
                    return False
            elif op == "matches":
                try:
                    if not bool(re.search(str(expected), str(actual), re.IGNORECASE)):
                        return False
                except re.error:
                    return False
            else:
                return False

        return True
