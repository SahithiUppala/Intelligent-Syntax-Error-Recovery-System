"""
Recovery engine — best-correction selection and continue-parsing.

Confidence thresholds:
  score >= 75 → high (auto-apply / recommend)
  score 50–74 → probable
  score < 50  → uncertain

Applies high-confidence edits, re-parses, and continues until the program
is clean, only low-confidence issues remain, or MAX_RECOVERY_ATTEMPTS is hit.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from compiler.errors.classifier import classify_errors
from compiler.errors.detector import detect_syntax_errors
from compiler.parser import parse
from compiler.recovery.candidate_generator import generate_candidates
from compiler.recovery.scorer import ScoredCandidate, ScoredErrorCandidates, score_candidates

HIGH_THRESHOLD = 75
PROBABLE_THRESHOLD = 50
MAX_RECOVERY_ATTEMPTS = 12

CONFIDENCE_HIGH = "high"
CONFIDENCE_PROBABLE = "probable"
CONFIDENCE_UNCERTAIN = "uncertain"

ACTION_APPLIED = "applied"
ACTION_RECOMMENDED = "recommended"
ACTION_SKIPPED = "skipped"
ACTION_SYNC = "synchronized"


def confidence_for_score(score: int) -> str:
    if score >= HIGH_THRESHOLD:
        return CONFIDENCE_HIGH
    if score >= PROBABLE_THRESHOLD:
        return CONFIDENCE_PROBABLE
    return CONFIDENCE_UNCERTAIN


@dataclass
class RecoveryAction:
    error_number: int
    error_type: str
    classification: str
    line: int
    column: int
    original_fragment: str
    selected_correction: Optional[str]
    score: Optional[int]
    confidence: str
    explanation: str
    action: str
    candidates: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RecoveryResult:
    original_code: str
    corrected_code: str
    actions: list[RecoveryAction]
    applied_count: int
    remaining_errors: list[dict[str, Any]]
    attempts: int
    success: bool
    message: str
    final_ast: Optional[dict[str, Any]] = None
    selections: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "original_code": self.original_code,
            "corrected_code": self.corrected_code,
            "actions": [a.to_dict() for a in self.actions],
            "applied_count": self.applied_count,
            "remaining_errors": self.remaining_errors,
            "attempts": self.attempts,
            "success": self.success,
            "message": self.message,
            "final_ast": self.final_ast,
            "selections": self.selections,
            "corrections": self._flatten_corrections(),
        }

    def _flatten_corrections(self) -> list[dict[str, Any]]:
        """API-friendly flat list combining selection + candidates."""
        flat: list[dict[str, Any]] = []
        for action in self.actions:
            for cand in action.candidates:
                flat.append(
                    {
                        **cand,
                        "error_type": action.error_type,
                        "classification": action.classification,
                        "line": action.line,
                        "column": action.column,
                        "original_fragment": action.original_fragment,
                        "selected": cand.get("correction") == action.selected_correction,
                        "confidence": action.confidence,
                        "recovery_action": action.action,
                    }
                )
        return flat


class RecoveryEngine:
    """Select best corrections and iteratively recover while parsing continues."""

    def __init__(
        self,
        high_threshold: int = HIGH_THRESHOLD,
        probable_threshold: int = PROBABLE_THRESHOLD,
        max_attempts: int = MAX_RECOVERY_ATTEMPTS,
        apply_probable: bool = False,
    ):
        self.high_threshold = high_threshold
        self.probable_threshold = probable_threshold
        self.max_attempts = max_attempts
        self.apply_probable = apply_probable

    def recover(self, source: str) -> RecoveryResult:
        original = source if source is not None else ""
        current = original
        actions: list[RecoveryAction] = []
        selections: list[dict[str, Any]] = []
        applied = 0
        attempts = 0
        seen_signatures: set[str] = set()
        error_number = 0

        while attempts < self.max_attempts:
            attempts += 1
            detection = detect_syntax_errors(current)
            if not detection.errors:
                break

            classification = classify_errors(current, detection=detection)
            generation = generate_candidates(current, classification=classification)
            scored = score_candidates(current, generation=generation)
            if not scored.items:
                break

            # Process earliest error first (stable continue-parsing order)
            group = min(
                scored.items,
                key=lambda g: (g.error.line, g.error.column, g.error_index),
            )
            selection = self._select_best(group)
            selections.append(selection)

            error_number += 1
            best: Optional[ScoredCandidate] = group.best
            confidence = selection["confidence"]
            signature = (
                f"{group.error.type}:{group.error.line}:{group.error.column}:"
                f"{best.correction if best else ''}"
            )

            if signature in seen_signatures:
                # Prevent infinite recovery loops
                actions.append(
                    self._action_from_group(
                        error_number,
                        group,
                        best,
                        confidence,
                        ACTION_SKIPPED,
                        "Skipped duplicate recovery attempt to prevent an infinite loop.",
                    )
                )
                break

            seen_signatures.add(signature)

            if best is None:
                actions.append(
                    self._action_from_group(
                        error_number,
                        group,
                        None,
                        CONFIDENCE_UNCERTAIN,
                        ACTION_SKIPPED,
                        "No candidate corrections were available.",
                    )
                )
                break

            should_apply = confidence == CONFIDENCE_HIGH or (
                self.apply_probable and confidence == CONFIDENCE_PROBABLE
            )

            if should_apply:
                next_source = best.corrected_source or current
                if next_source == current:
                    # Force apply via fragment splice if scorer source unchanged
                    next_source = self._splice_fragment(
                        current, group.error.line, group.original_fragment, best.correction
                    )

                if next_source == current:
                    actions.append(
                        self._action_from_group(
                            error_number,
                            group,
                            best,
                            confidence,
                            ACTION_SKIPPED,
                            "Selected correction did not change the source; stopping recovery.",
                        )
                    )
                    break

                current = next_source
                applied += 1
                actions.append(
                    self._action_from_group(
                        error_number,
                        group,
                        best,
                        confidence,
                        ACTION_APPLIED,
                        (
                            f"Applied high-confidence correction (score {best.score}). "
                            f"{best.reason}"
                        ),
                    )
                )
                # Continue parsing remaining program on updated source
                continue

            # Non-auto: record recommendation / uncertainty, then sync past this error
            action_kind = (
                ACTION_RECOMMENDED
                if confidence == CONFIDENCE_PROBABLE
                else ACTION_SKIPPED
            )
            explanation = (
                f"Marked as {confidence} (score {best.score}); not auto-applied. "
                f"{best.reason}"
            )
            actions.append(
                self._action_from_group(
                    error_number,
                    group,
                    best,
                    confidence,
                    action_kind,
                    explanation,
                )
            )

            # Panic-style continuation: record remaining and stop auto-loop
            # (parser itself already continues; we avoid blindly mutating low-confidence code)
            break

        final_parse = parse(current)
        remaining = [e.to_dict() for e in final_parse.errors]
        success = len(remaining) == 0
        message = self._summary_message(applied, attempts, success, remaining)

        return RecoveryResult(
            original_code=original,
            corrected_code=current,
            actions=actions,
            applied_count=applied,
            remaining_errors=remaining,
            attempts=attempts,
            success=success,
            message=message,
            final_ast=final_parse.ast,
            selections=selections,
        )

    def _select_best(self, group: ScoredErrorCandidates) -> dict[str, Any]:
        best = group.best
        if best is None:
            return {
                "original_fragment": group.original_fragment,
                "candidates": [],
                "selected_correction": None,
                "score": None,
                "confidence": CONFIDENCE_UNCERTAIN,
                "explanation": "No candidates to select.",
            }

        confidence = confidence_for_score(best.score)
        return {
            "original_fragment": group.original_fragment,
            "candidates": [c.to_dict() for c in group.candidates],
            "selected_correction": best.correction,
            "score": best.score,
            "confidence": confidence,
            "explanation": (
                f"Selected highest-scoring candidate '{best.correction}' "
                f"with confidence '{confidence}' (score {best.score}). {best.reason}"
            ),
            "error_type": group.error.type,
            "line": group.error.line,
            "column": group.error.column,
        }

    def _action_from_group(
        self,
        error_number: int,
        group: ScoredErrorCandidates,
        best: Optional[ScoredCandidate],
        confidence: str,
        action: str,
        explanation: str,
    ) -> RecoveryAction:
        return RecoveryAction(
            error_number=error_number,
            error_type=group.error.type,
            classification=group.error.classification,
            line=group.error.line,
            column=group.error.column,
            original_fragment=group.original_fragment,
            selected_correction=best.correction if best else None,
            score=best.score if best else None,
            confidence=confidence,
            explanation=explanation,
            action=action,
            candidates=[c.to_dict() for c in group.candidates],
        )

    def _splice_fragment(
        self,
        source: str,
        line: int,
        original_fragment: str,
        correction: str,
    ) -> str:
        lines = source.splitlines()
        if not lines or line < 1 or line > len(lines):
            return source
        idx = line - 1
        current = lines[idx]
        leading = current[: len(current) - len(current.lstrip())]
        if original_fragment and original_fragment in current:
            lines[idx] = current.replace(original_fragment, correction, 1)
        else:
            lines[idx] = leading + correction
        return "\n".join(lines)

    def _summary_message(
        self,
        applied: int,
        attempts: int,
        success: bool,
        remaining: list[dict[str, Any]],
    ) -> str:
        if success:
            return (
                f"Recovery complete: applied {applied} correction(s) "
                f"in {attempts} attempt(s); program parses successfully."
            )
        return (
            f"Recovery finished after {attempts} attempt(s); applied {applied} "
            f"correction(s); {len(remaining)} error(s) remain."
        )


def recover_source(source: str, **kwargs: Any) -> RecoveryResult:
    """Public entry point for the recovery pipeline."""
    return RecoveryEngine(**kwargs).recover(source)
