"""Tests for candidate correction generation (Phase 6)."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from compiler.recovery.candidate_generator import (
    DELETE,
    INSERT,
    REPLACE,
    generate_candidates,
)


def ops_of(item):
    return [c.operation.kind for c in item.candidates]


def texts_of(item):
    return [c.correction for c in item.candidates]


class TestCandidateGeneration:
    def test_missing_semicolon_generates_multiple_inserts(self):
        result = generate_candidates("int x = 10")
        assert result.items
        item = result.items[0]
        assert item.error.type == "MissingSemicolon"
        assert len(item.candidates) >= 3
        assert all(c.operation.kind == INSERT for c in item.candidates)
        corrections = texts_of(item)
        assert any(c.endswith(";") for c in corrections)
        assert any(c.endswith(")") for c in corrections)
        assert any(c.endswith("}") for c in corrections)
        # Best grammar-aligned candidate should prefer semicolon
        best = max(item.candidates, key=lambda c: c.priority_hint)
        assert best.operation.token == ";"
        assert best.correction == "int x = 10;"

    def test_missing_close_paren_in_if(self):
        source = "if (x > 5 {\n    x = 1;\n}"
        result = generate_candidates(source)
        paren_items = [i for i in result.items if i.error.type == "MissingClosingParenthesis"]
        assert paren_items
        item = paren_items[0]
        assert len(item.candidates) >= 2
        assert any(")" in c.correction for c in item.candidates)
        best = max(item.candidates, key=lambda c: c.priority_hint)
        assert best.operation.token.startswith(")")
        # Primary candidate should look like a repaired condition header
        assert ")" in best.correction

    def test_each_candidate_stores_edit_operation(self):
        result = generate_candidates("int x = 10")
        for item in result.items:
            for cand in item.candidates:
                payload = cand.to_dict()
                assert "operation" in payload
                assert payload["operation"]["kind"] in {INSERT, DELETE, REPLACE}
                assert "correction" in payload
                assert "description" in payload

    def test_extra_token_offers_deletion(self):
        result = generate_candidates(";\nint x = 1;")
        extra_items = [i for i in result.items if i.error.type == "ExtraToken"]
        assert extra_items
        kinds = ops_of(extra_items[0])
        assert DELETE in kinds

    def test_missing_operator_offers_operator_inserts(self):
        result = generate_candidates("int z = x y;")
        op_items = [i for i in result.items if i.error.type == "MissingOperator"]
        assert op_items
        item = op_items[0]
        assert len(item.candidates) >= 2
        assert all(c.operation.kind == INSERT for c in item.candidates)
        tokens = {c.operation.token for c in item.candidates}
        assert tokens & {"+", "*", "-", "/", "<", ">", "=="}

    def test_missing_operand_offers_literal_inserts(self):
        result = generate_candidates("int y = ;")
        items = [i for i in result.items if i.error.type == "MissingOperand"]
        assert items
        assert any(c.operation.kind == INSERT for c in items[0].candidates)

    def test_demo_program_candidates_for_both_errors(self):
        source = """int x = 10
int y = 20;

if (x < y {
    x = x + 1;
}
"""
        result = generate_candidates(source)
        types = {i.error.type for i in result.items}
        assert "MissingSemicolon" in types
        assert "MissingClosingParenthesis" in types
        payload = result.to_dict()
        assert payload["total_candidates"] >= 4
        assert payload["total_errors"] >= 2
        # Flat corrections list for API
        assert all("correction" in c for c in payload["corrections"])

    def test_candidates_are_not_random_duplicates_only(self):
        result = generate_candidates("int x = 10")
        texts = texts_of(result.items[0])
        assert len(texts) == len(set(texts))
