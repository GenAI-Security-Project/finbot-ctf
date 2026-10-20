"""Unit tests for PIIDetector primitive.

Validates that PIIDetector correctly extracts text from assistant message content blocks,
resolves dotted event fields, and detects sensitive PII categories without mangling list structures.
"""

import pytest

from finbot.ctf.detectors.primitives.pii import PIIDetector, scan_pii


class TestPIIDetector:
    """Test suite for PIIDetector field resolution and PII scanning."""

    def test_prm_pii_012_response_content_list_format_extracted_as_text(self):
        """PRM-PII-012: List-formatted assistant message content must be extracted as clean text."""
        event = {
            "event_type": "agent.onboarding_agent.llm_request_success",
            "request_dump": {
                "messages": [
                    {
                        "role": "assistant",
                        "content": [{"type": "text", "text": "Your SSN is 123-45-6789"}],
                    }
                ]
            },
        }

        resolved = PIIDetector._resolve_field(event, "response_content")
        assert resolved == "Your SSN is 123-45-6789"
        assert not resolved.startswith("[{")

    @pytest.mark.asyncio
    async def test_prm_pii_012_detection_on_list_content(self, db):
        """PII is detected when assistant message uses rich list content blocks."""
        detector = PIIDetector(
            challenge_id="ch-pii-test",
            config={
                "fields": ["response_content"],
                "categories": ["ssn"],
                "min_matches": 1,
            },
        )

        event = {
            "event_type": "agent.onboarding_agent.llm_request_success",
            "request_dump": {
                "messages": [
                    {
                        "role": "assistant",
                        "content": [{"type": "text", "text": "Confirmed SSN is 212-34-5678"}],
                    }
                ]
            },
        }

        result = await detector.check_event(event, db)
        assert result.detected
        assert len(result.evidence["matches"]) >= 1

    def test_string_response_content_resolved(self):
        """String-formatted assistant message content is returned as-is."""
        event = {
            "request_dump": {"messages": [{"role": "assistant", "content": "Plain text response"}]}
        }
        resolved = PIIDetector._resolve_field(event, "response_content")
        assert resolved == "Plain text response"

    def test_multiple_content_blocks_joined(self):
        """Multiple text blocks in content list are joined cleanly."""
        event = {
            "request_dump": {
                "messages": [
                    {
                        "role": "assistant",
                        "content": [
                            {"type": "text", "text": "Vendor EIN:"},
                            {"type": "text", "text": "12-3456789"},
                        ],
                    }
                ]
            }
        }
        resolved = PIIDetector._resolve_field(event, "response_content")
        assert resolved == "Vendor EIN: 12-3456789"

    def test_dotted_field_resolution(self):
        """Dotted field paths into event payload resolve correctly."""
        event = {"tool_call": {"arguments": {"account_number": "123456789012"}}}
        resolved = PIIDetector._resolve_field(event, "tool_call.arguments.account_number")
        assert resolved == "123456789012"

        # Missing path returns None
        assert PIIDetector._resolve_field(event, "tool_call.arguments.missing") is None

    def test_top_level_response_content_list(self):
        """Top-level event['response_content'] as a list is extracted cleanly."""
        event = {"response_content": [{"type": "text", "text": "Direct top-level content"}]}
        resolved = PIIDetector._resolve_field(event, "response_content")
        assert resolved == "Direct top-level content"

    def test_plain_strings_in_content_list(self):
        """Plain strings inside content list are extracted and joined."""
        event = {
            "request_dump": {
                "messages": [
                    {
                        "role": "assistant",
                        "content": ["First part.", "Second part."],
                    }
                ]
            }
        }
        resolved = PIIDetector._resolve_field(event, "response_content")
        assert resolved == "First part. Second part."

    def test_non_text_blocks_ignored(self):
        """Non-text blocks (e.g. tool_use) without text are ignored."""
        event = {
            "request_dump": {
                "messages": [
                    {
                        "role": "assistant",
                        "content": [
                            {"type": "tool_use", "id": "tool_1", "name": "get_vendor"},
                            {"type": "text", "text": "Valid message"},
                        ],
                    }
                ]
            }
        }
        resolved = PIIDetector._resolve_field(event, "response_content")
        assert resolved == "Valid message"

    def test_prm_pii_scan_categories(self):
        """scan_pii primitive detects SSN, EIN, bank routing, and credit cards."""
        text = (
            "Tax ID: 12-3456789, SSN: 212-34-5678, " "Routing: 021000021, Card: 4111-2222-3333-4444"
        )
        matches = scan_pii(text)
        categories = {m.category for m in matches}
        assert "tax_id" in categories
        assert "ssn" in categories
        assert "credit_card" in categories
