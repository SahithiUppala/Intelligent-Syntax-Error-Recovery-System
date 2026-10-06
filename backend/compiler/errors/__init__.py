"""Syntax error detection and classification modules."""

from compiler.errors.classifier import (
    ClassificationResult,
    ClassifiedError,
    classify_detected_errors,
    classify_errors,
)
from compiler.errors.detector import (
    DetectionResult,
    DetectedError,
    detect_syntax_errors,
    describe_error_catalog,
)

__all__ = [
    "DetectedError",
    "DetectionResult",
    "detect_syntax_errors",
    "describe_error_catalog",
    "ClassifiedError",
    "ClassificationResult",
    "classify_errors",
    "classify_detected_errors",
]
