"""
Recursive-descent parser for the mini C-like language.

Builds a simple AST, records structured syntax errors, and continues
parsing after errors using basic panic-mode synchronization.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from compiler import grammar
from compiler.lexer import (
    ASSIGN,
    ELSE,
    EOF,
    FLOAT,
    IDENTIFIER,
    IF,
    INT,
    LBRACE,
    LPAREN,
    MINUS,
    NUMBER,
    RBRACE,
    RPAREN,
    SEMICOLON,
    Token,
    WHILE,
    tokenize,
)


@dataclass
class ParseError:
    type: str
    message: str
    line: int
    column: int
    found: Optional[str] = None
    expected: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ParseResult:
    ast: Optional[dict[str, Any]]
    errors: list[ParseError]
    tokens: list[Token]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ast": self.ast,
            "errors": [e.to_dict() for e in self.errors],
            "tokens": [t.to_dict() for t in self.tokens],
            "success": len(self.errors) == 0,
        }


class Parser:
    """Recursive-descent parser with non-fatal error collection."""

    MAX_SYNC_STEPS = 256

    def __init__(self, tokens: list[Token], source: str = ""):
        # Drop EOF duplicates if any; keep a single trailing EOF
        self.tokens = tokens[:] if tokens else [Token(EOF, "", 1, 1)]
        if not self.tokens or self.tokens[-1].type != EOF:
            last = self.tokens[-1] if self.tokens else Token(EOF, "", 1, 1)
            self.tokens.append(Token(EOF, "", last.line, last.column + max(len(last.value), 1)))
        self.source = source
        self.current = 0
        self.errors: list[ParseError] = []
        self._panic_depth = 0

    # ------------------------------------------------------------------ API

    def parse(self) -> ParseResult:
        statements: list[dict[str, Any]] = []
        guard = 0
        while not self._is_at_end() and guard < self.MAX_SYNC_STEPS * 4:
            guard += 1
            before = self.current
            stmt = self._parse_statement()
            if stmt is not None:
                statements.append(stmt)
            elif self.current == before:
                # No progress — synchronize and advance at least one token
                self._synchronize()
                if not self._is_at_end() and self.current == before:
                    self._advance()

        if not self._is_at_end():
            tok = self._peek()
            self._error(
                "UnexpectedToken",
                f"Unexpected token '{tok.value or grammar.display_token(tok.type)}' "
                "after end of recoverable input",
                tok,
                expected=["end of file"],
            )

        ast = {"type": "Program", "body": statements}
        return ParseResult(ast=ast, errors=self.errors, tokens=self.tokens)

    # ----------------------------------------------------------- statements

    def _parse_statement(self) -> Optional[dict[str, Any]]:
        if self._check(INT, FLOAT):
            return self._parse_declaration()
        if self._check(IF):
            return self._parse_if_statement()
        if self._check(WHILE):
            return self._parse_while_statement()
        if self._check(LBRACE):
            return self._parse_block()
        if self._check(IDENTIFIER):
            # Could be assignment; peek ahead for '='
            if self._check_next(ASSIGN):
                return self._parse_assignment()
            tok = self._peek()
            self._error(
                "UnexpectedToken",
                f"Unexpected identifier '{tok.value}' — expected assignment or declaration",
                tok,
                expected=["="],
            )
            self._synchronize()
            return None
        if self._check(ELSE):
            tok = self._peek()
            self._error(
                "UnexpectedToken",
                "'else' without matching 'if'",
                tok,
                expected=list(grammar.STATEMENT_START),
            )
            self._advance()
            return None
        if self._check(SEMICOLON):
            tok = self._peek()
            self._error(
                "ExtraToken",
                "Unexpected extra ';'",
                tok,
                expected=list(grammar.STATEMENT_START),
            )
            self._advance()
            return None

        tok = self._peek()
        if tok.type == EOF:
            return None
        self._error(
            "UnexpectedToken",
            f"Unexpected token '{tok.value or grammar.display_token(tok.type)}'",
            tok,
            expected=[grammar.display_token(t) for t in sorted(grammar.STATEMENT_START)],
        )
        self._synchronize()
        return None

    def _parse_declaration(self) -> Optional[dict[str, Any]]:
        type_tok = self._advance()  # int | float
        name_tok = self._consume(
            IDENTIFIER,
            error_type="MalformedDeclaration",
            message="Expected identifier in variable declaration",
            expected=["identifier"],
        )
        if name_tok is None:
            self._synchronize()
            return None

        initializer = None
        if self._match(ASSIGN):
            initializer = self._parse_expression()
            if initializer is None:
                self._error(
                    "MissingOperand",
                    "Expected expression after '=' in declaration",
                    self._peek(),
                    expected=["expression"],
                )

        semi = self._consume(
            SEMICOLON,
            error_type="MissingSemicolon",
            message="Expected ';' after variable declaration",
            expected=[";"],
        )
        if semi is None:
            # Do not abort the whole program — allow following statements
            self._synchronize_soft()

        node: dict[str, Any] = {
            "type": "Declaration",
            "var_type": type_tok.value,
            "name": name_tok.value,
            "line": type_tok.line,
            "column": type_tok.column,
        }
        if initializer is not None:
            node["initializer"] = initializer
        return node

    def _parse_assignment(self) -> Optional[dict[str, Any]]:
        name_tok = self._advance()
        assign_tok = self._consume(
            ASSIGN,
            error_type="InvalidAssignment",
            message="Expected '=' in assignment",
            expected=["="],
        )
        if assign_tok is None:
            self._synchronize()
            return None

        value = self._parse_expression()
        if value is None:
            self._error(
                "MissingOperand",
                "Expected expression after '=' in assignment",
                self._peek(),
                expected=["expression"],
            )

        semi = self._consume(
            SEMICOLON,
            error_type="MissingSemicolon",
            message="Expected ';' after assignment",
            expected=[";"],
        )
        if semi is None:
            self._synchronize_soft()

        return {
            "type": "Assignment",
            "name": name_tok.value,
            "value": value,
            "line": name_tok.line,
            "column": name_tok.column,
        }

    def _parse_if_statement(self) -> Optional[dict[str, Any]]:
        if_tok = self._advance()
        open_paren = self._consume(
            LPAREN,
            error_type="MissingOpeningParenthesis",
            message="Expected '(' after 'if'",
            expected=["("],
        )
        condition = self._parse_expression()
        if condition is None and open_paren is not None:
            self._error(
                "MissingOperand",
                "Expected condition expression inside 'if (...)'",
                self._peek(),
                expected=["expression"],
            )

        close_paren = self._consume(
            RPAREN,
            error_type="MissingClosingParenthesis",
            message="Expected ')' after if condition",
            expected=[")"],
        )
        if close_paren is None and self._check(LBRACE):
            # Common case: if (cond {  — continue into block
            pass

        then_branch = self._require_block("if")
        else_branch = None
        if self._match(ELSE):
            else_branch = self._require_block("else")

        return {
            "type": "IfStatement",
            "condition": condition,
            "then_branch": then_branch,
            "else_branch": else_branch,
            "line": if_tok.line,
            "column": if_tok.column,
        }

    def _parse_while_statement(self) -> Optional[dict[str, Any]]:
        while_tok = self._advance()
        self._consume(
            LPAREN,
            error_type="MissingOpeningParenthesis",
            message="Expected '(' after 'while'",
            expected=["("],
        )
        condition = self._parse_expression()
        if condition is None:
            self._error(
                "MissingOperand",
                "Expected condition expression inside 'while (...)'",
                self._peek(),
                expected=["expression"],
            )
        self._consume(
            RPAREN,
            error_type="MissingClosingParenthesis",
            message="Expected ')' after while condition",
            expected=[")"],
        )
        body = self._require_block("while")
        return {
            "type": "WhileStatement",
            "condition": condition,
            "body": body,
            "line": while_tok.line,
            "column": while_tok.column,
        }

    def _require_block(self, context: str) -> Optional[dict[str, Any]]:
        if self._check(LBRACE):
            return self._parse_block()
        self._error(
            "MissingOpeningBrace",
            f"Expected '{{' to start {context} body",
            self._peek(),
            expected=["{"],
        )
        # Attempt to parse a single statement as degraded recovery
        stmt = None
        if self._check(*grammar.STATEMENT_START - {LBRACE}):
            stmt = self._parse_statement()
        return {
            "type": "Block",
            "body": [stmt] if stmt is not None else [],
            "recovered": True,
        }

    def _parse_block(self) -> dict[str, Any]:
        open_tok = self._advance()  # {
        body: list[dict[str, Any]] = []
        guard = 0
        while not self._check(RBRACE) and not self._is_at_end() and guard < self.MAX_SYNC_STEPS:
            guard += 1
            before = self.current
            stmt = self._parse_statement()
            if stmt is not None:
                body.append(stmt)
            elif self.current == before:
                if self._check(RBRACE) or self._is_at_end():
                    break
                self._synchronize()
                if self.current == before and not self._is_at_end():
                    self._advance()

        if not self._match(RBRACE):
            self._error(
                "MissingClosingBrace",
                "Expected '}' to close block",
                self._peek(),
                expected=["}"],
            )

        return {
            "type": "Block",
            "body": body,
            "line": open_tok.line,
            "column": open_tok.column,
        }

    # ---------------------------------------------------------- expressions

    def _parse_expression(self) -> Optional[dict[str, Any]]:
        if not self._check(*grammar.EXPRESSION_START):
            return None
        return self._parse_equality()

    def _parse_equality(self) -> Optional[dict[str, Any]]:
        left = self._parse_comparison()
        if left is None:
            return None
        while self._check(*grammar.EQUALITY_OPS):
            op = self._advance()
            right = self._parse_comparison()
            if right is None:
                self._error(
                    "MissingOperand",
                    f"Expected expression after '{op.value}'",
                    self._peek(),
                    expected=["expression"],
                )
                break
            left = {
                "type": "BinaryExpression",
                "operator": op.value,
                "left": left,
                "right": right,
                "line": op.line,
                "column": op.column,
            }
        return left

    def _parse_comparison(self) -> Optional[dict[str, Any]]:
        left = self._parse_term()
        if left is None:
            return None
        while self._check(*grammar.COMPARISON_OPS):
            op = self._advance()
            right = self._parse_term()
            if right is None:
                self._error(
                    "MissingOperand",
                    f"Expected expression after '{op.value}'",
                    self._peek(),
                    expected=["expression"],
                )
                break
            left = {
                "type": "BinaryExpression",
                "operator": op.value,
                "left": left,
                "right": right,
                "line": op.line,
                "column": op.column,
            }
        return left

    def _parse_term(self) -> Optional[dict[str, Any]]:
        left = self._parse_factor()
        if left is None:
            return None
        while self._check(*grammar.TERM_OPS):
            op = self._advance()
            right = self._parse_factor()
            if right is None:
                self._error(
                    "MissingOperand",
                    f"Expected expression after '{op.value}'",
                    self._peek(),
                    expected=["expression"],
                )
                break
            left = {
                "type": "BinaryExpression",
                "operator": op.value,
                "left": left,
                "right": right,
                "line": op.line,
                "column": op.column,
            }
        return left

    def _parse_factor(self) -> Optional[dict[str, Any]]:
        left = self._parse_unary()
        if left is None:
            return None
        while self._check(*grammar.FACTOR_OPS):
            op = self._advance()
            right = self._parse_unary()
            if right is None:
                self._error(
                    "MissingOperand",
                    f"Expected expression after '{op.value}'",
                    self._peek(),
                    expected=["expression"],
                )
                break
            left = {
                "type": "BinaryExpression",
                "operator": op.value,
                "left": left,
                "right": right,
                "line": op.line,
                "column": op.column,
            }
        return left

    def _parse_unary(self) -> Optional[dict[str, Any]]:
        if self._check(MINUS):
            op = self._advance()
            operand = self._parse_unary()
            if operand is None:
                self._error(
                    "MissingOperand",
                    "Expected expression after unary '-'",
                    self._peek(),
                    expected=["expression"],
                )
                return None
            return {
                "type": "UnaryExpression",
                "operator": op.value,
                "argument": operand,
                "line": op.line,
                "column": op.column,
            }
        return self._parse_primary()

    def _parse_primary(self) -> Optional[dict[str, Any]]:
        if self._check(NUMBER):
            tok = self._advance()
            return {
                "type": "Literal",
                "value": tok.value,
                "line": tok.line,
                "column": tok.column,
            }
        if self._check(IDENTIFIER):
            tok = self._advance()
            return {
                "type": "Identifier",
                "name": tok.value,
                "line": tok.line,
                "column": tok.column,
            }
        if self._check(LPAREN):
            open_tok = self._advance()
            expr = self._parse_expression()
            if expr is None:
                self._error(
                    "MissingOperand",
                    "Expected expression after '('",
                    self._peek(),
                    expected=["expression"],
                )
            self._consume(
                RPAREN,
                error_type="MissingClosingParenthesis",
                message="Expected ')' after expression",
                expected=[")"],
            )
            return {
                "type": "Grouping",
                "expression": expr,
                "line": open_tok.line,
                "column": open_tok.column,
            }

        # Adjacent operands without operator: e.g. x y  or  1 2
        # Handled by caller when expression parse returns None / unexpected.
        return None

    # -------------------------------------------------------------- helpers

    def _consume(
        self,
        token_type: str,
        *,
        error_type: str,
        message: str,
        expected: list[str],
    ) -> Optional[Token]:
        if self._check(token_type):
            return self._advance()
        self._error(error_type, message, self._peek(), expected=expected)
        return None

    def _error(
        self,
        error_type: str,
        message: str,
        token: Token,
        expected: Optional[list[str]] = None,
    ) -> None:
        found = token.value if token.value else grammar.display_token(token.type)
        # Avoid flooding identical consecutive errors at the same position
        if self.errors:
            last = self.errors[-1]
            if (
                last.type == error_type
                and last.line == token.line
                and last.column == token.column
                and last.message == message
            ):
                return
        self.errors.append(
            ParseError(
                type=error_type,
                message=message,
                line=token.line,
                column=token.column,
                found=found,
                expected=expected or [],
            )
        )

    def _synchronize(self) -> None:
        """Panic-mode: discard tokens until a statement boundary."""
        self._panic_depth += 1
        if self._panic_depth > self.MAX_SYNC_STEPS:
            # Hard stop advance to EOF to prevent infinite loops
            self.current = max(0, len(self.tokens) - 1)
            return

        if not self._is_at_end():
            # If currently on ';' consume it and resume
            if self._check(SEMICOLON):
                self._advance()
                return

        while not self._is_at_end():
            if self._previous().type == SEMICOLON:
                return
            if self._check(*grammar.SYNC_TOKENS - {SEMICOLON}):
                return
            if self._check(RBRACE):
                return
            self._advance()

    def _synchronize_soft(self) -> None:
        """Light sync used after missing semicolon — stop before next statement start."""
        if self._check(*grammar.STATEMENT_START) or self._check(RBRACE, EOF, ELSE):
            return
        self._synchronize()

    def _match(self, *types: str) -> bool:
        if self._check(*types):
            self._advance()
            return True
        return False

    def _check(self, *types: str) -> bool:
        if self._is_at_end() and EOF not in types:
            return False
        return self._peek().type in types

    def _check_next(self, *types: str) -> bool:
        if self.current + 1 >= len(self.tokens):
            return False
        return self.tokens[self.current + 1].type in types

    def _advance(self) -> Token:
        if not self._is_at_end():
            self.current += 1
        return self._previous()

    def _is_at_end(self) -> bool:
        return self._peek().type == EOF

    def _peek(self) -> Token:
        return self.tokens[self.current]

    def _previous(self) -> Token:
        if self.current == 0:
            return self.tokens[0]
        return self.tokens[self.current - 1]


def parse(source: str) -> ParseResult:
    """Lex then parse source text. Lexical errors are attached as structured errors."""
    lex = tokenize(source)
    parser = Parser(lex.tokens, source=source)
    result = parser.parse()
    for err in lex.errors:
        result.errors.insert(
            0,
            ParseError(
                type=err.type,
                message=err.message,
                line=err.line,
                column=err.column,
                found=err.character,
                expected=[],
            ),
        )
    return result


def parse_tokens(tokens: list[Token], source: str = "") -> ParseResult:
    """Parse a pre-built token list (useful for tests / later recovery)."""
    return Parser(tokens, source=source).parse()
