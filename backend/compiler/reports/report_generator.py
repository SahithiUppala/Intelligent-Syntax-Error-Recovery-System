"""
Structured error report generation.

Produces machine-readable report entries and a human-readable text report
suitable for demos / UI panels. Does not mutate compiler recovery results.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from compiler.errors.classifier import ClassificationResult, classify_errors
from compiler.recovery.recovery_engine import RecoveryAction, RecoveryResult, recover_source


@dataclass
class CandidateReport:
    rank: int
    correction: str
    score: int
    reason: str
    operation: dict[str, Any] = field(default_factory=dict)
    is_best: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ErrorReportEntry:
    error_number: int
    line: int
    column: int
    type: str
    classification: str
    original_fragment: str
    explanation: str
    found: Optional[str]
    expected: list[str]
    candidates: list[CandidateReport]
    best_correction: Optional[str]
    best_score: Optional[int]
    confidence: str
    confidence_percent: Optional[int]
    recovery_action: str
    how_fixed: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "error_number": self.error_number,
            "line": self.line,
            "column": self.column,
            "type": self.type,
            "classification": self.classification,
            "original_fragment": self.original_fragment,
            "explanation": self.explanation,
            "found": self.found,
            "expected": self.expected,
            "candidates": [c.to_dict() for c in self.candidates],
            "best_correction": self.best_correction,
            "best_score": self.best_score,
            "confidence": self.confidence,
            "confidence_percent": self.confidence_percent,
            "recovery_action": self.recovery_action,
            "how_fixed": self.how_fixed,
        }

    def to_text(self) -> str:
        lines = [
            f"ERROR #{self.error_number}",
            "",
            f"Line: {self.line}",
            f"Column: {self.column}",
            "",
            "Type:",
            self._human_type(self.type),
            "",
            "Classification:",
            self.classification,
            "",
            "Original:",
            self.original_fragment or "(empty)",
            "",
        ]
        if self.best_correction is not None:
            lines.extend(
                [
                    "Suggested:",
                    self.best_correction,
                    "",
                ]
            )
        if self.confidence_percent is not None:
            lines.extend(
                [
                    "Confidence:",
                    f"{self.confidence_percent}%",
                    "",
                ]
            )
        lines.extend(
            [
                "Explanation:",
                self.explanation or "(none)",
                "",
                "Recovery action:",
                self.recovery_action,
            ]
        )
        if self.candidates:
            lines.extend(["", "Candidates:"])
            for cand in self.candidates:
                marker = " ← BEST" if cand.is_best else ""
                lines.append(f"  {cand.rank}. {cand.correction}  (score {cand.score}){marker}")
        return "\n".join(lines)

    @staticmethod
    def _human_type(err_type: str) -> str:
        # MissingSemicolon → Missing Semicolon
        spaced = []
        for ch in err_type:
            if ch.isupper() and spaced:
                spaced.append(" ")
            spaced.append(ch)
        return "".join(spaced)


@dataclass
class AnalysisReport:
    total_errors: int
    entries: list[ErrorReportEntry]
    original_code: str
    corrected_code: str
    recovery_success: bool
    recovery_message: str
    applied_count: int
    text: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_errors": self.total_errors,
            "entries": [e.to_dict() for e in self.entries],
            "original_code": self.original_code,
            "corrected_code": self.corrected_code,
            "recovery_success": self.recovery_success,
            "recovery_message": self.recovery_message,
            "applied_count": self.applied_count,
            "text": self.text,
        }


class ReportGenerator:
    """Build structured + textual reports from recovery / classification data."""

    def generate(
        self,
        recovery: RecoveryResult,
        classification: Optional[ClassificationResult] = None,
    ) -> AnalysisReport:
        class_by_key: dict[tuple[Any, ...], dict[str, Any]] = {}
        if classification is not None:
            for err in classification.errors:
                key = (err.type, err.line, err.column)
                class_by_key[key] = err.to_dict()

        entries: list[ErrorReportEntry] = []
        for action in recovery.actions:
            classified = class_by_key.get(
                (action.error_type, action.line, action.column),
                {},
            )
            candidates = self._build_candidates(action)
            best_score = action.score
            confidence_percent = best_score if best_score is not None else None
            explanation = self._pick_explanation(action, classified)

            how_fixed = {
                "detected": f"Parser/detector reported {action.error_type}.",
                "classified_as": action.classification,
                "candidates_generated": len(action.candidates),
                "selected": action.selected_correction,
                "selected_operation": self._selected_operation(action),
                "reason": (
                    "Highest grammar validity and maximum parse continuation."
                    if action.confidence == "high"
                    else action.explanation
                ),
                "recovery_action": action.action,
            }

            entries.append(
                ErrorReportEntry(
                    error_number=action.error_number,
                    line=action.line,
                    column=action.column,
                    type=action.error_type,
                    classification=action.classification,
                    original_fragment=action.original_fragment,
                    explanation=explanation,
                    found=classified.get("found"),
                    expected=list(classified.get("expected") or []),
                    candidates=candidates,
                    best_correction=action.selected_correction,
                    best_score=best_score,
                    confidence=action.confidence,
                    confidence_percent=confidence_percent,
                    recovery_action=action.action,
                    how_fixed=how_fixed,
                )
            )

        # If recovery found nothing but classification still has errors (edge case)
        if not entries and classification and classification.errors:
            for i, err in enumerate(classification.errors, start=1):
                entries.append(
                    ErrorReportEntry(
                        error_number=i,
                        line=err.line,
                        column=err.column,
                        type=err.type,
                        classification=err.classification,
                        original_fragment=err.fragment,
                        explanation=err.explanation or err.message,
                        found=err.found,
                        expected=list(err.expected or []),
                        candidates=[],
                        best_correction=None,
                        best_score=None,
                        confidence="uncertain",
                        confidence_percent=None,
                        recovery_action="reported",
                        how_fixed={
                            "detected": err.message,
                            "classified_as": err.classification,
                            "candidates_generated": 0,
                            "selected": None,
                            "reason": "No recovery action was applied.",
                            "recovery_action": "reported",
                        },
                    )
                )

        text = self._render_text(
            entries,
            recovery.original_code,
            recovery.corrected_code,
            recovery.message,
        )

        return AnalysisReport(
            total_errors=len(entries),
            entries=entries,
            original_code=recovery.original_code,
            corrected_code=recovery.corrected_code,
            recovery_success=recovery.success,
            recovery_message=recovery.message,
            applied_count=recovery.applied_count,
            text=text,
        )

    def _build_candidates(self, action: RecoveryAction) -> list[CandidateReport]:
        ranked: list[CandidateReport] = []
        sorted_cands = sorted(
            action.candidates,
            key=lambda c: (-int(c.get("score") or 0), c.get("correction") or ""),
        )
        for idx, cand in enumerate(sorted_cands, start=1):
            correction = cand.get("correction") or ""
            is_best = correction == action.selected_correction or bool(cand.get("is_best"))
            ranked.append(
                CandidateReport(
                    rank=idx,
                    correction=correction,
                    score=int(cand.get("score") or 0),
                    reason=cand.get("reason") or cand.get("description") or "",
                    operation=dict(cand.get("operation") or {}),
                    is_best=is_best,
                )
            )
        return ranked

    def _pick_explanation(
        self,
        action: RecoveryAction,
        classified: dict[str, Any],
    ) -> str:
        if classified.get("explanation"):
            base = classified["explanation"]
        else:
            base = action.explanation
        # Prefer a concise educational explanation for common cases
        if action.error_type == "MissingSemicolon":
            return (
                "A variable declaration must terminate with a semicolon. "
                "Inserting ';' allows the following declaration to be parsed independently."
            )
        if action.error_type == "MissingClosingParenthesis":
            return (
                "The if/while condition must be closed with ')'. "
                "Inserting ')' before the block allows the statement to parse correctly."
            )
        return base

    def _selected_operation(self, action: RecoveryAction) -> Optional[str]:
        for cand in action.candidates:
            if cand.get("correction") == action.selected_correction:
                op = cand.get("operation") or {}
                kind = op.get("kind")
                token = op.get("token") or op.get("replacement") or ""
                if kind and token:
                    return f"{kind} '{token}'"
                return kind
        return None

    def _render_text(
        self,
        entries: list[ErrorReportEntry],
        original: str,
        corrected: str,
        recovery_message: str,
    ) -> str:
        parts = [
            "=== Intelligent Syntax Error Recovery Report ===",
            "",
            f"Total errors: {len(entries)}",
            f"Recovery: {recovery_message}",
            "",
        ]
        if not entries:
            parts.append("No syntax errors detected.")
        for entry in entries:
            parts.append(entry.to_text())
            parts.append("")
            parts.append("-" * 40)
            parts.append("")
        parts.extend(
            [
                "ORIGINAL CODE:",
                original,
                "",
                "CORRECTED CODE:",
                corrected,
            ]
        )
        return "\n".join(parts).rstrip() + "\n"


def generate_report(
    source: str,
    recovery: Optional[RecoveryResult] = None,
    classification: Optional[ClassificationResult] = None,
) -> AnalysisReport:
    """Public entry: recover/classify as needed, then build the report."""
    recovery_result = recovery if recovery is not None else recover_source(source)
    classification_result = (
        classification
        if classification is not None
        else classify_errors(source)
    )
    return ReportGenerator().generate(recovery_result, classification_result)
