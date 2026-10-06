"""
Intelligent Syntax Error Recovery System — FastAPI entry point.

Compiler logic lives under compiler/. Pipeline orchestration lives in pipeline.py.
This module only exposes HTTP endpoints.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from models import (
    AnalyzeResponse,
    CodeRequest,
    ExampleProgram,
    ExamplesResponse,
    HealthResponse,
    ParseResponse,
    TokenizeResponse,
)
from pipeline import list_examples, run_analyze, run_parse, run_tokenize

app = FastAPI(
    title="Intelligent Syntax Error Recovery System",
    description=(
        "Detect syntax errors, classify them, generate candidate corrections, "
        "score and apply the best recovery, then continue parsing."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", response_model=HealthResponse)
@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service="Intelligent Syntax Error Recovery System",
        version="1.0.0",
    )


@app.get("/api/examples", response_model=ExamplesResponse)
def examples() -> ExamplesResponse:
    """Built-in demonstration programs for the UI / demos."""
    return ExamplesResponse(
        examples=[ExampleProgram(**item) for item in list_examples()]
    )


@app.post("/api/tokenize", response_model=TokenizeResponse)
def tokenize(request: CodeRequest) -> TokenizeResponse:
    """Lexical analysis endpoint."""
    payload = run_tokenize(request.code)
    return TokenizeResponse(
        tokens=payload["tokens"],
        lexical_errors=payload["lexical_errors"],
        success=payload["success"],
        message=payload["message"],
    )


@app.post("/api/parse", response_model=ParseResponse)
def parse_endpoint(request: CodeRequest) -> ParseResponse:
    """Recursive-descent parse endpoint."""
    payload = run_parse(request.code)
    return ParseResponse(
        ast=payload["ast"],
        errors=payload["errors"],
        success=payload["success"],
        message=payload["message"],
    )


@app.post("/api/analyze", response_model=AnalyzeResponse)
def analyze(request: CodeRequest) -> AnalyzeResponse:
    """
    Full pipeline endpoint.

    Returns tokens, AST, classified errors, scored corrections, corrected code,
    structured report, and stage-level details for the pipeline visualizer.
    """
    payload = run_analyze(request.code)
    return AnalyzeResponse(
        tokens=payload["tokens"],
        ast=payload["ast"],
        errors=payload["errors"],
        corrections=payload["corrections"],
        corrected_code=payload["corrected_code"],
        original_code=payload["original_code"],
        report=payload["report"],
        stages=payload["stages"],
        pipeline=payload["pipeline"],
        success=payload["success"],
        message=payload["message"],
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
