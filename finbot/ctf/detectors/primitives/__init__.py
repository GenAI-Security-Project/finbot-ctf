"""Detector Primitives"""

from finbot.ctf.detectors.primitives.pattern_match import PatternMatchDetector
from finbot.ctf.detectors.primitives.pi_jb import PromptInjectionDetector
from finbot.ctf.detectors.primitives.pii import PIIDetector
from finbot.ctf.detectors.primitives.tool_call import ToolCallDetector

__all__ = [
    "PIIDetector",
    "PatternMatchDetector",
    "PromptInjectionDetector",
    "ToolCallDetector",
]
