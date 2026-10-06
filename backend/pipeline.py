"""
Analysis pipeline orchestrator.

Keeps FastAPI handlers thin: compiler modules stay independent, while this
module sequences them and builds the stage-aware API payload.
"""

from __future__ import annotations

from typing import Any

from compiler.errors.classifier import classify_errors
from compiler.errors.detector import detect_syntax_errors
from compiler.lexer import tokenize
from compiler.parser import parse
from compiler.recovery.candidate_generator import generate_candidates
from compiler.recovery.recovery_engine import recover_source
from compiler.recovery.scorer import score_candidates
from compiler.reports.report_generator import generate_report

DEMO_PROGRAM = """int x = 10
int y = 20;

if (x < y {
    x = x + 1;
}
"""

DEMO_EXPECTED_CORRECTED = """int x = 10;
int y = 20;

if (x < y) {
    x = x + 1;
}
"""

MULTI_ERROR_CONTINUE = """int x = 10
int y = ;
int z = 30;
"""

MISSING_BRACE = """if (x < y)
    x = x + 1;
"""

MISSING_OPERATOR = """int z = x y;
"""

WHILE_MISSING_PAREN = """while x > 0) {
    x = x - 1;
}
"""

EXTRA_SEMICOLON = """;
int x = 1;
"""

NESTED_VALID = """int a = 1;
int b = 2;
if (a < b) {
    while (a < 5) {
        a = a + 1;
    }
} else {
    a = 0;
}
"""

EXAMPLE_PROGRAMS = [
    {
        "id": "demo",
        "name": "Demo: missing semicolon + missing parenthesis",
        "description": (
            "Primary demonstration. Detects MissingSemicolon after `int x = 10` and "
            "MissingClosingParenthesis in the if-condition, then recovers both."
        ),
        "code": DEMO_PROGRAM,
        "expected_corrected": DEMO_EXPECTED_CORRECTED,
        "expected_error_types": ["MissingSemicolon", "MissingClosingParenthesis"],
    },
    {
        "id": "missing_semicolon",
        "name": "Missing semicolon only",
        "description": "Single INSERTION_ERROR at end of a declaration.",
        "code": "int x = 10\nint y = 20;\n",
        "expected_corrected": "int x = 10;\nint y = 20;\n",
        "expected_error_types": ["MissingSemicolon"],
    },
    {
        "id": "continue_after_errors",
        "name": "Continue parsing after multiple errors",
        "description": (
            "Missing semicolon on line 1 and missing operand on line 2; "
            "line 3 remains valid and parsing continues."
        ),
        "code": MULTI_ERROR_CONTINUE,
        "expected_corrected": None,
        "expected_error_types": ["MissingSemicolon", "MissingOperand"],
    },
    {
        "id": "missing_operand",
        "name": "Missing operand after '='",
        "description": "EXPRESSION_ERROR with candidate literal inserts.",
        "code": "int y = ;\nint z = 30;\n",
        "expected_corrected": None,
        "expected_error_types": ["MissingOperand"],
    },
    {
        "id": "missing_operator",
        "name": "Missing operator between operands",
        "description": "Pattern-detected MissingOperator between `x` and `y`.",
        "code": MISSING_OPERATOR,
        "expected_corrected": None,
        "expected_error_types": ["MissingOperator"],
    },
    {
        "id": "missing_opening_brace",
        "name": "Missing opening brace after if",
        "description": "DELIMITER_ERROR — if body should start with `{`.",
        "code": MISSING_BRACE,
        "expected_corrected": None,
        "expected_error_types": ["MissingOpeningBrace"],
    },
    {
        "id": "while_missing_paren",
        "name": "While missing opening parenthesis",
        "description": "DELIMITER_ERROR on while-condition.",
        "code": WHILE_MISSING_PAREN,
        "expected_corrected": None,
        "expected_error_types": ["MissingOpeningParenthesis"],
    },
    {
        "id": "extra_semicolon",
        "name": "Extra leading semicolon",
        "description": "DELETION_ERROR — stray `;` before a declaration.",
        "code": EXTRA_SEMICOLON,
        "expected_corrected": None,
        "expected_error_types": ["ExtraToken"],
    },
    {
        "id": "valid",
        "name": "Valid mini-program",
        "description": "Parses cleanly with no recovery needed.",
        "code": (
            "int x = 10;\n"
            "int y = 20;\n"
            "\n"
            "if (x < y) {\n"
            "    x = x + 1;\n"
            "}\n"
        ),
        "expected_corrected": None,
        "expected_error_types": [],
    },
    {
        "id": "nested_valid",
        "name": "Valid nested if/while/else",
        "description": "Exercises nested blocks and else branch.",
        "code": NESTED_VALID,
        "expected_corrected": None,
        "expected_error_types": [],
    },
]


def run_tokenize(code: str) -> dict[str, Any]:
    result = tokenize(code)
    payload = result.to_dict()
    payload["message"] = (
        "Lexical analysis completed"
        if payload["success"]
        else f"Lexical analysis completed with {len(payload['lexical_errors'])} error(s)"
    )
    return payload


