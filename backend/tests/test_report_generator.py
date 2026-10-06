"""Tests for structured error report generation (Phase 9)."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from compiler.reports.report_generator import generate_report


class TestReportGenerator:
    def test_single_error_report_fields(self):
        report = generate_report("int x = 10")
        assert report.total_errors >= 1
        entry = report.entries[0]
        payload = entry.to_dict()
        assert payload["error_number"] == 1
        assert payload["line"] >= 1
        assert payload["column"] >= 1
        assert payload["type"] == "MissingSemicolon"
        assert payload["classification"] == "INSERTION_ERROR"
        assert "int x = 10" in payload["original_fragment"]
        assert payload["best_correction"] == "int x = 10;"
        assert payload["best_score"] is not None
        assert payload["confidence"] == "high"
        assert payload["confidence_percent"] == payload["best_score"]
        assert payload["recovery_action"] == "applied"
        assert payload["explanation"]
        assert len(payload["candidates"]) >= 2
        assert any(c["is_best"] for c in payload["candidates"])
        assert "how_fixed" in payload
        assert payload["how_fixed"]["classified_as"] == "INSERTION_ERROR"

    def test_text_report_contains_sections(self):
        report = generate_report("int x = 10")
        text = report.text
        assert "ERROR #1" in text
        assert "Line:" in text
        assert "Classification:" in text
        assert "INSERTION_ERROR" in text
        assert "Original:" in text
        assert "Suggested:" in text
        assert "Confidence:" in text
        assert "int x = 10;" in text
        assert "ORIGINAL CODE:" in text
        assert "CORRECTED CODE:" in text

    def test_demo_program_multi_error_report(self):
        source = """int x = 10
int y = 20;

if (x < y {
    x = x + 1;
}
"""
        report = generate_report(source)
        assert report.total_errors >= 2
        types = {e.type for e in report.entries}
        assert "MissingSemicolon" in types
        assert "MissingClosingParenthesis" in types
        assert report.recovery_success is True
        assert "int x = 10;" in report.corrected_code
        assert "if (x < y) {" in report.corrected_code
        payload = report.to_dict()
        assert payload["total_errors"] == report.total_errors
        assert len(payload["entries"]) == report.total_errors

    def test_clean_program_report(self):
        report = generate_report("int x = 10;")
        assert report.total_errors == 0
        assert report.recovery_success is True
        assert "No syntax errors detected" in report.text

    def test_how_fixed_educational_block(self):
        report = generate_report("int x = 10")
        how = report.entries[0].how_fixed
        assert "detected" in how
        assert "classified_as" in how
        assert how["candidates_generated"] >= 2
        assert how["selected"] == "int x = 10;"
        assert "reason" in how
