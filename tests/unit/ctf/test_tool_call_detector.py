"""Unit tests for ToolCallDetector primitive."""

import pytest

from finbot.ctf.detectors.primitives.tool_call import ToolCallDetector
from finbot.ctf.detectors.registry import create_detector


class TestToolCallDetectorConfigValidation:
    """Tests for ToolCallDetector configuration validation."""

    def test_registry_lookup(self):
        detector = create_detector(
            "ToolCallDetector",
            "test_chal",
            {"tool_name": "transfer_funds"},
        )
        assert detector is not None
        assert isinstance(detector, ToolCallDetector)

    def test_valid_minimal_config(self):
        detector = ToolCallDetector("chal_1", {"tool_name": "execute_query"})
        assert detector.config["tool_name"] == "execute_query"

    def test_valid_comprehensive_config(self):
        config = {
            "tool_name": "create_transfer",
            "parameters": {
                "amount": {"gt": 100, "lte": 50000},
                "currency": {"equals": "USD"},
                "memo": {"contains": "urgent"},
                "vendor_id": {"exists": True},
                "status": {"in": ["pending", "approved"]},
                "reference": {"matches": r"^TRX-\d+$"},
            },
            "require_success": True,
            "event_types": ["agent.*.tool_call_success"],
        }
        detector = ToolCallDetector("chal_comp", config)
        assert detector.config["require_success"] is True

    def test_missing_tool_name_raises(self):
        with pytest.raises(ValueError, match="ToolCallDetector requires 'tool_name' config"):
            ToolCallDetector("chal_err", {})

    @pytest.mark.parametrize("invalid_tool_name", ["", "   ", None, 123, []])
    def test_invalid_tool_name_raises(self, invalid_tool_name):
        with pytest.raises(ValueError, match="tool_name must be a non-empty string"):
            ToolCallDetector("chal_err", {"tool_name": invalid_tool_name})

    @pytest.mark.parametrize("invalid_params", ["invalid_type", 123, [1, 2]])
    def test_non_dict_parameters_raises(self, invalid_params):
        with pytest.raises(ValueError, match="parameters must be a dict"):
            ToolCallDetector(
                "chal_err",
                {"tool_name": "valid_tool", "parameters": invalid_params},
            )

    def test_unsupported_operator_raises(self):
        with pytest.raises(
            ValueError, match="Unsupported operator 'unknown_op' for parameter 'amount'"
        ):
            ToolCallDetector(
                "chal_err",
                {
                    "tool_name": "valid_tool",
                    "parameters": {"amount": {"unknown_op": 100}},
                },
            )

    @pytest.mark.parametrize("invalid_require_success", ["true", 1, "yes", []])
    def test_invalid_require_success_raises(self, invalid_require_success):
        with pytest.raises(ValueError, match="require_success must be a boolean"):
            ToolCallDetector(
                "chal_err",
                {
                    "tool_name": "valid_tool",
                    "require_success": invalid_require_success,
                },
            )

    @pytest.mark.parametrize("invalid_event_types", ["agent.*", [123], {"a": "b"}])
    def test_invalid_event_types_raises(self, invalid_event_types):
        with pytest.raises(ValueError, match="event_types must be a list of strings"):
            ToolCallDetector(
                "chal_err",
                {
                    "tool_name": "valid_tool",
                    "event_types": invalid_event_types,
                },
            )


class TestToolCallDetectorEventRouting:
    """Tests for event types matching and routing."""

    def test_default_event_types(self):
        detector = ToolCallDetector("chal_route", {"tool_name": "my_tool"})
        types = detector.get_relevant_event_types()
        assert "agent.*.tool_call_success" in types
        assert "agent.*.mcp_tool_call_success" in types

    def test_custom_event_types_override(self):
        detector = ToolCallDetector(
            "chal_custom",
            {
                "tool_name": "my_tool",
                "event_types": ["custom.event.type"],
            },
        )
        assert detector.get_relevant_event_types() == ["custom.event.type"]

    def test_matches_event_type_wildcard(self):
        detector = ToolCallDetector("chal_wild", {"tool_name": "my_tool"})
        assert detector.matches_event_type("agent.invoice_agent.tool_call_success")
        assert detector.matches_event_type("agent.systemutils.mcp_tool_call_failure")
        assert not detector.matches_event_type("business.vendor.created")


