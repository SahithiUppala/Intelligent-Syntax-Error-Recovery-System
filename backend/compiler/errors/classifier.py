"""
Error classification for detected syntax errors.

Maps each DetectedError into one of:
  INSERTION_ERROR, DELETION_ERROR, REPLACEMENT_ERROR,
  DELIMITER_ERROR, EXPRESSION_ERROR, STRUCTURAL_ERROR

Classification is rule-based and deterministic so later scoring /
recovery modules can branch on category without re-inspecting tokens.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional, Union

from compiler.errors.detector import (
    EXTRA_TOKEN,
    INVALID_ASSIGNMENT,
    INVALID_NUMBER,
    MALFORMED_DECLARATION,
    MISSING_CLOSING_BRACE,
    MISSING_CLOSING_PARENTHESIS,
    MISSING_OPENING_BRACE,
    MISSING_OPENING_PARENTHESIS,
    MISSING_OPERAND,
    MISSING_OPERATOR,
    MISSING_SEMICOLON,
    UNEXPECTED_CHARACTER,
    UNEXPECTED_TOKEN,
    UNTERMINATED_COMMENT,
    DetectedError,
    DetectionResult,
    detect_syntax_errors,
)

# Classification categories
INSERTION_ERROR = "INSERTION_ERROR"
DELETION_ERROR = "DELETION_ERROR"
REPLACEMENT_ERROR = "REPLACEMENT_ERROR"
DELIMITER_ERROR = "DELIMITER_ERROR"
EXPRESSION_ERROR = "EXPRESSION_ERROR"
STRUCTURAL_ERROR = "STRUCTURAL_ERROR"

CATEGORY_DESCRIPTIONS = {
    INSERTION_ERROR: "A required token is missing and should be inserted.",
    DELETION_ERROR: "An extra token is present and should be removed.",
    REPLACEMENT_ERROR: "A token is incorrect and should be replaced.",
    DELIMITER_ERROR: "A delimiter such as (), {}, or matching brackets is wrong or missing.",
    EXPRESSION_ERROR: "An expression is incomplete (missing operand or operator).",
    STRUCTURAL_ERROR: "A statement/structure does not match the expected grammar shape.",
}

# Primary type → category
TYPE_TO_CATEGORY: dict[str, str] = {
    MISSING_SEMICOLON: INSERTION_ERROR,
    MISSING_CLOSING_PARENTHESIS: DELIMITER_ERROR,
    MISSING_OPENING_PARENTHESIS: DELIMITER_ERROR,
    MISSING_CLOSING_BRACE: DELIMITER_ERROR,
    MISSING_OPENING_BRACE: DELIMITER_ERROR,
    EXTRA_TOKEN: DELETION_ERROR,
    MISSING_OPERAND: EXPRESSION_ERROR,
    MISSING_OPERATOR: EXPRESSION_ERROR,
    INVALID_ASSIGNMENT: STRUCTURAL_ERROR,
    MALFORMED_DECLARATION: STRUCTURAL_ERROR,
    UNTERMINATED_COMMENT: STRUCTURAL_ERROR,
    INVALID_NUMBER: REPLACEMENT_ERROR,
    UNEXPECTED_CHARACTER: REPLACEMENT_ERROR,
    UNEXPECTED_TOKEN: REPLACEMENT_ERROR,
}

# Tokens typically missing for insertion/delimiter cases
DEFAULT_MISSING_TOKEN: dict[str, Optional[str]] = {
    MISSING_SEMICOLON: ";",
    MISSING_CLOSING_PARENTHESIS: ")",
    MISSING_OPENING_PARENTHESIS: "(",
    MISSING_CLOSING_BRACE: "}",
    MISSING_OPENING_BRACE: "{",
    MISSING_OPERATOR: None,  # multiple candidates
    MISSING_OPERAND: None,
    UNTERMINATED_COMMENT: "*/",
}


@dataclass
class ClassifiedError:
    """Detected error plus classification metadata."""

    type: str
    message: str
    explanation: str
    line: int
    column: int
    found: Optional[str] = None
    expected: list[str] = field(default_factory=list)
    fragment: str = ""
    source: str = "parser"
    classification: str = STRUCTURAL_ERROR
    classification_reason: str = ""
    missing_token: Optional[str] = None
    extra_token: Optional[str] = None
    suggested_fix: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ClassificationResult:
    errors: list[ClassifiedError]
    detection: Optional[DetectionResult] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "errors": [e.to_dict() for e in self.errors],
            "total_errors": len(self.errors),
            "success": len(self.errors) == 0,
            "categories": sorted({e.classification for e in self.errors}),
            "ast": self.detection.parse_result.ast if self.detection and self.detection.parse_result else None,
            "tokens": (
                [t.to_dict() for t in self.detection.parse_result.tokens]
                if self.detection and self.detection.parse_result
                else []
            ),
        }


class ErrorClassifier:
    """Classify DetectedError instances into recovery-oriented categories."""

    def classify_one(self, error: Union[DetectedError, dict[str, Any]]) -> ClassifiedError:
        data = error.to_dict() if isinstance(error, DetectedError) else dict(error)
        err_type = data.get("type", UNEXPECTED_TOKEN)
        category = TYPE_TO_CATEGORY.get(err_type, STRUCTURAL_ERROR)

        # Refine UnexpectedToken using expected/found hints
        if err_type == UNEXPECTED_TOKEN:
            category = self._refine_unexpected(data)

        missing = self._infer_missing_token(err_type, data)
        extra = self._infer_extra_token(err_type, data, category)
        reason = self._build_reason(err_type, category, missing, extra, data)
        action = self._build_action(category, missing, extra, data)

        return ClassifiedError(
            type=err_type,
            message=data.get("message", ""),
            explanation=data.get("explanation", ""),
            line=int(data.get("line", 1)),
            column=int(data.get("column", 1)),
            found=data.get("found"),
            expected=list(data.get("expected") or []),
            fragment=data.get("fragment") or "",
            source=data.get("source") or "parser",
            classification=category,
            classification_reason=reason,
            missing_token=missing,
            extra_token=extra,
            suggested_fix=action,
        )

    def classify_many(
        self,
        errors: list[Union[DetectedError, dict[str, Any]]],
    ) -> list[ClassifiedError]:
        return [self.classify_one(e) for e in errors]

    def classify_detection(self, detection: DetectionResult) -> ClassificationResult:
        classified = self.classify_many(detection.errors)
        return ClassificationResult(errors=classified, detection=detection)

    # ---------------------------------------------------------------- helpers

    def _refine_unexpected(self, data: dict[str, Any]) -> str:
        expected = [str(x) for x in (data.get("expected") or [])]
        found = data.get("found")
        delimiter_marks = {"(", ")", "{", "}", ";"}
        if any(e in delimiter_marks for e in expected):
            if any(e in {"(", ")", "{", "}"} for e in expected):
                return DELIMITER_ERROR
            if ";" in expected:
                return INSERTION_ERROR
        if found in {";"}:
            return DELETION_ERROR
        if found and expected and len(expected) == 1 and expected[0] not in delimiter_marks:
            return REPLACEMENT_ERROR
        return STRUCTURAL_ERROR

    def _infer_missing_token(
        self,
        err_type: str,
        data: dict[str, Any],
    ) -> Optional[str]:
        if err_type in DEFAULT_MISSING_TOKEN:
            default = DEFAULT_MISSING_TOKEN[err_type]
            if default is not None:
                return default
        expected = data.get("expected") or []
        if len(expected) == 1:
            return str(expected[0])
        if err_type == MISSING_OPERATOR and expected:
            return str(expected[0])
        return None

    def _infer_extra_token(
        self,
        err_type: str,
        data: dict[str, Any],
        category: str,
    ) -> Optional[str]:
        if category == DELETION_ERROR or err_type == EXTRA_TOKEN:
            return data.get("found")
        return None

    def _build_reason(
        self,
        err_type: str,
        category: str,
        missing: Optional[str],
        extra: Optional[str],
        data: dict[str, Any],
    ) -> str:
        base = CATEGORY_DESCRIPTIONS.get(category, "Uncategorized syntax issue.")
        if category == INSERTION_ERROR and missing:
            return f"{base} Missing token: {missing}"
        if category == DELIMITER_ERROR and missing:
            return f"{base} Missing token: {missing}"
        if category == DELETION_ERROR and extra:
            return f"{base} Extra token: {extra}"
        if category == EXPRESSION_ERROR:
            if err_type == MISSING_OPERATOR:
                return f"{base} Adjacent operands need an operator between them."
            if err_type == MISSING_OPERAND:
                return f"{base} An operand expression is required here."
        if category == REPLACEMENT_ERROR and data.get("found") and data.get("expected"):
            return (
                f"{base} Found '{data['found']}', expected "
                f"{', '.join(str(x) for x in data['expected'])}."
            )
        if category == STRUCTURAL_ERROR:
            return f"{base} Error kind: {err_type}."
        return base

    def _build_action(
        self,
        category: str,
        missing: Optional[str],
        extra: Optional[str],
        data: dict[str, Any],
    ) -> str:
        if category == INSERTION_ERROR:
            return f"Insert '{missing}'" if missing else "Insert the expected token"
        if category == DELIMITER_ERROR:
            return f"Insert delimiter '{missing}'" if missing else "Fix mismatched delimiter"
        if category == DELETION_ERROR:
            return f"Delete '{extra}'" if extra else "Delete the unexpected token"
        if category == REPLACEMENT_ERROR:
            expected = data.get("expected") or []
            if data.get("found") and expected:
                return f"Replace '{data['found']}' with '{expected[0]}'"
            return "Replace the unexpected token"
        if category == EXPRESSION_ERROR:
            if missing:
                return f"Insert operator/operand near '{missing}'"
            return "Complete the expression (add operand or operator)"
        return "Restructure the statement to match the grammar"


def classify_errors(
    source: str,
    detection: Optional[DetectionResult] = None,
) -> ClassificationResult:
    """Public entry: detect (if needed) then classify."""
    detection_result = detection if detection is not None else detect_syntax_errors(source)
    return ErrorClassifier().classify_detection(detection_result)


def classify_detected_errors(
    errors: list[Union[DetectedError, dict[str, Any]]],
) -> list[ClassifiedError]:
    """Classify an existing list of detected errors."""
    return ErrorClassifier().classify_many(errors)
