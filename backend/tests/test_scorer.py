"""Tests for explainable correction scoring (Phase 7)."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from compiler.recovery.scorer import score_candidates


class TestCorrectionScoring:
    def test_semicolon_candidate_ranks_highest(self):
        result = score_candidates("int x = 10")
        assert result.items
        item = result.items[0]
        assert len(item.candidates) >= 3
        scores = [c.score for c in item.candidates]
        assert scores == sorted(scores, reverse=True)
        best = item.best
        assert best is not None
        assert best.is_best is True
        assert best.correction == "int x = 10;"
        assert best.score >= 75
        assert best.operation.token == ";"

    def test_score_breakdown_in_range(self):
        result = score_candidates("int x = 10")
        for cand in result.items[0].candidates:
            b = cand.breakdown
            assert 0 <= b.grammar_validity <= 40
            assert 0 <= b.local_context <= 25
            assert 0 <= b.token_compatibility <= 15
            assert 0 <= b.parse_progress <= 20
            assert 0 <= b.edit_penalty <= 10
            expected = (
                b.grammar_validity
                + b.local_context
                + b.token_compatibility
                + b.parse_progress
                - b.edit_penalty
            )
            assert cand.score == max(0, min(100, expected))

    def test_reason_is_explainable(self):
        result = score_candidates("int x = 10")
        best = result.items[0].best
        assert best is not None
        assert "Score" in best.reason
        assert "grammar" in best.reason
        assert len(best.reason) > 40

    def test_wrong_delimiter_scores_lower_than_semicolon(self):
        result = score_candidates("int x = 10")
        by_token = {c.operation.token: c for c in result.items[0].candidates}
        assert ";" in by_token
        assert by_token[";"].score > by_token.get(")", by_token[";"]).score
        if ")" in by_token:
            assert by_token[";"].score > by_token[")"].score
        if "}" in by_token:
            assert by_token[";"].score > by_token["}"].score

    def test_missing_paren_prefers_closing_paren(self):
        source = "if (x > 5 {\n    x = 1;\n}"
        result = score_candidates(source)
        paren_items = [i for i in result.items if i.error.type == "MissingClosingParenthesis"]
        assert paren_items
        best = paren_items[0].best
        assert best is not None
        assert ")" in best.operation.token or ")" in best.correction
        assert best.score >= 50

    def test_demo_program_scores_both_error_groups(self):
        source = """int x = 10
int y = 20;

if (x < y {
    x = x + 1;
}
"""
        result = score_candidates(source)
        assert len(result.items) >= 2
        payload = result.to_dict()
        assert payload["total_candidates"] >= 4
        # Each group has a best candidate
        for item in result.items:
            assert item.best is not None
            assert item.candidates[0].score >= item.candidates[-1].score

    def test_scoring_is_deterministic(self):
        source = "int x = 10"
        a = score_candidates(source).to_dict()
        b = score_candidates(source).to_dict()
        assert a["corrections"] == b["corrections"]