def run_parse(code: str) -> dict[str, Any]:
    result = parse(code)
    payload = result.to_dict()
    payload["message"] = (
        "Parsing completed"
        if payload["success"]
        else f"Parsing completed with {len(payload['errors'])} error(s)"
    )
    return payload


def _stage(
    name: str,
    status: str,
    *,
    detail: str = "",
    data: Any = None,
) -> dict[str, Any]:
    return {
        "name": name,
        "status": status,
        "detail": detail,
        "data": data,
    }


def run_analyze(code: str) -> dict[str, Any]:
    """
    Full pipeline:
      Source → Lex → Parse → Detect → Classify → Candidates → Score → Recover → Report
    """
    source = code if code is not None else ""

    lex_result = tokenize(source)
    lex_payload = lex_result.to_dict()
    lex_ok = lex_payload["success"]

    parse_result = parse(source)
    parse_payload = parse_result.to_dict()
    parse_ok = parse_payload["success"]

    detection = detect_syntax_errors(source, parse_result=parse_result)
    detection_payload = detection.to_dict()
    detect_ok = detection_payload["success"]

    classification = classify_errors(source, detection=detection)
    class_payload = classification.to_dict()

    generation = generate_candidates(source, classification=classification)
    gen_payload = generation.to_dict()

    scored = score_candidates(source, generation=generation)
    scored_payload = scored.to_dict()

    recovery = recover_source(source)
    recovery_payload = recovery.to_dict()

    report = generate_report(
        source,
        recovery=recovery,
        classification=classification,
    )
    report_payload = report.to_dict()

    error_count = len(class_payload["errors"])
    candidate_count = scored_payload.get("total_candidates", 0)
    recovered = recovery.success
    applied = recovery.applied_count

    stages = [
        _stage(
            "Source Code",
            "completed",
            detail=f"{len(source.splitlines())} line(s), {len(source)} character(s)",
            data={"code": source},
        ),
        _stage(
            "Lexical Analysis",
            "completed" if lex_ok else "error",
            detail=f"{len(lex_payload['tokens'])} token(s)"
            + (
                f", {len(lex_payload['lexical_errors'])} lexical error(s)"
                if not lex_ok
                else ""
            ),
            data={
                "tokens": lex_payload["tokens"],
                "lexical_errors": lex_payload["lexical_errors"],
            },
        ),
        _stage(
            "Parsing",
            "completed" if parse_ok else "error",
            detail=(
                "AST built"
                if parse_ok
                else f"{len(parse_payload['errors'])} parse error(s) collected"
            ),
            data={"ast": parse_payload["ast"], "errors": parse_payload["errors"]},
        ),
        _stage(
            "Error Detection",
            "completed" if detect_ok else "error",
            detail=(
                "No syntax errors"
                if detect_ok
                else f"{detection_payload['total_errors']} structured error(s)"
            ),
            data={"errors": detection_payload["errors"]},
        ),
        _stage(
            "Classification",
            "completed" if detect_ok else "error",
            detail=(
                "No categories"
                if detect_ok
                else f"Categories: {', '.join(class_payload.get('categories') or [])}"
            ),
            data={"errors": class_payload["errors"]},
        ),
        _stage(
            "Candidate Generation",
            "completed",
            detail=f"{gen_payload.get('total_candidates', 0)} candidate(s) across "
            f"{gen_payload.get('total_errors', 0)} error(s)",
            data={"by_error": gen_payload.get("by_error", [])},
        ),
        _stage(
            "Correction Scoring",
            "completed",
            detail=f"Scored and ranked {candidate_count} candidate(s)",
            data={"by_error": scored_payload.get("by_error", [])},
        ),
        _stage(
            "Recovery",
            "recovered"
            if recovered
            else ("completed" if applied else ("completed" if detect_ok else "error")),
            detail=recovery.message,
            data={
                "actions": recovery_payload.get("actions", []),
                "applied_count": applied,
                "corrected_code": recovery.corrected_code,
            },
        ),
        _stage(
            "Result",
            "completed" if recovered or detect_ok else "error",
            detail=(
                "Analysis complete with no remaining syntax errors"
                if recovered or detect_ok
                else f"Report ready with {error_count} unresolved issue(s)"
            ),
            data={"report": report_payload},
        ),
    ]

    return {
        "tokens": lex_payload["tokens"],
        "ast": recovery.final_ast or parse_payload["ast"],
        "errors": class_payload["errors"],
        "corrections": recovery_payload.get("corrections")
        or scored_payload.get("corrections", []),
        "corrected_code": recovery.corrected_code,
        "report": report_payload,
        "stages": stages,
        "success": recovered or detect_ok,
        "message": recovery.message,
        "original_code": source,
        "pipeline": {
            "lexical_ok": lex_ok,
            "parse_ok": parse_ok,
            "detection_ok": detect_ok,
            "error_count": error_count,
            "candidate_count": candidate_count,
            "applied_count": applied,
            "recovery_success": recovered,
        },
    }


def list_examples() -> list[dict[str, Any]]:
    return EXAMPLE_PROGRAMS
