"""Tests for grammar helpers and the recursive-descent parser (Phase 3)."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from compiler.grammar import GRAMMAR_TEXT, STATEMENT_START, display_token
from compiler.parser import parse


def error_types(result):
    return [e.type for e in result.errors]


def stmt_types(result):
    assert result.ast is not None
    return [s["type"] for s in result.ast["body"]]


class TestGrammarModule:
    def test_grammar_text_contains_core_productions(self):
        assert "program" in GRAMMAR_TEXT
        assert "declaration" in GRAMMAR_TEXT
        assert "if_statement" in GRAMMAR_TEXT
        assert "equality" in GRAMMAR_TEXT

    def test_display_token(self):
        assert display_token("SEMICOLON") == ";"
        assert display_token("IDENTIFIER") == "identifier"

    def test_statement_start_set(self):
        assert "INT" in STATEMENT_START
        assert "IF" in STATEMENT_START


class TestValidPrograms:
    def test_simple_declaration(self):
        result = parse("int x = 10;")
        assert result.errors == []
        assert stmt_types(result) == ["Declaration"]
        decl = result.ast["body"][0]
        assert decl["name"] == "x"
        assert decl["var_type"] == "int"
        assert decl["initializer"]["type"] == "Literal"
        assert decl["initializer"]["value"] == "10"

    def test_declaration_without_initializer(self):
        result = parse("float y;")
        assert result.errors == []
        assert result.ast["body"][0]["name"] == "y"
        assert "initializer" not in result.ast["body"][0]

    def test_assignment(self):
        result = parse("x = x + 1;")
        assert result.errors == []
        assert stmt_types(result) == ["Assignment"]
        assign = result.ast["body"][0]
        assert assign["name"] == "x"
        assert assign["value"]["type"] == "BinaryExpression"
        assert assign["value"]["operator"] == "+"

    def test_if_else_while_block(self):
        source = """
        int x = 1;
        if (x < 10) {
            x = x + 1;
        } else {
            x = 0;
        }
        while (x > 0) {
            x = x - 1;
        }
        """
        result = parse(source)
        assert result.errors == []
        types = stmt_types(result)
        assert types == ["Declaration", "IfStatement", "WhileStatement"]
        if_node = result.ast["body"][1]
        assert if_node["then_branch"]["type"] == "Block"
        assert if_node["else_branch"]["type"] == "Block"
        assert if_node["condition"]["operator"] == "<"

    def test_nested_expressions(self):
        result = parse("int z = (a + b) * -c;")
        assert result.errors == []
        init = result.ast["body"][0]["initializer"]
        assert init["type"] == "BinaryExpression"
        assert init["operator"] == "*"
        assert init["right"]["type"] == "UnaryExpression"


class TestStructuredErrors:
    def test_missing_semicolon(self):
        result = parse("int x = 10")
        assert "MissingSemicolon" in error_types(result)
        err = next(e for e in result.errors if e.type == "MissingSemicolon")
        assert err.expected == [";"]
        assert err.line >= 1
        assert "declaration" in err.message.lower() or ";" in err.message

    def test_missing_semicolon_continues_to_next_statement(self):
        result = parse("int x = 10\nint y = 20;")
        assert "MissingSemicolon" in error_types(result)
        # Should still build both declarations in the AST
        assert stmt_types(result) == ["Declaration", "Declaration"]
        assert result.ast["body"][1]["name"] == "y"

    def test_missing_closing_paren_in_if(self):
        result = parse("if (x < y {\n  x = 1;\n}")
        assert "MissingClosingParenthesis" in error_types(result)
        assert any(s["type"] == "IfStatement" for s in result.ast["body"])

    def test_missing_opening_paren_in_while(self):
        result = parse("while x > 0) {\n  x = x - 1;\n}")
        assert "MissingOpeningParenthesis" in error_types(result)

    def test_missing_closing_brace(self):
        result = parse("if (x < y) {\n  x = 1;\n")
        assert "MissingClosingBrace" in error_types(result)

    def test_missing_operand_after_assign(self):
        result = parse("int y = ;")
        assert "MissingOperand" in error_types(result)

    def test_invalid_assignment_structure(self):
        # identifier not followed by '='
        result = parse("x;")
        assert any(e.type in {"UnexpectedToken", "InvalidAssignment"} for e in result.errors)

    def test_error_object_shape(self):
        result = parse("int x = 10")
        err = result.errors[0]
        payload = err.to_dict()
        assert set(payload.keys()) >= {
            "type",
            "message",
            "line",
            "column",
            "found",
            "expected",
        }


class TestDemoProgram:
    def test_demo_reports_multiple_errors_and_continues(self):
        source = """int x = 10
int y = 20;

if (x < y {
    x = x + 1;
}
"""
        result = parse(source)
        types = error_types(result)
        assert "MissingSemicolon" in types
        assert "MissingClosingParenthesis" in types
        # Continues parsing — declarations + if present
        body_types = stmt_types(result)
        assert body_types.count("Declaration") == 2
        assert "IfStatement" in body_types
        # Valid assignment inside the block should appear in AST
        if_node = next(s for s in result.ast["body"] if s["type"] == "IfStatement")
        assert if_node["then_branch"]["body"]
        assert if_node["then_branch"]["body"][0]["type"] == "Assignment"

    def test_to_dict_success_flag(self):
        ok = parse("int x = 1;").to_dict()
        bad = parse("int x = 1").to_dict()
        assert ok["success"] is True
        assert bad["success"] is False
        assert ok["ast"]["type"] == "Program"
