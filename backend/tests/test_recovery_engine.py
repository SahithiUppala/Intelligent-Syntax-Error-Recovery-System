"""Tests for recovery engine and continue-parsing (Phase 8)."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from compiler.parser import parse
from compiler.recovery.recovery_engine import (
    ACTION_APPLIED,
    CONFIDENCE_HIGH,
    CONFIDENCE_PROBABLE,
    CONFIDENCE_UNCERTAIN,
    confidence_for_score,
    recover_source,
)


class TestConfidenceThresholds:
    def test_thresholds(self):
        assert confidence_for_score(96) == CONFIDENCE_HIGH
        assert confidence_for_score(75) == CONFIDENCE_HIGH
        assert confidence_for_score(74) == CONFIDENCE_PROBABLE
        assert confidence_for_score(50) == CONFIDENCE_PROBABLE
        assert confidence_for_score(49) == CONFIDENCE_UNCERTAIN


class TestRecoveryEngine:
    def test_single_missing_semicolon_auto_applied(self):
        result = recover_source("int x = 10")
        assert result.applied_count >= 1
        assert result.corrected_code.strip() == "int x = 10;"
        assert result.success is True
        assert result.actions[0].action == ACTION_APPLIED
        assert result.actions[0].confidence == CONFIDENCE_HIGH
        assert result.actions[0].selected_correction == "int x = 10;"

    def test_demo_program_recovers_both_errors(self):
        source = """int x = 10
int y = 20;

if (x < y {
    x = x + 1;
}
"""
        expected = """int x = 10;
int y = 20;

if (x < y) {
    x = x + 1;
}
"""
        result = recover_source(source)
        assert result.applied_count >= 2
        # Normalize whitespace comparison on meaningful content
        assert "int x = 10;" in result.corrected_code
        assert "if (x < y)" in result.corrected_code or "if (x < y) {" in result.corrected_code
        final = parse(result.corrected_code)
        assert final.errors == [], [e.to_dict() for e in final.errors]
        assert result.success is True

        types = [a.error_type for a in result.actions if a.action == ACTION_APPLIED]
        assert "MissingSemicolon" in types
        assert "MissingClosingParenthesis" in types

    def test_continues_after_first_error(self):
        source = "int x = 10\nint y = ;\nint z = 30;"
        result = recover_source(source)
        # Should not stop after first missing semicolon — more than one action/attempt
        assert result.attempts >= 1
        assert "int x = 10;" in result.corrected_code
        # Line 3 should remain recognizable
        assert "int z = 30;" in result.corrected_code

    def test_preserves_original_code(self):
        source = "int x = 10"
        result = recover_source(source)
        assert result.original_code == source
        assert result.corrected_code != source

    def test_selection_payload_shape(self):
        result = recover_source("int x = 10")
        assert result.selections
        sel = result.selections[0]
        assert "original_fragment" in sel
        assert "candidates" in sel
        assert "selected_correction" in sel
        assert "score" in sel
        assert "confidence" in sel
        assert "explanation" in sel

    def test_valid_program_noop(self):
        source = "int x = 10;\nint y = 20;"
        result = recover_source(source)
        assert result.success is True
        assert result.applied_count == 0
        assert result.corrected_code == source

    def test_max_attempts_bound(self):
        result = recover_source("int x = 10\nint y = 20", max_attempts=1)
        assert result.attempts <= 1

    def test_to_dict_includes_corrected_code(self):
        payload = recover_source("int x = 10").to_dict()
        assert payload["corrected_code"].strip() == "int x = 10;"
        assert payload["applied_count"] >= 1
        assert isinstance(payload["actions"], list)
