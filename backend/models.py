"""Pydantic request/response models for the API layer."""

from typing import Any, Optional

from pydantic import BaseModel, Field


class CodeRequest(BaseModel):
    """Shared request body for tokenize / parse / analyze endpoints."""

    code: str = Field(..., description="Source code in the mini C-like language")


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


class TokenizeResponse(BaseModel):
    tokens: list[dict[str, Any]] = Field(default_factory=list)
    lexical_errors: list[dict[str, Any]] = Field(default_factory=list)
    success: bool = True
    message: str = "Tokenizer ready"


class ParseResponse(BaseModel):
    ast: Optional[dict[str, Any]] = None
    errors: list[dict[str, Any]] = Field(default_factory=list)
    success: bool = True
    message: str = "Parser ready"


class AnalyzeResponse(BaseModel):
    tokens: list[dict[str, Any]] = Field(default_factory=list)
    ast: Optional[dict[str, Any]] = None
    errors: list[dict[str, Any]] = Field(default_factory=list)
    corrections: list[dict[str, Any]] = Field(default_factory=list)
    corrected_code: str = ""
    original_code: str = ""
    report: Optional[dict[str, Any]] = None
    stages: list[dict[str, Any]] = Field(default_factory=list)
    pipeline: Optional[dict[str, Any]] = None
    success: bool = True
    message: str = "Analysis ready"


class ExampleProgram(BaseModel):
    id: str
    name: str
    description: str
    code: str
    expected_corrected: Optional[str] = None
    expected_error_types: list[str] = Field(default_factory=list)


class ExamplesResponse(BaseModel):
    examples: list[ExampleProgram]
