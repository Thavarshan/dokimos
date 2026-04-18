"""Pydantic models for analysis results and reports."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

from dokimos import __version__

REPORT_SCHEMA_VERSION = "1.0"

_AI_DISCLAIMER = (
    "This score reflects statistical likelihood of automated writing patterns. "
    "It is not proof of AI authorship and should not be treated as such."
)


def build_finding_id(*parts: str | int) -> str:
    """Generate a deterministic finding ID from stable parts."""
    payload = "::".join(str(part) for part in parts)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"fdg_{digest}"


class Caveat(BaseModel):
    """Structured warning or limitation included in machine-readable output."""

    code: str
    message: str
    severity: Literal["info", "warning"] = "warning"
    scope: Literal["report", "document", "plagiarism", "ai_likelihood"] = "report"


class DocumentMetadata(BaseModel):
    """Stable metadata describing the analyzed document."""

    source_path: str
    filename: str
    file_format: str
    character_count: int = Field(ge=0)


class OffsetSpan(BaseModel):
    """Character offsets into the normalized extracted document text."""

    start: int = Field(ge=0)
    end: int = Field(ge=0)
    unit: Literal["character"] = "character"
    basis: Literal["document_text"] = "document_text"
    end_exclusive: bool = True


class SourceMetadata(BaseModel):
    """Stable source metadata attached to plagiarism findings."""

    source_id: str
    source_label: str
    source_path: str
    chunk_index: int
    modified_at: datetime | None = None


class PlagiarismMatch(BaseModel):
    """A single plagiarism match between a document chunk and an indexed source."""

    finding_id: str
    source: SourceMetadata
    similarity_score: float = Field(ge=0.0, le=1.0)
    matched_excerpt: str
    source_excerpt: str
    match_type: Literal["exact", "near", "paraphrase"] = "near"
    offsets: OffsetSpan


class PlagiarismResult(BaseModel):
    """Aggregated plagiarism analysis result for a document."""

    document_id: str
    matches: list[PlagiarismMatch] = Field(default_factory=list)
    overall_score: float = Field(ge=0.0, le=1.0, default=0.0)
    match_count: int = Field(ge=0, default=0)


class AiLikelihoodIndicator(BaseModel):
    """A single metric contributing to the AI-likeness assessment."""

    signal_name: str
    value: float = Field(ge=0.0, le=1.0)
    description: str
    triggered: bool = False


class AiChunkFinding(BaseModel):
    """Per-chunk AI-likeness finding with individual signal scores."""

    finding_id: str
    chunk_index: int
    ai_likeness_score: float = Field(ge=0.0, le=1.0, default=0.0)
    signals: dict[str, float] = Field(default_factory=dict)
    signals_triggered: list[str] = Field(default_factory=list)
    explanation: str = ""


class AiLikelihoodResult(BaseModel):
    """AI-likeness / automated-writing-risk assessment for a document."""

    document_id: str
    indicators: list[AiLikelihoodIndicator] = Field(default_factory=list)
    chunk_findings: list[AiChunkFinding] = Field(default_factory=list)
    ai_likeness_score: float = Field(ge=0.0, le=1.0, default=0.0)
    automated_writing_risk: Literal["low", "medium", "high"] = "low"
    signals_triggered: list[str] = Field(default_factory=list)
    human_review_recommended: bool = False
    disclaimer: str = _AI_DISCLAIMER
    caveats: list[Caveat] = Field(default_factory=list)


class ReportSummary(BaseModel):
    """Top-level summary fields intended for UI and automation."""

    analyses_run: list[Literal["plagiarism", "ai_check"]] = Field(default_factory=list)
    plagiarism_match_count: int = Field(ge=0, default=0)
    plagiarism_overall_score: float = Field(ge=0.0, le=1.0, default=0.0)
    ai_likeness_score: float = Field(ge=0.0, le=1.0, default=0.0)
    automated_writing_risk: Literal["none", "low", "medium", "high"] = "none"
    human_review_recommended: bool = False


class AnalysisReport(BaseModel):
    """Complete analysis report combining plagiarism and AI-likeness results."""

    schema_version: str = REPORT_SCHEMA_VERSION
    document_id: str
    version: str = __version__
    status: Literal["complete", "partial", "error"] = "complete"
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    document: DocumentMetadata
    summary: ReportSummary
    plagiarism: PlagiarismResult | None = None
    ai_likelihood: AiLikelihoodResult | None = None
    caveats: list[Caveat] = Field(default_factory=list)
