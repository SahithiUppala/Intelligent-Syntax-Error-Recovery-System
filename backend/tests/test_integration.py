"""End-to-end integration tests across compiler modules (Phase 16)."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from compiler.errors.classifier import classify_errors
from compiler.errors.detector import detect_syntax_errors
from compiler.lexer import tokenize
from compiler.parser import parse
from compiler.recovery.candidate_generator import generate_candidates
from compiler.recovery.recovery_engine import recover_source
from compiler.recovery.scorer import score_candidates
from compiler.reports.report_generator import generate_report
from pipeline import DEMO_EXPECTED_CORRECTED, DEMO_PROGRAM, run_analyze


class TestEndToEndDemoPipeline:
    def test_module_chain_for_demo(self):
        lex = tokenize(DEMO_PROGRAM)
        assert lex.errors == []
        assert any(t.type == "IF" for t in lex.tokens)

        parsed = parse(DEMO_PROGRAM)
        parse_types = {e.type for e in parsed.errors}
        assert "MissingSemicolon" in parse_types
        assert "MissingClosingParenthesis" in parse_types

        detection = detect_syntax_errors(DEMO_PROGRAM, parse_result=parsed)
        assert len(detection.errors) >= 2

        classification = classify_errors(DEMO_PROGRAM, detection=detection)
        cats = {e.classification for e in classification.errors}
        assert "INSERTION_ERROR" in cats
        assert "DELIMITER_ERROR" in cats

        generation = generate_candidates(DEMO_PROGRAM, classification=classification)
        assert generation.items
        assert all(len(item.candidates) >= 2 for item in generation.items)

        scored = score_candidates(DEMO_PROGRAM, generation=generation)
        for item in scored.items:
            assert item.best is not None
            scores = [c.score for c in item.candidates]
            assert scores == sorted(scores, reverse=True)

        recovery = recover_source(DEMO_PROGRAM)
        assert recovery.success is True
        assert recovery.applied_count >= 2
        assert "int x = 10;" in recovery.corrected_code
        assert "if (x < y) {" in recovery.corrected_code

        report = generate_report(
            DEMO_PROGRAM,
            recovery=recovery,
            classification=classification,
        )
        assert report.total_errors >= 2
        assert "ERROR #1" in report.text
        assert report.recovery_success is True

    def test_run_analyze_matches_expected_demo_output(self):
        result = run_analyze(DEMO_PROGRAM)
        # Normalize blank-line tolerant compare on essential lines
        corrected_lines = [ln.rstrip() for ln in result["corrected_code"].splitlines() if ln.strip()]
        expected_lines = [
            ln.rstrip() for ln in DEMO_EXPECTED_CORRECTED.splitlines() if ln.strip()
        ]
        assert corrected_lines == expected_lines
        assert result["success"] is True
        assert result["original_code"] == DEMO_PROGRAM
        assert result["report"]["entries"]
        assert all("how_fixed" in entry for entry in result["report"]["entries"])

    def test_candidates_are_scored_not_arbitrary(self):
        result = run_analyze("int x = 10")
        # Best correction for missing semicolon should be inserting ';'
        semis = [
            c
            for c in result["corrections"]
            if c.get("error_type") == "MissingSemicolon" or c.get("operation", {}).get("token") == ";"
        ]
        assert semis
        best = max(semis, key=lambda c: c.get("score") or 0)
        assert best["correction"].endswith(";")
        assert best["score"] >= 75
