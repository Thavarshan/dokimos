"""Tests for the analysis pipeline."""

from __future__ import annotations

from pathlib import Path

from dokimos.config import Settings
from dokimos.engines.placeholder_ai import PlaceholderAiEngine
from dokimos.engines.placeholder_plagiarism import PlaceholderPlagiarismEngine
from dokimos.engines.shingling_plagiarism import ShinglingPlagiarismEngine
from dokimos.engines.stylometric_ai import StylometricAiEngine
from dokimos.pipeline import AnalysisPipeline
from dokimos.schemas.requests import AnalyzeRequest


class TestAnalysisPipeline:
    def test_full_pipeline_produces_report(self, sample_file: Path) -> None:
        pipeline = AnalysisPipeline(
            plagiarism_engine=PlaceholderPlagiarismEngine(),
            ai_engine=PlaceholderAiEngine(),
            settings=Settings(),
        )
        request = AnalyzeRequest(file_path=sample_file)
        report = pipeline.run(request)

        assert report.document_id
        assert report.plagiarism is not None
        assert report.ai_likelihood is not None
        assert report.version
        assert report.summary

    def test_skip_plagiarism(self, sample_file: Path) -> None:
        pipeline = AnalysisPipeline(
            plagiarism_engine=PlaceholderPlagiarismEngine(),
            ai_engine=PlaceholderAiEngine(),
            settings=Settings(),
        )
        request = AnalyzeRequest(file_path=sample_file, run_plagiarism=False)
        report = pipeline.run(request)

        assert report.plagiarism is None
        assert report.ai_likelihood is not None

    def test_skip_ai_check(self, sample_file: Path) -> None:
        pipeline = AnalysisPipeline(
            plagiarism_engine=PlaceholderPlagiarismEngine(),
            ai_engine=PlaceholderAiEngine(),
            settings=Settings(),
        )
        request = AnalyzeRequest(file_path=sample_file, run_ai_check=False)
        report = pipeline.run(request)

        assert report.plagiarism is not None
        assert report.ai_likelihood is None

    def test_with_real_engines(self, sample_file: Path, tmp_path: Path) -> None:
        settings = Settings(index_file=tmp_path / "idx.json")
        pipeline = AnalysisPipeline(
            plagiarism_engine=ShinglingPlagiarismEngine(settings=settings),
            ai_engine=StylometricAiEngine(settings=settings),
            settings=settings,
        )
        request = AnalyzeRequest(file_path=sample_file)
        report = pipeline.run(request)

        assert report.document_id
        assert report.plagiarism is not None
        assert report.ai_likelihood is not None
        assert len(report.ai_likelihood.indicators) == 6
        assert report.summary
