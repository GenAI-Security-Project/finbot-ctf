"""Evaluator Registry - Maps evaluator class names to implementations"""

import logging
from typing import Any, Type

from finbot.ctf.evaluators.base import BaseEvaluator

logger = logging.getLogger(__name__)


# Registry of evaluator classes
_EVALUATOR_REGISTRY: dict[str, Type[BaseEvaluator]] = {}


def register_evaluator(name: str):
    """Decorator to register an evaluator class.

    Usage:
    @register_evaluator("VendorCountEvaluator")
    class VendorCountEvaluator(BaseEvaluator):
        ...
    """

    def decorator(cls: Type[BaseEvaluator]) -> Type[BaseEvaluator]:
        if name in _EVALUATOR_REGISTRY:
            logger.warning("Overwriting evaluator registration: %s", name)
        _EVALUATOR_REGISTRY[name] = cls
        logger.debug("Registered evaluator: %s -> %s", name, cls.__name__)
        return cls

    return decorator


def get_evaluator_class(name: str) -> Type[BaseEvaluator]:
    """Get a registered evaluator class by name.
    Raises ValueError if evaluator is not found.
    """
    try:
        return _EVALUATOR_REGISTRY[name]
    except KeyError:
        raise ValueError(f"Evaluator not found: {name}") from None


def create_evaluator(
    evaluator_class_name: str, badge_id: str, config: dict[str, Any] | None = None
) -> BaseEvaluator | None:
    """Create an evaluator instance by name.
    Args:
        evaluator_class_name: The name of the evaluator class to create
        badge_id: The ID of the badge this evaluator is associated with
        config: Optional evaluator configuration (evaluator-specific)
    Returns:
        Evaluator instance or None if not found
    """
    try:
        evaluator_class = get_evaluator_class(evaluator_class_name)
        if not evaluator_class:
            raise ValueError(f"Evaluator not found: {evaluator_class_name}")
        return evaluator_class(badge_id=badge_id, config=config)
    except ValueError as e:
        logger.error("Failed to create evaluator: %s", e)
        return None


def list_registered_evaluators() -> list[str]:
    """List all registered evaluator class names"""
    return list(_EVALUATOR_REGISTRY.keys())


def _register_all_evaluators():
    """Import all evaluator implementations to trigger registration"""
    from finbot.ctf.evaluators.implementations import vendor_count

    logger.info("Registered %d evaluators", len(_EVALUATOR_REGISTRY))


# Auto-register on import
_register_all_evaluators()
