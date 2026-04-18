"""Placeholder plagiarism engine — returns empty results.

Swap this out for a real implementation (e.g. TF-IDF, embedding similarity)
once the analysis backend is ready.
"""

from __future__ import annotations

import logging

from dokimos.schemas.documents import Chunk
from dokimos.schemas.results import PlagiarismResult

logger = logging.getLogger(__name__)


class PlaceholderPlagiarismEngine:
    """No-op plagiarism engine that always returns an empty result."""

    def analyze(
        self,
        chunks: list[Chunk],
        corpus_id: str | None = None,
    ) -> PlagiarismResult:
        if not chunks:
            logger.warning("Plagiarism engine received zero chunks")
            return PlagiarismResult(document_id="unknown")

        document_id = chunks[0].document_id
        logger.info(
            "PlaceholderPlagiarismEngine: analysing %d chunks for document %s",
            len(chunks),
            document_id,
        )

        # TODO: Implement real plagiarism detection (TF-IDF, embeddings, etc.)
        return PlagiarismResult(
            document_id=document_id,
            matches=[],
            overall_score=0.0,
        )
