"""Tests for Pydantic schema validation."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from dokimos.schemas.documents import Document
from dokimos.schemas.index import IndexedChunk, IndexedSource, SourceIndex
from dokimos.schemas.results import (
    AiChunkFinding,
    AiLikelihoodResult,
    AnalysisReport,
    DocumentMetadata,
    OffsetSpan,
    PlagiarismMatch,
    ReportSummary,
    SourceMetadata,
)


class TestDocument:
    def test_creates_with_defaults(self, tmp_path: Path) -> None:
        doc = Document(source_path=tmp_path / "f.txt", raw_text="hello")
        assert doc.id
        assert doc.ingested_at is not None

    def test_metadata_defaults_to_empty(self, tmp_path: Path) -> None:
        doc = Document(source_path=tmp_path / "f.txt", raw_text="hello")
        assert doc.metadata == {}


class TestPlagiarismMatch:
    def test_score_must_be_between_0_and_1(self) -> None:
        with pytest.raises(ValidationError):
            PlagiarismMatch(
                finding_id="f1",
                source=SourceMetadata(
                    source_id="s1", source_label="test",
                    source_path="/tmp/a.txt", chunk_index=0,
                ),
                similarity_score=1.5,
                matched_excerpt="x",
                source_excerpt="y",
                match_type="near",
                offsets=OffsetSpan(start=0, end=10),
            )

    def test_match_type_default(self) -> None:
        m = PlagiarismMatch(
            finding_id="f1",
            source=SourceMetadata(
                source_id="s1", source_label="test",
                source_path="/tmp/a.txt", chunk_index=0,
            ),
            similarity_score=0.8,
            matched_excerpt="x",
            source_excerpt="y",
            offsets=OffsetSpan(start=0, end=10),
        )
        assert m.match_type == "near"
        assert m.finding_id == "f1"


class TestAiChunkFinding:
    def test_defaults(self) -> None:
        f = AiChunkFinding(finding_id="f1", chunk_index=0)
        assert f.ai_likeness_score == 0.0
        assert f.signals == {}


class TestAiLikelihoodResult:
    def test_disclaimer_always_present(self) -> None:
        result = AiLikelihoodResult(document_id="abc")
        assert "not proof" in result.disclaimer.lower()

    def test_caveats_default_empty(self) -> None:
        result = AiLikelihoodResult(document_id="abc")
        assert result.caveats == []


class TestAnalysisReport:
    def test_minimal_report(self) -> None:
        report = AnalysisReport(
            document_id="abc",
            document=DocumentMetadata(
                source_path="/tmp/a.txt", filename="a.txt",
                file_format=".txt", character_count=100,
            ),
            summary=ReportSummary(),
        )
        assert report.plagiarism is None
        assert report.ai_likelihood is None
        assert report.generated_at is not None
        assert report.version
        assert report.status == "complete"

    def test_summary_defaults(self) -> None:
        report = AnalysisReport(
            document_id="abc",
            document=DocumentMetadata(
                source_path="/tmp/a.txt", filename="a.txt",
                file_format=".txt", character_count=100,
            ),
            summary=ReportSummary(),
        )
        assert report.summary.analyses_run == []
        assert report.caveats == []


class TestSourceIndex:
    def test_roundtrip(self) -> None:
        idx = SourceIndex(
            sources=[
                IndexedSource(
                    source_id="s1",
                    source_path="/tmp/a.txt",
                    label="a.txt",
                    chunks=[IndexedChunk(chunk_index=0, text="hello", shingles=["hello"])],
                )
            ]
        )
        data = idx.model_dump(mode="json")
        restored = SourceIndex.model_validate(data)
        assert len(restored.sources) == 1
        assert restored.sources[0].chunks[0].text == "hello"
