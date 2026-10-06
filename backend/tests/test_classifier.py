"""Tests for error classification (Phase 5)."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from compiler.errors.classifier import (
    DELETION_ERROR,
    DELIMITER_ERROR,
    EXPRESSION_ERROR,
    INSERTION_ERROR,
    STRUCTURAL_ERROR,
    classify_detected_errors,
    classify_errors,
)
from compiler.errors.detector import DetectedError, detect_syntax_errors


class TestClassificationRules:
    def test_missing_semicolon_is_insertion(self):
        result = classify_errors("int x = 10")
        assert result.errors
        err = next(e for e in result.errors if e.type == "MissingSemicolon")
        assert err.classification == INSERTION_ERROR
        assert err.missing_token == ";"
        assert "Missing token: ;" in err.classification_reason
        assert "Insert" in err.suggested_fix

    def test_missing_paren_is_delimiter(self):
        result = classify_errors("if (x > 5 {\n  x = 1;\n}")
        err = next(e for e in result.errors if e.type == "MissingClosingParenthesis")
        assert err.classification == DELIMITER_ERROR
        assert err.missing_token == ")"
        assert "Missing token: )" in err.classification_reason

    def test_missing_brace_is_delimiter(self):
        result = classify_errors("if (x < y)\n  x = 1;")
        types = {e.type: e for e in result.errors}
        assert "MissingOpeningBrace" in types
        assert types["MissingOpeningBrace"].classification == DELIMITER_ERROR
        assert types["MissingOpeningBrace"].missing_token == "{"

    def test_extra_semicolon_is_deletion(self):
        # Leading stray semicolon before a statement
        result = classify_errors(";\nint x = 1;")
        err = next(e for e in result.errors if e.type == "ExtraToken")
        assert err.classification == DELETION_ERROR
        assert err.extra_token == ";"

    def test_missing_operand_is_expression(self):
        result = classify_errors("int y = ;")
        err = next(e for e in result.errors if e.type == "MissingOperand")
        assert err.classification == EXPRESSION_ERROR

    def test_missing_operator_is_expression(self):
        result = classify_errors("int z = x y;")
        err = next(e for e in result.errors if e.type == "MissingOperator")
        assert err.classification == EXPRESSION_ERROR

    def test_malformed_declaration_is_structural(self):
        # type without identifier
        result = classify_errors("int = 10;")
        assert any(e.classification == STRUCTURAL_ERROR for e in result.errors)

    def test_demo_program_classifications(self):
        source = """int x = 10
int y = 20;

if (x < y {
    x = x + 1;
}
"""
        result = classify_errors(source)
        by_type = {e.type: e for e in result.errors}
        assert by_type["MissingSemicolon"].classification == INSERTION_ERROR
        assert by_type["MissingClosingParenthesis"].classification == DELIMITER_ERROR
        payload = result.to_dict()
        assert "INSERTION_ERROR" in payload["categories"]
        assert "DELIMITER_ERROR" in payload["categories"]
        for err in result.errors:
            data = err.to_dict()
            assert "classification" in data
            assert "classification_reason" in data

    def test_classify_detected_errors_helper(self):
        detection = detect_syntax_errors("int x = 10")
        classified = classify_detected_errors(detection.errors)
        assert classified[0].classification == INSERTION_ERROR

    def test_classify_from_dict(self):
        raw = DetectedError(
            type="MissingSemicolon",
            message="Expected ';'",
            explanation="...",
            line=1,
            column=11,
            found="int",
            expected=[";"],
            fragment="int x = 10",
        ).to_dict()
        classified = classify_detected_errors([raw])
        assert classified[0].classification == INSERTION_ERROR
        assert classified[0].missing_token == ";"
