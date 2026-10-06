"""Candidate generation, scoring, and recovery engine."""

from compiler.recovery.candidate_generator import (
    CandidateGenerationResult,
    CorrectionCandidate,
    generate_candidates,
    generate_candidates_for_errors,
)
from compiler.recovery.recovery_engine import RecoveryResult, recover_source
from compiler.recovery.scorer import ScoringResult, ScoredCandidate, score_candidates

__all__ = [
    "CandidateGenerationResult",
    "CorrectionCandidate",
    "generate_candidates",
    "generate_candidates_for_errors",
    "ScoringResult",
    "ScoredCandidate",
    "score_candidates",
    "RecoveryResult",
    "recover_source",
]