class TestToolCallDetectorOperators:
    """Unit tests for individual parameter condition operators in _check_condition."""

    @pytest.fixture
    def detector(self):
        return ToolCallDetector("test_chal", {"tool_name": "test_tool"})

    def test_direct_value_equals(self, detector):
        assert detector._check_condition("active", "active") is True
        assert detector._check_condition("active", "inactive") is False
        assert detector._check_condition(42, 42) is True
        assert detector._check_condition(None, None) is True
        assert detector._check_condition(None, "active") is False

    def test_equals_and_eq_operators(self, detector):
        assert detector._check_condition("abc", {"equals": "abc"}) is True
        assert detector._check_condition("abc", {"equals": "def"}) is False
        assert detector._check_condition(100, {"eq": 100}) is True
        assert detector._check_condition(100, {"eq": 200}) is False
        assert detector._check_condition(None, {"equals": "abc"}) is False

    def test_contains_case_insensitivity(self, detector):
        # Case insensitive on both actual and expected
        assert detector._check_condition("amount in USD", {"contains": "USD"}) is True
        assert detector._check_condition("amount in usd", {"contains": "USD"}) is True
        assert detector._check_condition("amount in USD", {"contains": "usd"}) is True
        assert detector._check_condition("EUR transfer", {"contains": "USD"}) is False

    def test_contains_with_non_string_types(self, detector):
        # Integer expected and string actual
        assert detector._check_condition("account_12345_verified", {"contains": 12345}) is True
        # Integer actual and integer expected
        assert detector._check_condition(987654, {"contains": 765}) is True
        # None actual
        assert detector._check_condition(None, {"contains": "anything"}) is False

    @pytest.mark.parametrize(
        "actual,expected,op,expected_result",
        [
            (150, 100, "gt", True),
            (100, 100, "gt", False),
            (50, 100, "gt", False),
            (100, 100, "gte", True),
            (101, 100, "gte", True),
            (99, 100, "gte", False),
            (50, 100, "lt", True),
            (100, 100, "lt", False),
            (150, 100, "lt", False),
            (100, 100, "lte", True),
            (99, 100, "lte", True),
            (101, 100, "lte", False),
            ("150.5", 100, "gt", True),
            (150, "100.0", "gt", True),
            (-5, 0, "lt", True),
            (0.001, 0, "gt", True),
        ],
    )
    def test_numeric_comparisons(self, detector, actual, expected, op, expected_result):
        assert detector._check_condition(actual, {op: expected}) is expected_result

    @pytest.mark.parametrize("invalid_num", ["not_a_number", {}, [], "", "NaN-invalid"])
    def test_numeric_comparisons_invalid_inputs_do_not_crash(self, detector, invalid_num):
        assert detector._check_condition(invalid_num, {"gt": 100}) is False
        assert detector._check_condition(invalid_num, {"gte": 100}) is False
        assert detector._check_condition(invalid_num, {"lt": 100}) is False
        assert detector._check_condition(invalid_num, {"lte": 100}) is False
        assert detector._check_condition(150, {"gt": invalid_num}) is False
        assert detector._check_condition(None, {"gt": 100}) is False

    def test_in_and_not_in_operators(self, detector):
        assert detector._check_condition("admin", {"in": ["admin", "root"]}) is True
        assert detector._check_condition("viewer", {"in": ["admin", "root"]}) is False
        assert detector._check_condition("viewer", {"not_in": ["admin", "root"]}) is True
        assert detector._check_condition("admin", {"not_in": ["admin", "root"]}) is False
        assert detector._check_condition(1, {"in": [1, 2, 3]}) is True
        # Malformed non-iterable expected should return False rather than raising TypeError
        assert detector._check_condition("admin", {"in": 12345}) is False
        assert detector._check_condition("admin", {"not_in": 12345}) is False
        assert detector._check_condition(None, {"in": ["admin"]}) is False

    def test_exists_operator(self, detector):
        assert detector._check_condition("present", {"exists": True}) is True
        assert detector._check_condition("", {"exists": True}) is True
        assert detector._check_condition(0, {"exists": True}) is True
        assert detector._check_condition(None, {"exists": True}) is False
        assert detector._check_condition(None, {"exists": False}) is True
        assert detector._check_condition("present", {"exists": False}) is False

    def test_matches_regex_operator(self, detector):
        assert detector._check_condition("INV-2026-001", {"matches": r"^inv-\d{4}-\d+$"}) is True
        assert detector._check_condition("INVALID", {"matches": r"^inv-\d{4}-\d+$"}) is False
        assert detector._check_condition(None, {"matches": r".*"}) is False
        # Invalid regex syntax should return False rather than raising re.error
        assert detector._check_condition("text", {"matches": "[unclosed_bracket"}) is False

    def test_multi_operator_condition(self, detector):
        condition = {"gte": 10, "lte": 50}
        assert detector._check_condition(25, condition) is True
        assert detector._check_condition(10, condition) is True
        assert detector._check_condition(50, condition) is True
        assert detector._check_condition(5, condition) is False
        assert detector._check_condition(60, condition) is False


