"""API endpoint tests for the full analysis pipeline (Phase 10)."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from main import app
from pipeline import DEMO_PROGRAM

client = TestClient(app)


class TestHealthAndExamples:
    def test_health(self):
        response = client.get("/api/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert "Intelligent Syntax Error Recovery" in body["service"]

    def test_examples(self):
        response = client.get("/api/examples")
        assert response.status_code == 200
        body = response.json()
        assert len(body["examples"]) >= 1
        demo = next(e for e in body["examples"] if e["id"] == "demo")
        assert "int x = 10" in demo["code"]


class TestTokenizeAndParse:
    def test_tokenize_demo_fragment(self):
        response = client.post("/api/tokenize", json={"code": "int x = 10"})
        assert response.status_code == 200
        body = response.json()
        types = [t["type"] for t in body["tokens"]]
        assert types[:4] == ["INT", "IDENTIFIER", "ASSIGN", "NUMBER"]
        assert body["success"] is True

    def test_parse_reports_structured_errors(self):
        response = client.post("/api/parse", json={"code": "int x = 10"})
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is False
        assert body["ast"]["type"] == "Program"
        assert any(e["type"] == "MissingSemicolon" for e in body["errors"])


class TestAnalyzePipeline:
    def test_analyze_response_shape(self):
        response = client.post("/api/analyze", json={"code": "int x = 10"})
        assert response.status_code == 200
        body = response.json()
        for key in [
            "tokens",
            "ast",
            "errors",
            "corrections",
            "corrected_code",
            "original_code",
            "report",
            "stages",
            "pipeline",
            "success",
            "message",
        ]:
            assert key in body

    def test_analyze_recovers_demo_program(self):
        response = client.post("/api/analyze", json={"code": DEMO_PROGRAM})
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert "int x = 10;" in body["corrected_code"]
        assert "if (x < y) {" in body["corrected_code"]
        assert body["report"]["total_errors"] >= 2
        assert len(body["stages"]) == 9
        stage_names = [s["name"] for s in body["stages"]]
        assert stage_names[0] == "Source Code"
        assert stage_names[-1] == "Result"
        assert all("status" in s and "detail" in s for s in body["stages"])
        assert body["pipeline"]["applied_count"] >= 2
        assert body["pipeline"]["recovery_success"] is True

    def test_analyze_stage_data_for_visualizer(self):
        response = client.post("/api/analyze", json={"code": "int x = 10"})
        body = response.json()
        lex_stage = body["stages"][1]
        assert lex_stage["name"] == "Lexical Analysis"
        assert "tokens" in lex_stage["data"]
        result_stage = body["stages"][-1]
        assert "report" in result_stage["data"]

    def test_analyze_valid_program(self):
        code = "int x = 10;\nint y = 20;\n"
        response = client.post("/api/analyze", json={"code": code})
        body = response.json()
        assert body["success"] is True
        assert body["errors"] == []
        assert body["corrected_code"] == code
        assert body["report"]["total_errors"] == 0
