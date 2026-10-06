"""
Grammar definition for the mini C-like language.

This module documents productions and FIRST/follow helpers used by the
recursive-descent parser. It intentionally contains no parsing logic so
an alternate ranking model can later reuse the same grammar metadata.
"""

from __future__ import annotations

from compiler.lexer import (
    ASSIGN,
    DIVIDE,
    ELSE,
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
    RPAREN,
    SEMICOLON,
    WHILE,
)

# Human-readable grammar (EBNF-style)
GRAMMAR_TEXT = """
program           → statement*

statement         → declaration
                  | assignment
                  | if_statement
                  | while_statement
                  | block

declaration       → type IDENTIFIER ("=" expression)? ";"
type              → "int" | "float"

assignment        → IDENTIFIER "=" expression ";"

if_statement      → "if" "(" expression ")" block ("else" block)?

while_statement   → "while" "(" expression ")" block

block             → "{" statement* "}"

expression        → equality
equality          → comparison (("==" | "!=") comparison)*
comparison        → term (("<" | ">" | "<=" | ">=") term)*
term              → factor (("+" | "-") factor)*
factor             → unary (("*" | "/") unary)*
unary             → "-" unary | primary
primary           → NUMBER | IDENTIFIER | "(" expression ")"
"""

TYPE_TOKENS = frozenset({INT, FLOAT})
STATEMENT_START = frozenset({INT, FLOAT, IDENTIFIER, IF, WHILE, LBRACE})
EXPRESSION_START = frozenset({NUMBER, IDENTIFIER, LPAREN, MINUS})

EQUALITY_OPS = frozenset({EQ, NEQ})
COMPARISON_OPS = frozenset({LT, GT, LTE, GTE})
TERM_OPS = frozenset({PLUS, MINUS})
FACTOR_OPS = frozenset({MULTIPLY, DIVIDE})

# Synchronization tokens for panic-mode recovery (refined further in Phase 8)
SYNC_TOKENS = frozenset(
    {
        SEMICOLON,
        RBRACE,
        INT,
        FLOAT,
        IF,
        WHILE,
        EOF,
    }
)

TOKEN_DISPLAY = {
    INT: "int",
    FLOAT: "float",
    IF: "if",
    ELSE: "else",
    WHILE: "while",
    IDENTIFIER: "identifier",
    NUMBER: "number",
    PLUS: "+",
    MINUS: "-",
    MULTIPLY: "*",
    DIVIDE: "/",
    ASSIGN: "=",
    EQ: "==",
    NEQ: "!=",
    LT: "<",
    GT: ">",
    LTE: "<=",
    GTE: ">=",
    LPAREN: "(",
    RPAREN: ")",
    LBRACE: "{",
    RBRACE: "}",
    SEMICOLON: ";",
    EOF: "end of file",
}


def display_token(token_type: str) -> str:
    return TOKEN_DISPLAY.get(token_type, token_type)


def expected_display(token_types: list[str] | tuple[str, ...] | set[str]) -> list[str]:
    return [display_token(t) for t in token_types]
