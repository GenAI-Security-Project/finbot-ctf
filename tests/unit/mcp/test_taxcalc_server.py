"""
Unit tests for the TaxCalc MCP Server -- tax ID validation.
"""

from typing import Any

import pytest

from finbot.mcp.servers.taxcalc.server import create_taxcalc_server


@pytest.fixture
def taxcalc_server() -> Any:
    """Create a TaxCalc MCP server instance."""
    return create_taxcalc_server(session_context=None)  # type: ignore[arg-type]


# ============================================================================
# EIN Validation Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_validate_tax_id_valid_ein_hyphenated(taxcalc_server: Any) -> None:
    """EIN formatted with standard hyphen (XX-XXXXXXX) is valid."""
    res = await taxcalc_server.call_tool("validate_tax_id", {"tax_id": "12-3456789"})
    data = res.structured_content
    assert data["format_valid"] is True
    assert data["id_type"] == "EIN"
    assert data["formatted"] == "12-3456789"
    assert data["country"] == "US"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_validate_tax_id_valid_ein_raw_digits(taxcalc_server: Any) -> None:
    """Raw 9-digit string without hyphens defaults to EIN."""
    res = await taxcalc_server.call_tool("validate_tax_id", {"tax_id": "123456789"})
    data = res.structured_content
    assert data["format_valid"] is True
    assert data["id_type"] == "EIN"
    assert data["formatted"] == "12-3456789"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_validate_tax_id_valid_ein_spaced(taxcalc_server: Any) -> None:
    """EIN with spaces instead of hyphen is valid and formatted correctly."""
    res = await taxcalc_server.call_tool("validate_tax_id", {"tax_id": "98 7654321"})
    data = res.structured_content
    assert data["format_valid"] is True
    assert data["id_type"] == "EIN"
    assert data["formatted"] == "98-7654321"


