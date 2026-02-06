"""Detector Implementations"""

# Imports trigger registration via decorators
from finbot.ctf.detectors.implementations.prompt_leak import PromptLeakDetector

__all__ = ["PromptLeakDetector"]
