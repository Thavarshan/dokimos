"""Analysis pipeline orchestrator.

The pipeline coordinates document ingestion, chunking, engine execution,
and report assembly.  Each stage is a separate method so individual steps
can be tested or replaced independently.
"""

from __future__ import annotations

import logging

from dokimos.config import Settings, get_settings
from dokimos.engines.base import AiLikelihoodEngine, PlagiarismEngine
from dokimos.exceptions import AnalysisError
from dokimos.ingestion.chunker import get_chunks
from dokimos.ingestion.reader import read_document
from dokimos.schemas.documents import Chunk, Document
from dokimos.schemas.requests import AnalyzeRequest
from dokimos.schemas.results import (
    AiLikelihoodResult,
    AnalysisReport,
    Caveat,
    DocumentMetadata,
    PlagiarismResult,
    ReportSummary,
)

logger = logging.getLogger(__name__)


class AnalysisPipeline:
    """Orchestrates the full analysis workflow."""

    def __init__(
        self,
        plagiarism_engine: PlagiarismEngine,
        ai_engine: AiLikelihoodEngine,
        settings: Settings | None = None,
    ) -> None:
        self._plagiarism_engine = plagiarism_engine
        self._ai_engine = ai_engine
        self._settings = settings or get_settings()

    # -- public API ----------------------------------------------------------

    def run(self, request: AnalyzeRequest) -> AnalysisReport:
        """Execute the full analysis pipeline for a single document."""
        logger.info("Pipeline: starting analysis for %s", request.file_path)

        document = self._ingest(request)
        chunks = self._chunk(document)

        plagiarism_result: PlagiarismResult | None = None
        ai_result: AiLikelihoodResult | None = None

        if request.run_plagiarism:
            plagiarism_result = self._run_plagiarism(chunks)

        if request.run_ai_check:
            ai_result = self._run_ai_check(chunks)

        report = self._assemble_report(document, plagiarism_result, ai_result)
        logger.info("Pipeline: analysis complete for document %s", document.id)
        return report

    # -- pipeline stages (each independently testable) -----------------------

    def _ingest(self, request: AnalyzeRequest) -> Document:
        """Read the file into a ``Document``."""
        return read_document(request.file_path)

    def _chunk(self, document: Document) -> list[Chunk]:
        """Split the document into chunks using the configured strategy."""
        return get_chunks(
            document,
            strategy=self._settings.chunk_strategy,
            chunk_size=self._settings.chunk_size,
            overlap=self._settings.chunk_overlap,
        )

    def _run_plagiarism(self, chunks: list[Chunk]) -> PlagiarismResult:
        """Delegate to the plagiarism engine."""
        try:
            return self._plagiarism_engine.analyze(chunks)
        except Exception as exc:
            raise AnalysisError(f"Plagiarism engine failed: {exc}") from exc

    def _run_ai_check(self, chunks: list[Chunk]) -> AiLikelihoodResult:
        """Delegate to the AI-likeness engine."""
        try:
            return self._ai_engine.analyze(chunks)
        except Exception as exc:
            raise AnalysisError(f"AI-likeness engine failed: {exc}") from exc

    def _assemble_report(
        self,
        document: Document,
        plagiarism: PlagiarismResult | None,
        ai_likelihood: AiLikelihoodResult | None,
    ) -> AnalysisReport:
        """Combine results into a single report with a stable summary contract."""
        caveats: list[Caveat] = []
        analyses_run: list[str] = []

        if plagiarism is not None:
            analyses_run.append("plagiarism")

        if ai_likelihood is not None:
            analyses_run.append("ai_check")
            caveats.extend(ai_likelihood.caveats)

        summary = ReportSummary(
            analyses_run=analyses_run,
            plagiarism_match_count=plagiarism.match_count if plagiarism is not None else 0,
            plagiarism_overall_score=(
                plagiarism.overall_score if plagiarism is not None else 0.0
            ),
            ai_likeness_score=(
                ai_likelihood.ai_likeness_score if ai_likelihood is not None else 0.0
            ),
            automated_writing_risk=(
                ai_likelihood.automated_writing_risk if ai_likelihood is not None else "none"
            ),
            human_review_recommended=(
                ai_likelihood.human_review_recommended if ai_likelihood is not None else False
            ),
        )

        return AnalysisReport(
            document_id=document.id,
            document=DocumentMetadata(
                source_path=str(document.source_path),
                filename=document.metadata.get("filename", document.source_path.name),
                file_format=document.metadata.get("format", document.source_path.suffix.lower()),
                character_count=len(document.raw_text),
            ),
            plagiarism=plagiarism,
            ai_likelihood=ai_likelihood,
            summary=summary,
            caveats=caveats,
        )
