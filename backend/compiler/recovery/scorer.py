"""
Explainable correction scoring.

Score =
  Grammar Validity (0–40)
+ Local Context (0–25)
+ Token Compatibility (0–15)
+ Parse Progress (0–20)
− Edit Cost (0–10)

Deterministic and explainable. Candidates are sorted highest → lowest.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from compiler.errors.classifier import ClassifiedError
from compiler.parser import parse
from compiler.recovery.candidate_generator import (
    DELETE,
    INSERT,
    REPLACE,
    CandidateGenerationResult,
    CorrectionCandidate,
    EditOperation,
    ErrorCandidates,
    generate_candidates,
)

# Component maxima (sum of positives = 100; edit cost subtracts up to 10)
MAX_GRAMMAR = 40
MAX_CONTEXT = 25
MAX_TOKEN = 15
MAX_PROGRESS = 20
MAX_EDIT_PENALTY = 10


@dataclass
class ScoreBreakdown:
    grammar_validity: int
    local_context: int
    token_compatibility: int
    parse_progress: int
    edit_penalty: int

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


@dataclass
class ScoredCandidate:
    correction: str
    score: int
    reason: str
    operation: EditOperation
    description: str
    error_index: int
    breakdown: ScoreBreakdown
    corrected_source: str = ""
    is_best: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "correction": self.correction,
            "score": self.score,
            "reason": self.reason,
            "operation": self.operation.to_dict(),
            "description": self.description,
            "error_index": self.error_index,
            "breakdown": self.breakdown.to_dict(),
            "corrected_source": self.corrected_source,
            "is_best": self.is_best,
        }


@dataclass
class ScoredErrorCandidates:
    error: ClassifiedError
    error_index: int
    original_fragment: str
    candidates: list[ScoredCandidate] = field(default_factory=list)
    best: Optional[ScoredCandidate] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": self.error.to_dict(),
            "error_index": self.error_index,
            "original_fragment": self.original_fragment,
            "candidates": [c.to_dict() for c in self.candidates],
            "best": self.best.to_dict() if self.best else None,
        }


@dataclass
class ScoringResult:
    source: str
    items: list[ScoredErrorCandidates] = field(default_factory=list)

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


class CorrectionScorer:
    """Score and rank correction candidates with explainable breakdowns."""

    def score(
        self,
        source: str,
        generation: CandidateGenerationResult,
    ) -> ScoringResult:
        baseline = parse(source)
        baseline_error_count = len(baseline.errors)
        baseline_stmt_count = self._statement_count(baseline.ast)

        items: list[ScoredErrorCandidates] = []
        for group in generation.items:
            scored = [
                self._score_one(
                    source,
                    group.error,
                    cand,
                    baseline_error_count,
                    baseline_stmt_count,
                )
                for cand in group.candidates
            ]
            scored.sort(key=lambda c: (-c.score, c.operation.kind, c.correction))
            if scored:
                scored[0].is_best = True
            items.append(
                ScoredErrorCandidates(
                    error=group.error,
                    error_index=group.error_index,
                    original_fragment=group.original_fragment,
                    candidates=scored,
                    best=scored[0] if scored else None,
                )
            )
        return ScoringResult(source=source, items=items)

    def _score_one(
        self,
        source: str,
        error: ClassifiedError,
        candidate: CorrectionCandidate,
        baseline_error_count: int,
        baseline_stmt_count: int,
    ) -> ScoredCandidate:
        corrected_source = self._apply_to_source(source, error, candidate)
        after = parse(corrected_source)

        grammar = self._grammar_validity(after, error)
        context = self._local_context(error, candidate)
        token = self._token_compatibility(error, candidate)
        progress = self._parse_progress(
            baseline_error_count,
            baseline_stmt_count,
            after,
        )
        penalty = self._edit_penalty(candidate)

        total = grammar + context + token + progress - penalty
        total = max(0, min(100, total))

        reason = self._build_reason(
            error, candidate, grammar, context, token, progress, penalty, total, after
        )

        return ScoredCandidate(
            correction=candidate.correction,
            score=total,
            reason=reason,
            operation=candidate.operation,
            description=candidate.description,
            error_index=candidate.error_index,
            breakdown=ScoreBreakdown(
                grammar_validity=grammar,
                local_context=context,
                token_compatibility=token,
                parse_progress=progress,
                edit_penalty=penalty,
            ),
            corrected_source=corrected_source,
        )

    # ----------------------------------------------------------- components

    def _grammar_validity(self, parse_result, error: ClassifiedError) -> int:
        """0–40: how well the corrected program parses."""
        err_count = len(parse_result.errors)
        if err_count == 0:
            return MAX_GRAMMAR

        # Reward clearing the same error type
        remaining_same = sum(1 for e in parse_result.errors if e.type == error.type)
        if remaining_same == 0 and err_count <= 2:
            return 32
        if remaining_same == 0:
            return 26
        if err_count <= 2:
            return 18
        if err_count <= 4:
            return 10
        return 4

    def _local_context(self, error: ClassifiedError, candidate: CorrectionCandidate) -> int:
        """0–25: does the edit match the classified repair intent?"""
        op = candidate.operation
        classification = error.classification
        missing = error.missing_token
        score = 8  # baseline for attempting a contextual edit

        if classification == "INSERTION_ERROR" and op.kind == INSERT:
            score += 10
            if missing and op.token == missing:
                score += 7
            elif missing and missing in op.token:
                score += 4
        elif classification == "DELIMITER_ERROR" and op.kind == INSERT:
            score += 10
            if missing and op.token.startswith(missing):
                score += 7
            elif op.token in {")", "(", "}", "{"}:
                score += 4
        elif classification == "DELETION_ERROR" and op.kind == DELETE:
            score += 15
            if error.extra_token and op.token == error.extra_token:
                score += 2
        elif classification == "EXPRESSION_ERROR" and op.kind == INSERT:
            score += 12
            if error.type == "MissingOperator" and op.token in {
                "+",
                "-",
                "*",
                "/",
                "<",
                ">",
                "==",
                "!=",
                "<=",
                ">=",
            }:
                score += 5
            if error.type == "MissingOperand" and op.token.isalnum():
                score += 5
        elif classification == "REPLACEMENT_ERROR" and op.kind == REPLACE:
            score += 15
        elif classification == "STRUCTURAL_ERROR":
            score += 8
            if op.kind in {INSERT, REPLACE}:
                score += 4
        else:
            # Mismatched strategy — still some credit from priority_hint
            score += min(6, candidate.priority_hint // 20)

        # Prefer generator's grammar-aligned hint
        if candidate.priority_hint >= 90:
            score += 2

        return max(0, min(MAX_CONTEXT, score))

    def _token_compatibility(
        self,
        error: ClassifiedError,
        candidate: CorrectionCandidate,
    ) -> int:
        """0–15: inserted/replaced token matches expected set."""
        expected = {str(x) for x in (error.expected or [])}
        if error.missing_token:
            expected.add(error.missing_token)

        op = candidate.operation
        token = op.replacement if op.kind == REPLACE else op.token

        if not expected:
            # Soft credit for known delimiter/operator vocabulary
            if token in {";", ")", "(", "}", "{", "+", "-", "*", "/", "0", "1"}:
                return 10
            return 6

        if token in expected:
            return MAX_TOKEN
        if any(token.startswith(e) or e in token for e in expected):
            return 12
        if op.kind == DELETE and error.found and op.token == error.found:
            return 13
        return 3

    def _parse_progress(
        self,
        baseline_error_count: int,
        baseline_stmt_count: int,
        after,
    ) -> int:
        """0–20: fewer errors / more recoverable structure after the edit."""
        after_errors = len(after.errors)
        after_stmts = self._statement_count(after.ast)

        if after_errors == 0:
            return MAX_PROGRESS

        reduced = baseline_error_count - after_errors
        score = 6
        if reduced > 0:
            score += min(10, reduced * 5)
        elif reduced == 0:
            score += 2
        else:
            score -= min(4, abs(reduced) * 2)

        if after_stmts > baseline_stmt_count:
            score += 4
        elif after_stmts == baseline_stmt_count and after_stmts > 0:
            score += 2

        return max(0, min(MAX_PROGRESS, score))

    def _edit_penalty(self, candidate: CorrectionCandidate) -> int:
        """0–10 subtracted: prefer smaller, single-token edits."""
        op = candidate.operation
        if op.kind == INSERT:
            length = len(op.token.strip())
            if length <= 1:
                return 0
            if length <= 2:
                return 2
            return min(MAX_EDIT_PENALTY, 2 + length)
        if op.kind == DELETE:
            return 1 if len(op.token) <= 1 else 3
        if op.kind == REPLACE:
            return 2 if len(op.replacement) <= 2 else 5
        return 4

    def _build_reason(
        self,
        error: ClassifiedError,
        candidate: CorrectionCandidate,
        grammar: int,
        context: int,
        token: int,
        progress: int,
        penalty: int,
        total: int,
        after,
    ) -> str:
        parts: list[str] = []
        op = candidate.operation

        if grammar >= 32:
            parts.append(
                "The corrected fragment is largely grammar-valid and allows parsing to continue."
            )
        elif grammar >= 18:
            parts.append("The edit removes the primary local syntax fault.")
        else:
            parts.append("The edit only partially improves grammatical validity.")

        if context >= 20 and op.kind == INSERT and error.missing_token:
            parts.append(
                f"Inserting '{op.token}' matches the classified repair "
                f"({error.classification})."
            )
        elif context >= 18:
            parts.append("The chosen operation aligns with the local error category.")

        if token >= 12:
            parts.append("The token is compatible with what the parser expected.")

        if progress >= 15:
            parts.append("Parse progress improves (fewer remaining errors / more structure).")
        elif len(after.errors) == 0:
            parts.append("Re-parsing succeeds with no remaining syntax errors.")

        if penalty == 0:
            parts.append("Edit cost is minimal (single-character change).")
        elif penalty >= 5:
            parts.append("A higher edit cost slightly lowers confidence.")

        parts.append(
            f"Score {total} = grammar {grammar} + context {context} + token {token} "
            f"+ progress {progress} − edit {penalty}."
        )
        return " ".join(parts)

    # --------------------------------------------------------------- apply

    def _apply_to_source(
        self,
        source: str,
        error: ClassifiedError,
        candidate: CorrectionCandidate,
    ) -> str:
        """Apply the candidate edit to the full source for re-parse evaluation."""
        lines = source.splitlines()
        if not lines:
            return candidate.correction

        line_idx = max(0, min(len(lines) - 1, error.line - 1))
        original_line = lines[line_idx]
        op = candidate.operation

        # Prefer splicing the corrected fragment into the line when it clearly
        # derives from the stripped original fragment.
        fragment = error.fragment or original_line.strip()
        if fragment and fragment in original_line and candidate.correction:
            # Preserve indentation
            leading = original_line[: len(original_line) - len(original_line.lstrip())]
            # If correction is a full-line replacement of the fragment
            if original_line.strip() == fragment:
                lines[line_idx] = leading + candidate.correction
                return "\n".join(lines)

        # Fall back to operation-based edit at column
        col = max(1, op.column)
        if op.kind == INSERT:
            # Append when insert column is at/after end of line (typical for ';')
            if col > len(original_line):
                lines[line_idx] = original_line + op.token
            else:
                idx = min(len(original_line), col - 1)
                lines[line_idx] = original_line[:idx] + op.token + original_line[idx:]
        elif op.kind == DELETE and op.token:
            idx = min(len(original_line), col - 1)
            # Delete first occurrence of token at/after idx
            region = original_line[idx:]
            if op.token in region:
                lines[line_idx] = original_line[:idx] + region.replace(op.token, "", 1)
            elif op.token in original_line:
                lines[line_idx] = original_line.replace(op.token, "", 1)
        elif op.kind == REPLACE and op.token:
            idx = min(len(original_line), col - 1)
            region = original_line[idx:]
            if op.token in region:
                lines[line_idx] = (
                    original_line[:idx] + region.replace(op.token, op.replacement, 1)
                )
            elif op.token in original_line:
                lines[line_idx] = original_line.replace(op.token, op.replacement, 1)
        else:
            # Last resort: replace stripped line with correction text
            leading = original_line[: len(original_line) - len(original_line.lstrip())]
            lines[line_idx] = leading + candidate.correction

        return "\n".join(lines)

    def _statement_count(self, ast: Optional[dict[str, Any]]) -> int:
        if not ast:
            return 0
        body = ast.get("body") or []
        return len(body)


def score_candidates(
    source: str,
    generation: Optional[CandidateGenerationResult] = None,
) -> ScoringResult:
    """Public entry: generate (if needed) then score/rank candidates."""
    gen = generation if generation is not None else generate_candidates(source)
    return CorrectionScorer().score(source, gen)
