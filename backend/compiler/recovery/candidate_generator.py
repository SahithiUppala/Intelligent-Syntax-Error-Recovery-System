"""
Candidate correction generator.

For each classified syntax error, produce multiple grammar-constrained
edit candidates (insert / delete / replace). Scoring is deferred to Phase 7;
this module only generates plausible edits and records the operation used.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional, Union

from compiler.errors.classifier import (
    DELETION_ERROR,
    DELIMITER_ERROR,
    EXPRESSION_ERROR,
    INSERTION_ERROR,
    REPLACEMENT_ERROR,
    STRUCTURAL_ERROR,
    ClassifiedError,
    ClassificationResult,
    classify_errors,
)
from compiler.errors.detector import (
    EXTRA_TOKEN,
    INVALID_ASSIGNMENT,
    MALFORMED_DECLARATION,
    MISSING_CLOSING_BRACE,
    MISSING_CLOSING_PARENTHESIS,
    MISSING_OPENING_BRACE,
    MISSING_OPENING_PARENTHESIS,
    MISSING_OPERAND,
    MISSING_OPERATOR,
    MISSING_SEMICOLON,
    UNEXPECTED_TOKEN,
)

INSERT = "insert"
DELETE = "delete"
REPLACE = "replace"

# Grammar-inspired alternate tokens (not random)
ALT_STATEMENT_ENDINGS = [";", ")", "}"]
ALT_CLOSE_DELIMS = [")", ";", "}"]
ALT_OPEN_DELIMS = ["(", "{"]
ALT_OPERATORS = ["+", "-", "*", "/", "<", ">", "=="]
ALT_OPERANDS = ["0", "1", "x"]


@dataclass
class EditOperation:
    kind: str  # insert | delete | replace
    token: str = ""
    replacement: str = ""
    line: int = 1
    column: int = 1

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CorrectionCandidate:
    correction: str
    operation: EditOperation
    description: str
    error_index: int = 0
    priority_hint: int = 0  # higher = more grammar-aligned (used later by scorer)

    def to_dict(self) -> dict[str, Any]:
        return {
            "correction": self.correction,
            "operation": self.operation.to_dict(),
            "description": self.description,
            "error_index": self.error_index,
            "priority_hint": self.priority_hint,
        }


@dataclass
class ErrorCandidates:
    error: ClassifiedError
    error_index: int
    original_fragment: str
    candidates: list[CorrectionCandidate] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": self.error.to_dict(),
            "error_index": self.error_index,
            "original_fragment": self.original_fragment,
            "candidates": [c.to_dict() for c in self.candidates],
        }


@dataclass
class CandidateGenerationResult:
    source: str
    items: list[ErrorCandidates] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        flat: list[dict[str, Any]] = []
        for item in self.items:
            for cand in item.candidates:
                flat.append(
                    {
                        **cand.to_dict(),
                        "error_type": item.error.type,
                        "classification": item.error.classification,
                        "line": item.error.line,
                        "column": item.error.column,
                        "original_fragment": item.original_fragment,
                    }
                )
        return {
            "source": self.source,
            "corrections": flat,
            "by_error": [item.to_dict() for item in self.items],
            "total_candidates": len(flat),
            "total_errors": len(self.items),
        }


class CandidateGenerator:
    """Generate multiple edit candidates per classified error."""

    def generate(
        self,
        source: str,
        classified_errors: list[ClassifiedError],
    ) -> CandidateGenerationResult:
        items: list[ErrorCandidates] = []
        for index, err in enumerate(classified_errors):
            fragment = err.fragment or self._line_text(source, err.line)
            candidates = self._candidates_for_error(source, err, fragment, index)
            # Deduplicate by correction text while preserving order
            seen: set[str] = set()
            unique: list[CorrectionCandidate] = []
            for cand in candidates:
                key = cand.correction
                if key in seen:
                    continue
                seen.add(key)
                unique.append(cand)
            items.append(
                ErrorCandidates(
                    error=err,
                    error_index=index,
                    original_fragment=fragment,
                    candidates=unique,
                )
            )
        return CandidateGenerationResult(source=source, items=items)

    def _candidates_for_error(
        self,
        source: str,
        err: ClassifiedError,
        fragment: str,
        error_index: int,
    ) -> list[CorrectionCandidate]:
        err_type = err.type
        classification = err.classification

        if err_type == MISSING_SEMICOLON or (
            classification == INSERTION_ERROR and err.missing_token == ";"
        ):
            return self._missing_semicolon_candidates(source, err, fragment, error_index)

        if err_type == MISSING_CLOSING_PARENTHESIS:
            return self._missing_close_paren_candidates(source, err, fragment, error_index)

        if err_type == MISSING_OPENING_PARENTHESIS:
            return self._insert_token_variants(
                source,
                err,
                fragment,
                error_index,
                primary="(",
                alternates=["{", ";"],
                labels=["opening parenthesis", "opening brace", "semicolon"],
            )

        if err_type == MISSING_CLOSING_BRACE:
            return self._insert_token_variants(
                source,
                err,
                fragment,
                error_index,
                primary="}",
                alternates=[";", ")"],
                labels=["closing brace", "semicolon", "closing parenthesis"],
            )

        if err_type == MISSING_OPENING_BRACE:
            return self._insert_token_variants(
                source,
                err,
                fragment,
                error_index,
                primary="{",
                alternates=["(", ";"],
                labels=["opening brace", "opening parenthesis", "semicolon"],
            )

        if err_type == EXTRA_TOKEN or classification == DELETION_ERROR:
            return self._deletion_candidates(source, err, fragment, error_index)

        if err_type == MISSING_OPERAND:
            return self._missing_operand_candidates(source, err, fragment, error_index)

        if err_type == MISSING_OPERATOR:
            return self._missing_operator_candidates(source, err, fragment, error_index)

        if err_type in {INVALID_ASSIGNMENT, MALFORMED_DECLARATION} or classification == STRUCTURAL_ERROR:
            return self._structural_candidates(source, err, fragment, error_index)

        if classification == REPLACEMENT_ERROR or err_type == UNEXPECTED_TOKEN:
            return self._replacement_candidates(source, err, fragment, error_index)

        if classification == DELIMITER_ERROR and err.missing_token:
            return self._insert_token_variants(
                source,
                err,
                fragment,
                error_index,
                primary=err.missing_token,
                alternates=[t for t in ALT_CLOSE_DELIMS if t != err.missing_token][:2],
                labels=["expected delimiter", "alternate delimiter", "alternate delimiter"],
            )

        if classification == INSERTION_ERROR and err.missing_token:
            return self._insert_token_variants(
                source,
                err,
                fragment,
                error_index,
                primary=err.missing_token,
                alternates=[t for t in ALT_STATEMENT_ENDINGS if t != err.missing_token][:2],
                labels=["expected token", "alternate token", "alternate token"],
            )

        # Fallback: insert expected token or delete found token
        return self._fallback_candidates(source, err, fragment, error_index)

    # ----------------------------------------------------------- strategies

    def _missing_semicolon_candidates(
        self,
        source: str,
        err: ClassifiedError,
        fragment: str,
        error_index: int,
    ) -> list[CorrectionCandidate]:
        """
        Example: int x = 10
          1) int x = 10;
          2) int x = 10)
          3) int x = 10}
        Always append to the unfinished statement fragment (EOL insert).
        """
        base = fragment.rstrip()
        # Insert column = end of the statement line in source
        line_text = self._line_text(source, err.line)
        insert_col = len(line_text) + 1 if line_text else len(base) + 1

        candidates: list[CorrectionCandidate] = []
        for token, hint, label in [
            (";", 100, "statement terminator"),
            (")", 40, "closing parenthesis"),
            ("}", 30, "closing brace"),
        ]:
            corrected = base + token
            candidates.append(
                CorrectionCandidate(
                    correction=corrected,
                    operation=EditOperation(
                        kind=INSERT, token=token, line=err.line, column=insert_col
                    ),
                    description=f"Insert '{token}' ({label})",
                    error_index=error_index,
                    priority_hint=hint,
                )
            )
        return candidates

    def _missing_close_paren_candidates(
        self,
        source: str,
        err: ClassifiedError,
        fragment: str,
        error_index: int,
    ) -> list[CorrectionCandidate]:
        """
        Example: if (x > 5 {
          1) if (x > 5) {
          2) if (x > 5) ;
          3) if (x > 5) {
        Prefer inserting ')' just before '{'.
        """
        insert_col = self._insertion_column(source, err)
        # If fragment contains '{', insert ')' immediately before it
        brace_idx = fragment.find("{")
        local_col = None
        if brace_idx >= 0:
            # Map fragment-relative index back to approximate source column
            line = self._line_text(source, err.line)
            prefix = line[: max(0, err.column - 1)]
            # Prefer position of '{' on the error line
            if "{" in line:
                local_col = line.index("{") + 1
        col = local_col or insert_col

        variants = [
            (")", 100, "close the condition before '{'"),
            (");", 45, "close condition and end statement"),
            (";", 25, "semicolon instead of parenthesis"),
        ]
        # Also offer ") {" style full fragment rewrite when brace present
        candidates: list[CorrectionCandidate] = []
        for token, hint, label in variants:
            if token == ")" and "{" in fragment:
                # Preferred shape: ...expr) {
                before, _, after = fragment.partition("{")
                corrected = before.rstrip() + ") {" + after
            else:
                corrected = self._apply_insert_on_fragment(
                    fragment, source, err.line, col, token
                )
            candidates.append(
                CorrectionCandidate(
                    correction=corrected,
                    operation=EditOperation(kind=INSERT, token=token, line=err.line, column=col),
                    description=f"Insert '{token}' — {label}",
                    error_index=error_index,
                    priority_hint=hint,
                )
            )
        return candidates

    def _insert_token_variants(
        self,
        source: str,
        err: ClassifiedError,
        fragment: str,
        error_index: int,
        *,
        primary: str,
        alternates: list[str],
        labels: list[str],
    ) -> list[CorrectionCandidate]:
        insert_col = self._insertion_column(source, err)
        tokens = [primary] + [t for t in alternates if t != primary]
        candidates: list[CorrectionCandidate] = []
        for i, token in enumerate(tokens[:3]):
            label = labels[i] if i < len(labels) else "alternate token"
            hint = 100 - i * 30
            corrected = self._apply_insert_on_fragment(fragment, source, err.line, insert_col, token)
            candidates.append(
                CorrectionCandidate(
                    correction=corrected,
                    operation=EditOperation(
                        kind=INSERT, token=token, line=err.line, column=insert_col
                    ),
                    description=f"Insert '{token}' ({label})",
                    error_index=error_index,
                    priority_hint=hint,
                )
            )
        return candidates

    def _deletion_candidates(
        self,
        source: str,
        err: ClassifiedError,
        fragment: str,
        error_index: int,
    ) -> list[CorrectionCandidate]:
        found = err.extra_token or err.found or ""
        candidates: list[CorrectionCandidate] = []
        if found:
            deleted = self._apply_delete_on_fragment(fragment, found)
            candidates.append(
                CorrectionCandidate(
                    correction=deleted,
                    operation=EditOperation(
                        kind=DELETE, token=found, line=err.line, column=err.column
                    ),
                    description=f"Delete extra '{found}'",
                    error_index=error_index,
                    priority_hint=100,
                )
            )
        # Alternates: replace extra with ';' or nothing already covered
        if found and found != ";":
            replaced = fragment.replace(found, ";", 1)
            candidates.append(
                CorrectionCandidate(
                    correction=replaced,
                    operation=EditOperation(
                        kind=REPLACE,
                        token=found,
                        replacement=";",
                        line=err.line,
                        column=err.column,
                    ),
                    description=f"Replace '{found}' with ';'",
                    error_index=error_index,
                    priority_hint=50,
                )
            )
        if found and found != "":
            replaced = fragment.replace(found, "", 1).replace("  ", " ").strip()
            # already have delete; add replace-with-identifier noop avoid
            if replaced != fragment and all(c.correction != replaced for c in candidates):
                candidates.append(
                    CorrectionCandidate(
                        correction=replaced or fragment,
                        operation=EditOperation(
                            kind=DELETE, token=found, line=err.line, column=err.column
                        ),
                        description=f"Remove '{found}' and tidy whitespace",
                        error_index=error_index,
                        priority_hint=70,
                    )
                )
        if not candidates:
            candidates.append(
                CorrectionCandidate(
                    correction=fragment,
                    operation=EditOperation(kind=DELETE, token="", line=err.line, column=err.column),
                    description="No-op (unable to locate extra token)",
                    error_index=error_index,
                    priority_hint=10,
                )
            )
        return candidates[:3]

    def _missing_operand_candidates(
        self,
        source: str,
        err: ClassifiedError,
        fragment: str,
        error_index: int,
    ) -> list[CorrectionCandidate]:
        insert_col = self._insertion_column(source, err)
        candidates: list[CorrectionCandidate] = []
        for i, token in enumerate(ALT_OPERANDS[:3]):
            corrected = self._apply_insert_on_fragment(fragment, source, err.line, insert_col, token)
            # Prefer inserting after '=' with spacing
            if "=" in fragment and fragment.rstrip().endswith("="):
                corrected = fragment.rstrip() + f" {token};"
                if not fragment.rstrip().endswith(";") and not corrected.endswith(";;"):
                    pass
            candidates.append(
                CorrectionCandidate(
                    correction=corrected,
                    operation=EditOperation(
                        kind=INSERT, token=token, line=err.line, column=insert_col
                    ),
                    description=f"Insert operand '{token}'",
                    error_index=error_index,
                    priority_hint=90 - i * 20,
                )
            )
        return candidates

    def _missing_operator_candidates(
        self,
        source: str,
        err: ClassifiedError,
        fragment: str,
        error_index: int,
    ) -> list[CorrectionCandidate]:
        insert_col = self._insertion_column(source, err)
        ops = list(err.expected) if err.expected else ALT_OPERATORS
        # Prefer common arithmetic/relational ops first
        ordered = []
        for preferred in ["+", "*", "-", "/", "<", ">", "=="]:
            if preferred in ops or preferred in ALT_OPERATORS:
                ordered.append(preferred)
        for op in ops:
            if op not in ordered:
                ordered.append(op)
        candidates: list[CorrectionCandidate] = []
        for i, token in enumerate(ordered[:3]):
            corrected = self._apply_insert_on_fragment(
                fragment, source, err.line, insert_col, f" {token} "
            )
            # Clean double spaces
            corrected = " ".join(corrected.split())
            candidates.append(
                CorrectionCandidate(
                    correction=corrected,
                    operation=EditOperation(
                        kind=INSERT, token=token, line=err.line, column=insert_col
                    ),
                    description=f"Insert operator '{token}'",
                    error_index=error_index,
                    priority_hint=95 - i * 15,
                )
            )
        return candidates

    def _structural_candidates(
        self,
        source: str,
        err: ClassifiedError,
        fragment: str,
        error_index: int,
    ) -> list[CorrectionCandidate]:
        candidates: list[CorrectionCandidate] = []
        # Try insert expected tokens
        for i, token in enumerate((err.expected or [";", "=", "identifier"])[:2]):
            if token == "identifier":
                token = "x"
            insert_col = self._insertion_column(source, err)
            corrected = self._apply_insert_on_fragment(fragment, source, err.line, insert_col, token)
            candidates.append(
                CorrectionCandidate(
                    correction=corrected,
                    operation=EditOperation(
                        kind=INSERT, token=str(token), line=err.line, column=insert_col
                    ),
                    description=f"Insert '{token}' to repair structure",
                    error_index=error_index,
                    priority_hint=80 - i * 20,
                )
            )
        # Delete found token as alternate
        if err.found:
            deleted = self._apply_delete_on_fragment(fragment, err.found)
            candidates.append(
                CorrectionCandidate(
                    correction=deleted,
                    operation=EditOperation(
                        kind=DELETE, token=err.found, line=err.line, column=err.column
                    ),
                    description=f"Delete '{err.found}'",
                    error_index=error_index,
                    priority_hint=40,
                )
            )
        return candidates[:3]

    def _replacement_candidates(
        self,
        source: str,
        err: ClassifiedError,
        fragment: str,
        error_index: int,
    ) -> list[CorrectionCandidate]:
        found = err.found or ""
        expected = [str(x) for x in (err.expected or [])]
        candidates: list[CorrectionCandidate] = []
        replacements = expected[:2] if expected else [";", ")"]
        for i, rep in enumerate(replacements):
            if not found:
                corrected = self._apply_insert_on_fragment(
                    fragment, source, err.line, self._insertion_column(source, err), rep
                )
                op = EditOperation(kind=INSERT, token=rep, line=err.line, column=err.column)
                desc = f"Insert '{rep}'"
            else:
                corrected = fragment.replace(found, rep, 1) if found in fragment else fragment
                op = EditOperation(
                    kind=REPLACE,
                    token=found,
                    replacement=rep,
                    line=err.line,
                    column=err.column,
                )
                desc = f"Replace '{found}' with '{rep}'"
            candidates.append(
                CorrectionCandidate(
                    correction=corrected,
                    operation=op,
                    description=desc,
                    error_index=error_index,
                    priority_hint=90 - i * 25,
                )
            )
        if found:
            deleted = self._apply_delete_on_fragment(fragment, found)
            candidates.append(
                CorrectionCandidate(
                    correction=deleted,
                    operation=EditOperation(
                        kind=DELETE, token=found, line=err.line, column=err.column
                    ),
                    description=f"Delete '{found}'",
                    error_index=error_index,
                    priority_hint=35,
                )
            )
        return candidates[:3]

    def _fallback_candidates(
        self,
        source: str,
        err: ClassifiedError,
        fragment: str,
        error_index: int,
    ) -> list[CorrectionCandidate]:
        candidates: list[CorrectionCandidate] = []
        if err.missing_token:
            col = self._insertion_column(source, err)
            corrected = self._apply_insert_on_fragment(
                fragment, source, err.line, col, err.missing_token
            )
            candidates.append(
                CorrectionCandidate(
                    correction=corrected,
                    operation=EditOperation(
                        kind=INSERT, token=err.missing_token, line=err.line, column=col
                    ),
                    description=f"Insert '{err.missing_token}'",
                    error_index=error_index,
                    priority_hint=80,
                )
            )
        if err.found:
            candidates.append(
                CorrectionCandidate(
                    correction=self._apply_delete_on_fragment(fragment, err.found),
                    operation=EditOperation(
                        kind=DELETE, token=err.found, line=err.line, column=err.column
                    ),
                    description=f"Delete '{err.found}'",
                    error_index=error_index,
                    priority_hint=40,
                )
            )
        if not candidates:
            candidates.append(
                CorrectionCandidate(
                    correction=fragment,
                    operation=EditOperation(
                        kind=INSERT, token="", line=err.line, column=err.column
                    ),
                    description="No automatic candidate available",
                    error_index=error_index,
                    priority_hint=0,
                )
            )
        return candidates[:3]

    # --------------------------------------------------------------- edits

    def _insertion_column(self, source: str, err: ClassifiedError) -> int:
        """Column at which to insert; usually the unexpected token column."""
        return max(1, err.column)

    def _line_text(self, source: str, line: int) -> str:
        lines = source.splitlines() or [""]
        if 1 <= line <= len(lines):
            return lines[line - 1]
        return ""

    def _apply_insert_on_fragment(
        self,
        fragment: str,
        source: str,
        line: int,
        column: int,
        token: str,
    ) -> str:
        """
        Insert token into the error line fragment.
        Column is 1-based in the full source line; map into stripped fragment carefully.
        """
        line_text = self._line_text(source, line)
        if not line_text:
            # Operate on fragment alone — append/insert by best effort
            if column <= 1:
                return token + fragment
            if column > len(fragment):
                return fragment + token
            idx = column - 1
            return fragment[:idx] + token + fragment[idx:]

        # Work on full line then return stripped equivalent for display
        idx = max(0, min(len(line_text), column - 1))
        # If inserting a single delimiter before an unexpected token, don't add spaces
        # unless token itself includes spaces.
        new_line = line_text[:idx] + token + line_text[idx:]
        # Prefer returning the edited line stripped for candidate display
        return new_line.strip() if fragment == line_text.strip() else new_line.strip()

    def _apply_delete_on_fragment(self, fragment: str, token: str) -> str:
        if not token:
            return fragment
        if token in fragment:
            return fragment.replace(token, "", 1).replace("  ", " ").strip()
        return fragment


def generate_candidates(
    source: str,
    classification: Optional[ClassificationResult] = None,
) -> CandidateGenerationResult:
    """Public entry: classify (if needed) then generate candidates."""
    class_result = classification if classification is not None else classify_errors(source)
    return CandidateGenerator().generate(source, class_result.errors)


def generate_candidates_for_errors(
    source: str,
    errors: list[Union[ClassifiedError, dict[str, Any]]],
) -> CandidateGenerationResult:
    """Generate candidates from an explicit error list."""
    normalized: list[ClassifiedError] = []
    for err in errors:
        if isinstance(err, ClassifiedError):
            normalized.append(err)
        else:
            normalized.append(ClassifiedError(**{k: v for k, v in err.items() if k in ClassifiedError.__dataclass_fields__}))
    return CandidateGenerator().generate(source, normalized)
