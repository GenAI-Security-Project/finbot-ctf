"""Unit tests for ExtraFormatter in finbot.logging_config."""

import logging

from finbot.logging_config import setup_logging


def test_extra_formatter_appends_extra_attributes_only_when_present():
    """Verify setup_logging configures ExtraFormatter to append structured extras."""
    root_logger = logging.getLogger()
    saved_handlers = list(root_logger.handlers)
    saved_level = root_logger.level
    try:
        setup_logging(log_level="INFO")
        formatter = root_logger.handlers[0].formatter

        plain_record = logging.LogRecord(
            name="finbot.test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="plain message",
            args=(),
            exc_info=None,
        )
        assert " | " not in formatter.format(plain_record)

        extra_record = logging.LogRecord(
            name="finbot.test",
            level=logging.INFO,
            pathname=__file__,
            lineno=2,
            msg="session message",
            args=(),
            exc_info=None,
        )
        setattr(extra_record, "app.trusted_source", False)
        formatted = formatter.format(extra_record)
        assert "session message | app.trusted_source=False" in formatted
    finally:
        root_logger.handlers.clear()
        root_logger.handlers.extend(saved_handlers)
        root_logger.setLevel(saved_level)