# ============================================================================
# SSN Validation Tests (Explicit 3-2-4 Grouping)
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_validate_tax_id_valid_ssn_hyphenated(taxcalc_server: Any) -> None:
    """SSN formatted with standard hyphens (XXX-XX-XXXX) is identified as SSN."""
    res = await taxcalc_server.call_tool("validate_tax_id", {"tax_id": "123-45-6789"})
    data = res.structured_content
    assert data["format_valid"] is True
    assert data["id_type"] == "SSN"
    assert data["formatted"] == "123-45-6789"
    assert data["country"] == "US"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_validate_tax_id_valid_ssn_spaced(taxcalc_server: Any) -> None:
    """SSN formatted with spaces (XXX XX XXXX) is identified as SSN."""
    res = await taxcalc_server.call_tool("validate_tax_id", {"tax_id": "123 45 6789"})
    data = res.structured_content
    assert data["format_valid"] is True
    assert data["id_type"] == "SSN"
    assert data["formatted"] == "123-45-6789"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_validate_tax_id_invalid_ssn_area_zero(taxcalc_server: Any) -> None:
    """SSN with area number 000 is rejected as invalid."""
    res = await taxcalc_server.call_tool("validate_tax_id", {"tax_id": "000-12-3456"})
    data = res.structured_content
    assert data["format_valid"] is False
    assert "Invalid SSN" in data["error"]
    assert "000" in data["error"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_validate_tax_id_invalid_ssn_spaced_area_zero(taxcalc_server: Any) -> None:
    """Spaced SSN with area number 000 is rejected as invalid."""
    res = await taxcalc_server.call_tool("validate_tax_id", {"tax_id": "000 12 3456"})
    data = res.structured_content
    assert data["format_valid"] is False
    assert "Invalid SSN" in data["error"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_validate_tax_id_invalid_ssn_area_666(taxcalc_server: Any) -> None:
    """SSN with area number 666 is rejected as invalid."""
    res = await taxcalc_server.call_tool("validate_tax_id", {"tax_id": "666-12-3456"})
    data = res.structured_content
    assert data["format_valid"] is False
    assert "Invalid SSN" in data["error"]
    assert "666" in data["error"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_validate_tax_id_invalid_ssn_spaced_area_666(taxcalc_server: Any) -> None:
    """Spaced SSN with area number 666 is rejected as invalid."""
    res = await taxcalc_server.call_tool("validate_tax_id", {"tax_id": "666 12 3456"})
    data = res.structured_content
    assert data["format_valid"] is False
    assert "Invalid SSN" in data["error"]
    assert "666" in data["error"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_validate_tax_id_invalid_ssn_area_900(taxcalc_server: Any) -> None:
    """SSN with area number 900 is rejected as invalid."""
    res = await taxcalc_server.call_tool("validate_tax_id", {"tax_id": "900-12-3456"})
    data = res.structured_content
    assert data["format_valid"] is False
    assert "Invalid SSN" in data["error"]
    assert "900-999" in data["error"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_validate_tax_id_invalid_ssn_area_999(taxcalc_server: Any) -> None:
    """SSN with area number 999 is rejected as invalid."""
    res = await taxcalc_server.call_tool("validate_tax_id", {"tax_id": "999-12-3456"})
    data = res.structured_content
    assert data["format_valid"] is False
    assert "Invalid SSN" in data["error"]
    assert "900-999" in data["error"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_validate_tax_id_invalid_ssn_spaced_area_900(taxcalc_server: Any) -> None:
    """Spaced SSN with area number in 900-999 range is rejected as invalid."""
    res = await taxcalc_server.call_tool("validate_tax_id", {"tax_id": "950 12 3456"})
    data = res.structured_content
    assert data["format_valid"] is False
    assert "Invalid SSN" in data["error"]
    assert "900-999" in data["error"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_validate_tax_id_invalid_ssn_group_zero(taxcalc_server: Any) -> None:
    """SSN with group number 00 is rejected as invalid."""
    res = await taxcalc_server.call_tool("validate_tax_id", {"tax_id": "123-00-6789"})
    data = res.structured_content
    assert data["format_valid"] is False
    assert "Invalid SSN" in data["error"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_validate_tax_id_invalid_ssn_serial_zero(taxcalc_server: Any) -> None:
    """SSN with serial number 0000 is rejected as invalid."""
    res = await taxcalc_server.call_tool("validate_tax_id", {"tax_id": "123-45-0000"})
    data = res.structured_content
    assert data["format_valid"] is False
    assert "Invalid SSN" in data["error"]


# ============================================================================
# Whitespace Handling Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_validate_tax_id_ssn_with_surrounding_whitespace(taxcalc_server: Any) -> None:
    """SSN with leading and trailing whitespace is trimmed and recognized as SSN."""
    res = await taxcalc_server.call_tool("validate_tax_id", {"tax_id": "  123-45-6789  "})
    data = res.structured_content
    assert data["format_valid"] is True
    assert data["id_type"] == "SSN"
    assert data["formatted"] == "123-45-6789"
    assert data["country"] == "US"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_validate_tax_id_ein_with_surrounding_whitespace(taxcalc_server: Any) -> None:
    """EIN with leading and trailing whitespace is trimmed and recognized as EIN."""
    res = await taxcalc_server.call_tool("validate_tax_id", {"tax_id": "  12-3456789  "})
    data = res.structured_content
    assert data["format_valid"] is True
    assert data["id_type"] == "EIN"
    assert data["formatted"] == "12-3456789"
    assert data["country"] == "US"


# ============================================================================
# Invalid Lengths & Malformed Identifiers
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_validate_tax_id_too_short(taxcalc_server: Any) -> None:
    """Tax ID with fewer than 9 digits is rejected."""
    res = await taxcalc_server.call_tool("validate_tax_id", {"tax_id": "12345"})
    data = res.structured_content
    assert data["format_valid"] is False
    assert "must be 9 digits" in data["error"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_validate_tax_id_too_long(taxcalc_server: Any) -> None:
    """Tax ID with more than 9 digits is rejected."""
    res = await taxcalc_server.call_tool("validate_tax_id", {"tax_id": "12345678901"})
    data = res.structured_content
    assert data["format_valid"] is False
    assert "must be 9 digits" in data["error"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_validate_tax_id_empty_string(taxcalc_server: Any) -> None:
    """Empty string tax ID is rejected."""
    res = await taxcalc_server.call_tool("validate_tax_id", {"tax_id": ""})
    data = res.structured_content
    assert data["format_valid"] is False
    assert "must be 9 digits" in data["error"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_validate_tax_id_non_numeric_characters(taxcalc_server: Any) -> None:
    """Tax ID containing letters or special characters is rejected."""
    res = await taxcalc_server.call_tool("validate_tax_id", {"tax_id": "12-ABC5678"})
    data = res.structured_content
    assert data["format_valid"] is False
    assert "must be 9 digits" in data["error"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_validate_tax_id_ssn_embedded_in_extra_characters(
    taxcalc_server: Any,
) -> None:
    """A valid SSN embedded within extra characters or text is rejected."""
    cases = [
        "prefix 123-45-6789",
        "123-45-6789 suffix",
        "prefix 123-45-6789 suffix",
        "123-45-6789-extra",
        "extra-123-45-6789",
        "123 45 6789 extra",
        "prefix 123 45 6789",
        "Tax ID: 123-45-6789",
        "A123-45-6789",
        "123-45-6789B",
    ]
    for case in cases:
        res = await taxcalc_server.call_tool("validate_tax_id", {"tax_id": case})
        data = res.structured_content
        assert data["format_valid"] is False, f"Expected {case!r} to be rejected"


# ============================================================================
# Country Handling
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_validate_tax_id_unsupported_country(taxcalc_server: Any) -> None:
    """Countries other than 'US' return an unsupported error."""
    res = await taxcalc_server.call_tool(
        "validate_tax_id", {"tax_id": "12-3456789", "country": "CA"}
    )
    data = res.structured_content
    assert data["format_valid"] is False
    assert "Tax ID validation not supported for country: CA" in data["error"]
