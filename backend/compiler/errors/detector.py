"""
Structured syntax error detection for the mini C-like language.

Normalizes parser diagnostics into rich DetectedError objects with
human-readable explanations and source fragments. Also performs a
lightweight token-pattern scan for missing-operator cases that pure
panic-mode parsing may under-specify.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional

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
    RPAREN,
    SEMICOLON,
    Token,
    WHILE,
    tokenize,
)
from compiler.parser import ParseError, ParseResult, parse


# Canonical error kinds (Phase 4 detection catalog)
MISSING_SEMICOLON = "MissingSemicolon"
MISSING_CLOSING_PARENTHESIS = "MissingClosingParenthesis"
MISSING_OPENING_PARENTHESIS = "MissingOpeningParenthesis"
MISSING_CLOSING_BRACE = "MissingClosingBrace"
MISSING_OPENING_BRACE = "MissingOpeningBrace"
UNEXPECTED_TOKEN = "UnexpectedToken"
EXTRA_TOKEN = "ExtraToken"
MISSING_OPERAND = "MissingOperand"
MISSING_OPERATOR = "MissingOperator"
INVALID_ASSIGNMENT = "InvalidAssignment"
MALFORMED_DECLARATION = "MalformedDeclaration"
UNTERMINATED_COMMENT = "UnterminatedComment"
INVALID_NUMBER = "InvalidNumber"
UNEXPECTED_CHARACTER = "UnexpectedCharacter"

EXPLANATIONS: dict[str, str] = {
    MISSING_SEMICOLON: (
        "A statement in this language must end with a semicolon. "
        "The parser reached the next token before finding ';'."
    ),
    MISSING_CLOSING_PARENTHESIS: (
        "A closing parenthesis ')' is required to finish a grouped expression "
        "or a condition list such as if (...) / while (...)."
    ),
    MISSING_OPENING_PARENTHESIS: (
        "An opening parenthesis '(' is required after keywords like 'if' and 'while' "
        "before the condition expression."
    ),
    MISSING_CLOSING_BRACE: (
        "A closing brace '}' is required to terminate a block that started with '{'."
    ),
    MISSING_OPENING_BRACE: (
        "An opening brace '{' is required to start the body of an if, else, or while."
    ),
    UNEXPECTED_TOKEN: (
        "The token at this position does not fit the grammar production being parsed."
    ),
    EXTRA_TOKEN: (
        "An extra token appears where the grammar does not allow it "
        "(for example a stray ';')."
    ),
    MISSING_OPERAND: (
        "An operator or '=' was found without a valid expression operand beside it."
    ),
    MISSING_OPERATOR: (
        "Two values or identifiers appear next to each other without an operator between them."
    ),
    INVALID_ASSIGNMENT: (
        "An assignment must follow the form: identifier '=' expression ';'."
    ),
    MALFORMED_DECLARATION: (
        "A variable declaration must follow: type identifier ('=' expression)? ';'."
    ),
    UNTERMINATED_COMMENT: "A block comment starting with /* was never closed with */.",
    INVALID_NUMBER: "The numeric literal is not a valid integer or floating-point value.",
    UNEXPECTED_CHARACTER: "This character is not part of the language alphabet.",
}

# Map raw parser / lexer type names onto the detection catalog
TYPE_ALIASES: dict[str, str] = {
    "MissingSemicolon": MISSING_SEMICOLON,
    "MissingClosingParenthesis": MISSING_CLOSING_PARENTHESIS,
    "MissingOpeningParenthesis": MISSING_OPENING_PARENTHESIS,
    "MissingClosingBrace": MISSING_CLOSING_BRACE,
    "MissingOpeningBrace": MISSING_OPENING_BRACE,
    "UnexpectedToken": UNEXPECTED_TOKEN,
    "ExtraToken": EXTRA_TOKEN,
    "MissingOperand": MISSING_OPERAND,
    "MissingOperator": MISSING_OPERATOR,
    "InvalidAssignment": INVALID_ASSIGNMENT,
    "MalformedDeclaration": MALFORMED_DECLARATION,
    "UnterminatedComment": UNTERMINATED_COMMENT,
    "InvalidNumber": INVALID_NUMBER,
    "UnexpectedCharacter": UNEXPECTED_CHARACTER,
}

OPERAND_LIKE = frozenset({IDENTIFIER, NUMBER, RPAREN, RBRACE})
OPERATOR_LIKE = frozenset(
    {
        PLUS,
        MINUS,
        MULTIPLY,
        DIVIDE,
        EQ,
        NEQ,
        LT,
        GT,
        LTE,
        GTE,
        ASSIGN,
    }
)
VALUE_START = frozenset({IDENTIFIER, NUMBER, LPAREN})


@dataclass
class DetectedError:
    """Fully structured syntax error ready for classification / UI."""

    type: str
    message: str
    explanation: str
    line: int
    column: int
    found: Optional[str] = None
    expected: list[str] = field(default_factory=list)
    fragment: str = ""
    source: str = "parser"  # parser | lexer | pattern

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DetectionResult:
    errors: list[DetectedError]
    parse_result: Optional[ParseResult] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "errors": [e.to_dict() for e in self.errors],
            "total_errors": len(self.errors),
            "success": len(self.errors) == 0,
            "ast": self.parse_result.ast if self.parse_result else None,
            "tokens": (
                [t.to_dict() for t in self.parse_result.tokens]
                if self.parse_result
                else []
            ),
        }


class SyntaxErrorDetector:
    """Detect and enrich syntax errors from source code."""

    def __init__(self, source: str):
        self.source = source if source is not None else ""
        self.lines = self.source.splitlines() or [""]

    def detect(self, parse_result: Optional[ParseResult] = None) -> DetectionResult:
        result = parse_result if parse_result is not None else parse(self.source)
        detected: list[DetectedError] = []

        for err in result.errors:
            detected.append(self._from_parse_error(err))

        # Pattern pass for missing operators — prefer these over vague unexpected-token
        for pattern_err in self._detect_missing_operators(result.tokens):
            detected = [
                e
                for e in detected
                if not (
                    e.line == pattern_err.line
                    and abs(e.column - pattern_err.column) <= 2
                    and e.type in {UNEXPECTED_TOKEN, MISSING_SEMICOLON, MISSING_OPERAND}
                )
            ]
            if not self._is_duplicate(detected, pattern_err):
                detected.append(pattern_err)

        detected.sort(key=lambda e: (e.line, e.column, e.type))
        return DetectionResult(errors=detected, parse_result=result)

    # ----------------------------------------------------------------- core

    def _from_parse_error(self, err: ParseError) -> DetectedError:
        err_type = TYPE_ALIASES.get(err.type, err.type)
        explanation = EXPLANATIONS.get(
            err_type,
            "A syntax rule of the mini-language was violated at this location.",
        )
        message = err.message or self._default_message(err_type, err.expected, err.found)
        line = err.line
        column = err.column
        fragment = self._fragment_at(line, column)

        # Missing ';': parser often points at the *next* statement. Attribute the
        # error to the end of the previous non-empty line so repairs insert there.
        if err_type == MISSING_SEMICOLON:
            line, column, fragment = self._reattribute_missing_semicolon(line, column)

        return DetectedError(
            type=err_type,
            message=message,
            explanation=explanation,
            line=line,
            column=column,
            found=err.found,
            expected=list(err.expected or []),
            fragment=fragment,
            source="lexer"
            if err_type
            in {UNTERMINATED_COMMENT, INVALID_NUMBER, UNEXPECTED_CHARACTER}
            else "parser",
        )

    def _reattribute_missing_semicolon(
        self,
        line: int,
        column: int,
    ) -> tuple[int, int, str]:
        """Move MissingSemicolon to EOL of the unfinished previous statement."""
        # If pointing mid-line, keep but fragment is that line; insert at EOL.
        if line >= 1 and line <= len(self.lines):
            current = self.lines[line - 1]
            # Error at beginning of a new statement line → fix previous line
            if column <= 1 and line > 1:
                prev_idx = line - 2
                while prev_idx >= 0 and not self.lines[prev_idx].strip():
                    prev_idx -= 1
                if prev_idx >= 0:
                    prev = self.lines[prev_idx]
                    if not prev.rstrip().endswith(";"):
                        return prev_idx + 1, len(prev) + 1, prev.strip()
            # Same-line case: unfinished statement, insert at end of this line
            if not current.rstrip().endswith(";"):
                # If column is past useful content or at next token mid-line,
                # still use this line's end when it looks like a declaration/assign
                stripped = current.strip()
                if stripped and not stripped.endswith(";"):
                    return line, len(current) + 1, stripped
        return line, column, self._fragment_at(line, column)

    def _detect_missing_operators(self, tokens: list[Token]) -> list[DetectedError]:
        """
        Flag adjacent operands such as `x y` or `10 20` inside expression-like
        contexts when no operator separates them.
        """
        findings: list[DetectedError] = []
        usable = [t for t in tokens if t.type != EOF]
        i = 0
        while i < len(usable) - 1:
            left = usable[i]
            right = usable[i + 1]
            if left.type in VALUE_START and right.type in VALUE_START:
                # Skip declaration header: int x / float y
                if left.type in {INT, FLOAT} and right.type == IDENTIFIER:
                    i += 1
                    continue
                # Skip `) {` style — not an operator issue
                if left.type == RPAREN or right.type == LBRACE:
                    i += 1
                    continue
                # Only treat IDENTIFIER/NUMBER adjacency as missing operator
                if left.type in {IDENTIFIER, NUMBER} and right.type in {
                    IDENTIFIER,
                    NUMBER,
                }:
                    # Avoid flagging `x =` style handled elsewhere; only pure adjacency
                    findings.append(
                        DetectedError(
                            type=MISSING_OPERATOR,
                            message=(
                                f"Missing operator between '{left.value}' and '{right.value}'"
                            ),
                            explanation=EXPLANATIONS[MISSING_OPERATOR],
                            line=right.line,
                            column=right.column,
                            found=right.value,
                            expected=["+", "-", "*", "/", "==", "!=", "<", ">", "<=", ">="],
                            fragment=self._fragment_at(right.line, right.column),
                            source="pattern",
                        )
                    )
            i += 1
        return findings

    # -------------------------------------------------------------- helpers

    def _fragment_at(self, line: int, column: int) -> str:
        if line < 1 or line > len(self.lines):
            return self.source.strip()[:80]
        text = self.lines[line - 1]
        # Prefer the full line as the fragment (clear for demos / reports)
        return text.strip() if text.strip() else text

    def _default_message(
        self,
        err_type: str,
        expected: Optional[list[str]],
        found: Optional[str],
    ) -> str:
        exp = ", ".join(expected) if expected else "a valid token"
        if found:
            return f"{err_type}: found '{found}', expected {exp}"
        return f"{err_type}: expected {exp}"

    def _is_duplicate(self, existing: list[DetectedError], candidate: DetectedError) -> bool:
        for err in existing:
            if (
                err.type == candidate.type
                and err.line == candidate.line
                and abs(err.column - candidate.column) <= 2
            ):
                return True
        return False


def detect_syntax_errors(
    source: str,
    parse_result: Optional[ParseResult] = None,
) -> DetectionResult:
    """Public entry point used by the API and later recovery stages."""
    return SyntaxErrorDetector(source).detect(parse_result=parse_result)


def describe_error_catalog() -> list[dict[str, str]]:
    """Return the detection catalog for educational / UI use."""
    return [
        {"type": key, "explanation": value}
        for key, value in EXPLANATIONS.items()
    ]
