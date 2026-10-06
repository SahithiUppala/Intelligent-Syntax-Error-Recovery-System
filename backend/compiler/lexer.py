"""
Lexical analyzer for the mini C-like language.

Produces a stream of tokens with line/column positions and collects
lexical errors without crashing on invalid input.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Optional


# Token type constants (exported for parser / tests)
INT = "INT"
FLOAT = "FLOAT"
IF = "IF"
ELSE = "ELSE"
WHILE = "WHILE"
IDENTIFIER = "IDENTIFIER"
NUMBER = "NUMBER"
PLUS = "PLUS"
MINUS = "MINUS"
MULTIPLY = "MULTIPLY"
DIVIDE = "DIVIDE"
ASSIGN = "ASSIGN"
EQ = "EQ"
NEQ = "NEQ"
LT = "LT"
GT = "GT"
LTE = "LTE"
GTE = "GTE"
LPAREN = "LPAREN"
RPAREN = "RPAREN"
LBRACE = "LBRACE"
RBRACE = "RBRACE"
SEMICOLON = "SEMICOLON"
EOF = "EOF"

KEYWORDS = {
    "int": INT,
    "float": FLOAT,
    "if": IF,
    "else": ELSE,
    "while": WHILE,
}


@dataclass
class Token:
    type: str
    value: str
    line: int
    column: int

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class LexicalError:
    type: str
    message: str
    line: int
    column: int
    character: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class LexerResult:
    tokens: list[Token]
    errors: list[LexicalError]

    def to_dict(self) -> dict:
        return {
            "tokens": [t.to_dict() for t in self.tokens],
            "lexical_errors": [e.to_dict() for e in self.errors],
            "success": len(self.errors) == 0,
        }


class Lexer:
    """Scan source text into tokens; collect lexical errors separately."""

    def __init__(self, source: str):
        self.source = source if source is not None else ""
        self.length = len(self.source)
        self.pos = 0
        self.line = 1
        self.column = 1
        self.tokens: list[Token] = []
        self.errors: list[LexicalError] = []

    def tokenize(self) -> LexerResult:
        while not self._is_at_end():
            self._skip_whitespace_and_comments()
            if self._is_at_end():
                break

            start_line = self.line
            start_col = self.column
            ch = self._peek()

            if ch.isalpha() or ch == "_":
                self._scan_identifier_or_keyword(start_line, start_col)
            elif ch.isdigit() or (ch == "." and self._peek_next().isdigit()):
                self._scan_number(start_line, start_col)
            elif ch == "=":
                self._advance()
                if self._match("="):
                    self._emit(EQ, "==", start_line, start_col)
                else:
                    self._emit(ASSIGN, "=", start_line, start_col)
            elif ch == "!":
                self._advance()
                if self._match("="):
                    self._emit(NEQ, "!=", start_line, start_col)
                else:
                    self._error(
                        "UnexpectedCharacter",
                        "Unexpected '!' — did you mean '!='?",
                        start_line,
                        start_col,
                        "!",
                    )
            elif ch == "<":
                self._advance()
                if self._match("="):
                    self._emit(LTE, "<=", start_line, start_col)
                else:
                    self._emit(LT, "<", start_line, start_col)
            elif ch == ">":
                self._advance()
                if self._match("="):
                    self._emit(GTE, ">=", start_line, start_col)
                else:
                    self._emit(GT, ">", start_line, start_col)
            elif ch == "+":
                self._advance()
                self._emit(PLUS, "+", start_line, start_col)
            elif ch == "-":
                self._advance()
                self._emit(MINUS, "-", start_line, start_col)
            elif ch == "*":
                self._advance()
                self._emit(MULTIPLY, "*", start_line, start_col)
            elif ch == "/":
                # Comments already handled; lone '/' is division
                self._advance()
                self._emit(DIVIDE, "/", start_line, start_col)
            elif ch == "(":
                self._advance()
                self._emit(LPAREN, "(", start_line, start_col)
            elif ch == ")":
                self._advance()
                self._emit(RPAREN, ")", start_line, start_col)
            elif ch == "{":
                self._advance()
                self._emit(LBRACE, "{", start_line, start_col)
            elif ch == "}":
                self._advance()
                self._emit(RBRACE, "}", start_line, start_col)
            elif ch == ";":
                self._advance()
                self._emit(SEMICOLON, ";", start_line, start_col)
            else:
                bad = self._advance()
                self._error(
                    "UnexpectedCharacter",
                    f"Unexpected character '{bad}'",
                    start_line,
                    start_col,
                    bad,
                )

        self._emit(EOF, "", self.line, self.column)
        return LexerResult(tokens=self.tokens, errors=self.errors)

    # --- scanners ---------------------------------------------------------

    def _scan_identifier_or_keyword(self, start_line: int, start_col: int) -> None:
        start = self.pos
        while not self._is_at_end() and (self._peek().isalnum() or self._peek() == "_"):
            self._advance()
        text = self.source[start : self.pos]
        token_type = KEYWORDS.get(text, IDENTIFIER)
        self._emit(token_type, text, start_line, start_col)

    def _scan_number(self, start_line: int, start_col: int) -> None:
        start = self.pos
        saw_dot = False

        # Leading dot form: .5
        if self._peek() == ".":
            saw_dot = True
            self._advance()
            if not self._peek().isdigit():
                self._error(
                    "InvalidNumber",
                    "Invalid number literal starting with '.'",
                    start_line,
                    start_col,
                    ".",
                )
                return
            while self._peek().isdigit():
                self._advance()
        else:
            while self._peek().isdigit():
                self._advance()
            if self._peek() == "." and self._peek_next().isdigit():
                saw_dot = True
                self._advance()
                while self._peek().isdigit():
                    self._advance()
            elif self._peek() == ".":
                # Trailing lone dot — consume and report
                self._advance()
                text = self.source[start : self.pos]
                self._error(
                    "InvalidNumber",
                    f"Invalid number literal '{text}'",
                    start_line,
                    start_col,
                    text,
                )
                return

        # Reject identifier-like continuation: 10abc
        if self._peek().isalpha() or self._peek() == "_":
            while not self._is_at_end() and (self._peek().isalnum() or self._peek() == "_"):
                self._advance()
            text = self.source[start : self.pos]
            self._error(
                "InvalidNumber",
                f"Invalid number literal '{text}'",
                start_line,
                start_col,
                text,
            )
            return

        text = self.source[start : self.pos]
        self._emit(NUMBER, text, start_line, start_col)
        _ = saw_dot  # floats and ints share NUMBER type per language spec

    def _skip_whitespace_and_comments(self) -> None:
        while not self._is_at_end():
            ch = self._peek()
            if ch in " \t\r":
                self._advance()
                continue
            if ch == "\n":
                self._advance()
                continue
            # Line comment //
            if ch == "/" and self._peek_next() == "/":
                self._advance()
                self._advance()
                while not self._is_at_end() and self._peek() != "\n":
                    self._advance()
                continue
            # Block comment /* */
            if ch == "/" and self._peek_next() == "*":
                start_line = self.line
                start_col = self.column
                self._advance()
                self._advance()
                closed = False
                while not self._is_at_end():
                    if self._peek() == "*" and self._peek_next() == "/":
                        self._advance()
                        self._advance()
                        closed = True
                        break
                    self._advance()
                if not closed:
                    self._error(
                        "UnterminatedComment",
                        "Unterminated block comment",
                        start_line,
                        start_col,
                        "/*",
                    )
                continue
            break

    # --- helpers ----------------------------------------------------------

    def _emit(self, token_type: str, value: str, line: int, column: int) -> None:
        self.tokens.append(Token(type=token_type, value=value, line=line, column=column))

    def _error(
        self,
        err_type: str,
        message: str,
        line: int,
        column: int,
        character: Optional[str] = None,
    ) -> None:
        self.errors.append(
            LexicalError(
                type=err_type,
                message=message,
                line=line,
                column=column,
                character=character,
            )
        )

    def _is_at_end(self) -> bool:
        return self.pos >= self.length

    def _peek(self) -> str:
        if self._is_at_end():
            return "\0"
        return self.source[self.pos]

    def _peek_next(self) -> str:
        if self.pos + 1 >= self.length:
            return "\0"
        return self.source[self.pos + 1]

    def _advance(self) -> str:
        ch = self.source[self.pos]
        self.pos += 1
        if ch == "\n":
            self.line += 1
            self.column = 1
        else:
            self.column += 1
        return ch

    def _match(self, expected: str) -> bool:
        if self._is_at_end() or self._peek() != expected:
            return False
        self._advance()
        return True


def tokenize(source: str) -> LexerResult:
    """Convenience entry point used by the API and tests."""
    return Lexer(source).tokenize()
