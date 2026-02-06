"""CTF Challenge Detectors"""

from finbot.ctf.detectors.base import BaseDetector
from finbot.ctf.detectors.registry import (
    create_detector,
    get_detector_class,
    list_registered_detectors,
    register_detector,
)
from finbot.ctf.detectors.result import DetectionResult

__all__ = [
    "BaseDetector",
    "DetectionResult",
    "register_detector",
    "get_detector_class",
    "create_detector",
    "list_registered_detectors",
]
