"""Tests for structured syntax error detection (Phase 4)."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from compiler.errors.detector import (
    EXPLANATIONS,
    MISSING_CLOSING_PARENTHESIS,
    MISSING_OPERAND,
    MISSING_OPERATOR,
    MISSING_SEMICOLON,
    detect_syntax_errors,
    describe_error_catalog,
)


def types_of(result):
    return [e.type for e in result.errors]


class TestDetectorBasics:
    def test_valid_program_has_no_errors(self):
        result = detect_syntax_errors("int x = 10;\nint y = 20;")
        assert result.errors == []
        assert result.to_dict()["success"] is True
        assert result.to_dict()["total_errors"] == 0

    def test_missing_semicolon_enriched(self):
        result = detect_syntax_errors("int x = 10")
        assert MISSING_SEMICOLON in types_of(result)
        err = next(e for e in result.errors if e.type == MISSING_SEMICOLON)
        assert err.line >= 1
        assert err.expected == [";"]
        assert err.explanation
        assert "semicolon" in err.explanation.lower()
        assert err.fragment  # original line fragment
        assert "int x = 10" in err.fragment
        payload = err.to_dict()
        assert set(payload.keys()) >= {
            "type",
            "message",
            "explanation",
            "line",
            "column",
            "found",
            "expected",
            "fragment",
        }

    def test_missing_semicolon_between_declarations(self):
        source = "int x = 10\nint y = 20;"
        result = detect_syntax_errors(source)
        assert MISSING_SEMICOLON in types_of(result)
        err = next(e for e in result.errors if e.type == MISSING_SEMICOLON)
        assert "int x = 10" in err.fragment or err.line in (1, 2)

    def test_missing_closing_paren_in_if(self):
        source = "if (x < y {\n    x = x + 1;\n}"
        result = detect_syntax_errors(source)
        assert MISSING_CLOSING_PARENTHESIS in types_of(result)
        err = next(e for e in result.errors if e.type == MISSING_CLOSING_PARENTHESIS)
        assert ")" in err.expected
        assert "parenthesis" in err.explanation.lower()

    def test_missing_operand_after_equals(self):
        result = detect_syntax_errors("int y = ;")
        assert MISSING_OPERAND in types_of(result)
        err = next(e for e in result.errors if e.type == MISSING_OPERAND)
        assert err.explanation

    def test_missing_operator_pattern(self):
        result = detect_syntax_errors("int z = x y;")
        assert MISSING_OPERATOR in types_of(result)
        err = next(e for e in result.errors if e.type == MISSING_OPERATOR)
        assert "x" in err.message and "y" in err.message

    def test_demo_program_multiple_structured_errors(self):
        source = """int x = 10
int y = 20;

if (x < y {
    x = x + 1;
}
"""
        result = detect_syntax_errors(source)
        types = types_of(result)
        assert MISSING_SEMICOLON in types
        assert MISSING_CLOSING_PARENTHESIS in types
        # Every error has explanation + fragment — never a bare "syntax error"
        for err in result.errors:
            assert err.type.lower() != "syntax error"
            assert err.explanation.strip()
            assert err.message.strip()
            assert err.line >= 1
            assert err.column >= 1

    def test_error_catalog(self):
        catalog = describe_error_catalog()
        assert len(catalog) == len(EXPLANATIONS)
        assert any(item["type"] == MISSING_SEMICOLON for item in catalog)
