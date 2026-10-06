"""Tests for the lexical analyzer (Phase 2)."""

from __future__ import annotations

import sys
from pathlib import Path

# Allow importing compiler package when running from backend/ or repo root
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from compiler.lexer import (
    ASSIGN,
    DIVIDE,
    EOF,
    EQ,
    FLOAT,
    GT,
    GTE,
    IDENTIFIER,
    IF,
    INT,
    LBRACE,
    LPAREN,
    LT,
    LTE,
    MINUS,
    MULTIPLY,
    NEQ,
    NUMBER,
    PLUS,
    RBRACE,
    SEMICOLON,
    WHILE,
    tokenize,
)


def types_of(result):
    return [t.type for t in result.tokens]


def values_of(result):
    return [t.value for t in result.tokens]


class TestBasicTokenization:
    def test_simple_declaration_fragment(self):
        result = tokenize("int x = 10")
        assert result.errors == []
        assert types_of(result) == [INT, IDENTIFIER, ASSIGN, NUMBER, EOF]
        assert values_of(result)[:-1] == ["int", "x", "=", "10"]

    def test_token_positions(self):
        result = tokenize("int x = 10")
        tokens = {t.type: t for t in result.tokens if t.type != EOF}
        assert tokens[INT].line == 1 and tokens[INT].column == 1
        assert tokens[IDENTIFIER].line == 1 and tokens[IDENTIFIER].column == 5
        assert tokens[ASSIGN].line == 1 and tokens[ASSIGN].column == 7
        assert tokens[NUMBER].line == 1 and tokens[NUMBER].column == 9

    def test_full_statement_with_semicolon(self):
        result = tokenize("int x = 10;")
        assert types_of(result) == [INT, IDENTIFIER, ASSIGN, NUMBER, SEMICOLON, EOF]

    def test_keywords_and_control_flow(self):
        result = tokenize("if (x < y) { while (1) { } } else { }")
        assert types_of(result)[:3] == [IF, LPAREN, IDENTIFIER]
        assert WHILE in types_of(result)
        assert LBRACE in types_of(result)
        assert RBRACE in types_of(result)

    def test_float_keyword_and_float_literal(self):
        result = tokenize("float y = 3.14;")
        assert types_of(result) == [FLOAT, IDENTIFIER, ASSIGN, NUMBER, SEMICOLON, EOF]
        assert values_of(result)[3] == "3.14"

    def test_operators(self):
        result = tokenize("a == b != c <= d >= e < f > g + h - i * j / k")
        expected = [
            IDENTIFIER,
            EQ,
            IDENTIFIER,
            NEQ,
            IDENTIFIER,
            LTE,
            IDENTIFIER,
            GTE,
            IDENTIFIER,
            LT,
            IDENTIFIER,
            GT,
            IDENTIFIER,
            PLUS,
            IDENTIFIER,
            MINUS,
            IDENTIFIER,
            MULTIPLY,
            IDENTIFIER,
            DIVIDE,
            IDENTIFIER,
            EOF,
        ]
        assert types_of(result) == expected

    def test_multiline_positions(self):
        source = "int x = 1;\nint y = 2;"
        result = tokenize(source)
        y_token = next(t for t in result.tokens if t.value == "y")
        assert y_token.line == 2
        assert y_token.column == 5


class TestCommentsAndWhitespace:
    def test_line_comment_ignored(self):
        result = tokenize("int x = 1; // comment here\nint y;")
        assert result.errors == []
        assert "y" in values_of(result)
        assert types_of(result).count(INT) == 2

    def test_block_comment_ignored(self):
        result = tokenize("int /* skip */ x = 10;")
        assert types_of(result) == [INT, IDENTIFIER, ASSIGN, NUMBER, SEMICOLON, EOF]

    def test_unterminated_block_comment(self):
        result = tokenize("int x /* oops")
        assert any(e.type == "UnterminatedComment" for e in result.errors)
        assert INT in types_of(result)
        assert IDENTIFIER in types_of(result)


class TestLexicalErrors:
    def test_unexpected_character(self):
        result = tokenize("int x @ 10;")
        assert any(e.type == "UnexpectedCharacter" for e in result.errors)
        assert any(e.character == "@" for e in result.errors)
        # Still produces surrounding tokens
        assert INT in types_of(result)
        assert NUMBER in types_of(result)

    def test_lone_bang(self):
        result = tokenize("x ! y")
        assert any("!" in (e.message or "") for e in result.errors)

    def test_invalid_number_with_letters(self):
        result = tokenize("int x = 10abc;")
        assert any(e.type == "InvalidNumber" for e in result.errors)

    def test_empty_source(self):
        result = tokenize("")
        assert types_of(result) == [EOF]
        assert result.errors == []

    def test_to_dict_shape(self):
        payload = tokenize("int x = 10").to_dict()
        assert "tokens" in payload
        assert "lexical_errors" in payload
        assert payload["success"] is True
        assert payload["tokens"][0] == {
            "type": "INT",
            "value": "int",
            "line": 1,
            "column": 1,
        }


class TestDemoSnippet:
    def test_example_program_tokens(self):
        source = """int x = 10
int y = 20;

if (x < y {
    x = x + 1;
}
"""
        result = tokenize(source)
        assert result.errors == []
        assert types_of(result)[:5] == [INT, IDENTIFIER, ASSIGN, NUMBER, INT]
        assert IF in types_of(result)
        assert LT in types_of(result)
        assert LPAREN in types_of(result)
        # Missing ')' is a syntax issue for the parser, not the lexer
        assert types_of(result).count("RPAREN") == 0
