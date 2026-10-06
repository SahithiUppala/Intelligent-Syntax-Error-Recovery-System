"""Tests for built-in example programs (Phase 16)."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from pipeline import EXAMPLE_PROGRAMS, list_examples, run_analyze


def example_by_id(example_id: str) -> dict:
    return next(item for item in EXAMPLE_PROGRAMS if item["id"] == example_id)


class TestExampleCatalog:
    def test_list_examples_matches_catalog(self):
        listed = list_examples()
        assert len(listed) == len(EXAMPLE_PROGRAMS)
        assert {item["id"] for item in listed} == {item["id"] for item in EXAMPLE_PROGRAMS}

    def test_each_example_has_required_fields(self):
        for item in EXAMPLE_PROGRAMS:
            assert item["id"]
            assert item["name"]
            assert item["description"]
            assert isinstance(item["code"], str) and item["code"].strip()
            assert "expected_error_types" in item

    def test_demo_expected_corrected_shape(self):
        demo = example_by_id("demo")
        assert "int x = 10;" in demo["expected_corrected"]
        assert "if (x < y) {" in demo["expected_corrected"]


class TestExampleAnalysis:
    def test_demo_recovers_to_expected(self):
        demo = example_by_id("demo")
        result = run_analyze(demo["code"])
        assert result["success"] is True
        assert "int x = 10;" in result["corrected_code"]
        assert "if (x < y) {" in result["corrected_code"]
        types = {e["type"] for e in result["errors"]}
        for expected in demo["expected_error_types"]:
            assert expected in types
        assert result["report"]["total_errors"] >= 2
        assert result["pipeline"]["applied_count"] >= 2

    def test_missing_semicolon_example(self):
        example = example_by_id("missing_semicolon")
        result = run_analyze(example["code"])
        assert result["success"] is True
        assert result["corrected_code"].strip() == example["expected_corrected"].strip()
        assert any(e["type"] == "MissingSemicolon" for e in result["errors"])

    def test_valid_examples_have_no_errors(self):
        for example_id in ("valid", "nested_valid"):
            example = example_by_id(example_id)
            result = run_analyze(example["code"])
            assert result["errors"] == []
            assert result["success"] is True
            assert result["corrected_code"] == example["code"]
            assert result["report"]["total_errors"] == 0

    def test_continue_after_errors_keeps_valid_tail(self):
        example = example_by_id("continue_after_errors")
        result = run_analyze(example["code"])
        types = {e["type"] for e in result["errors"]}
        assert "MissingSemicolon" in types
        # Parsing continues — z declaration should appear in AST body at some point
        # after recovery, or remain visible in corrected/original source.
        assert "int z = 30;" in result["original_code"]
        assert "int z = 30;" in result["corrected_code"]

    def test_missing_operator_example(self):
        example = example_by_id("missing_operator")
        result = run_analyze(example["code"])
        assert any(e["type"] == "MissingOperator" for e in result["errors"])
        assert result["corrections"]

    def test_extra_semicolon_classified_as_deletion(self):
        example = example_by_id("extra_semicolon")
        result = run_analyze(example["code"])
        assert any(e["type"] == "ExtraToken" for e in result["errors"])
        assert any(e.get("classification") == "DELETION_ERROR" for e in result["errors"])

    def test_all_examples_produce_nine_stages(self):
        for example in EXAMPLE_PROGRAMS:
            result = run_analyze(example["code"])
            assert len(result["stages"]) == 9
            assert result["stages"][0]["name"] == "Source Code"
            assert result["stages"][-1]["name"] == "Result"
            for stage in result["stages"]:
                assert "status" in stage
                assert "detail" in stage