class TestToolCallDetectorCheckEvent:
    """End-to-end event checking tests across native and MCP payloads."""

    @pytest.mark.asyncio
    async def test_tool_name_mismatch(self):
        detector = ToolCallDetector("chal", {"tool_name": "approve_invoice"})
        event = {"tool_name": "reject_invoice", "event_type": "agent.tool_call_success"}
        result = await detector.check_event(event, db=None)
        assert result.detected is False
        assert "Tool mismatch" in (result.message or "")

    @pytest.mark.asyncio
    async def test_require_success_enforcement(self):
        detector = ToolCallDetector(
            "chal",
            {"tool_name": "execute_script", "require_success": True},
        )
        fail_event = {
            "tool_name": "execute_script",
            "event_type": "agent.systemutils.mcp_tool_call_failure",
        }
        res_fail = await detector.check_event(fail_event, db=None)
        assert res_fail.detected is False
        assert "not successful" in (res_fail.message or "")

        success_event = {
            "tool_name": "execute_script",
            "event_type": "agent.systemutils.mcp_tool_call_success",
        }
        res_succ = await detector.check_event(success_event, db=None)
        assert res_succ.detected is True

    @pytest.mark.asyncio
    async def test_native_payload_as_dict(self):
        detector = ToolCallDetector(
            "chal",
            {
                "tool_name": "update_vendor",
                "parameters": {"vendor_id": 42, "trust_level": {"in": ["high", "critical"]}},
            },
        )
        event = {
            "tool_name": "update_vendor",
            "event_type": "agent.tool_call_success",
            "tool_args": {"vendor_id": 42, "trust_level": "high"},
        }
        result = await detector.check_event(event, db=None)
        assert result.detected is True
        assert result.evidence["tool_name"] == "update_vendor"

    @pytest.mark.asyncio
    async def test_native_payload_as_json_string(self):
        detector = ToolCallDetector(
            "chal",
            {
                "tool_name": "update_vendor",
                "parameters": {"vendor_id": 42},
            },
        )
        event = {
            "tool_name": "update_vendor",
            "event_type": "agent.tool_call_success",
            "tool_args": '{"vendor_id": 42, "extra": "data"}',
        }
        result = await detector.check_event(event, db=None)
        assert result.detected is True
        assert result.evidence["tool_args"]["vendor_id"] == 42

    @pytest.mark.asyncio
    async def test_mcp_payload_as_dict(self):
        detector = ToolCallDetector(
            "chal",
            {
                "tool_name": "create_transfer",
                "parameters": {
                    "amount": {"gt": 1000},
                    "currency": {"contains": "USD"},
                },
            },
        )
        event = {
            "tool_name": "create_transfer",
            "event_type": "agent.finstripe.mcp_tool_call_success",
            "tool_arguments": {"amount": 5000, "currency": "Amount in USD"},
        }
        result = await detector.check_event(event, db=None)
        assert result.detected is True

    @pytest.mark.asyncio
    async def test_mcp_payload_as_json_string(self):
        detector = ToolCallDetector(
            "chal",
            {
                "tool_name": "delete_file",
                "parameters": {"file_id": {"gt": 0}},
            },
        )
        event = {
            "tool_name": "delete_file",
            "event_type": "agent.findrive.mcp_tool_call_success",
            "tool_arguments": '{"file_id": 99}',
        }
        result = await detector.check_event(event, db=None)
        assert result.detected is True
        assert result.evidence["tool_args"]["file_id"] == 99

    @pytest.mark.asyncio
    async def test_missing_argument_key_fails_match(self):
        detector = ToolCallDetector(
            "chal",
            {
                "tool_name": "transfer",
                "parameters": {"amount": {"gt": 0}, "required_memo": {"exists": True}},
            },
        )
        # Event has amount, but required_memo key is missing entirely
        event = {
            "tool_name": "transfer",
            "event_type": "agent.tool_call_success",
            "tool_args": {"amount": 500},
        }
        result = await detector.check_event(event, db=None)
        assert result.detected is False
        assert result.confidence == 0.5  # 1 of 2 matched
        assert "Parameter conditions not met" in (result.message or "")

    @pytest.mark.asyncio
    async def test_malformed_json_arguments_fallback_to_empty(self):
        detector = ToolCallDetector(
            "chal",
            {
                "tool_name": "transfer",
                "parameters": {"amount": {"gt": 0}},
            },
        )
        event = {
            "tool_name": "transfer",
            "event_type": "agent.tool_call_success",
            "tool_args": "{not_valid_json...",
        }
        result = await detector.check_event(event, db=None)
        assert result.detected is False
        assert result.evidence["checked"]["all_matched"] is False

    @pytest.mark.asyncio
    async def test_no_parameters_config_matches_tool_call_alone(self):
        detector = ToolCallDetector("chal", {"tool_name": "any_call"})
        event = {
            "tool_name": "any_call",
            "event_type": "agent.tool_call_success",
            "tool_args": {"any": "arg"},
        }
        result = await detector.check_event(event, db=None)
        assert result.detected is True
