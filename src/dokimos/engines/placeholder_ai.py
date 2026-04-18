"""Placeholder AI-likeness engine — returns stub indicators.

Swap this out for a real implementation (e.g. perplexity analysis,
stylometric features) once the analysis backend is ready.
"""

from __future__ import annotations

import logging

from dokimos.schemas.documents import Chunk
from dokimos.schemas.results import AiLikelihoodIndicator, AiLikelihoodResult

logger = logging.getLogger(__name__)


class PlaceholderAiEngine:
    """No-op AI-likeness engine that returns a zero-risk stub result."""

    def analyze(self, chunks: list[Chunk]) -> AiLikelihoodResult:
        if not chunks:
            logger.warning("AI-likeness engine received zero chunks")
            return AiLikelihoodResult(document_id="unknown")

        document_id = chunks[0].document_id
        logger.info(
            "PlaceholderAiEngine: analysing %d chunks for document %s",
            len(chunks),
            document_id,
        )

        # TODO: Implement real AI-likeness scoring (perplexity, burstiness,
        #       stylometric features, etc.)
        indicators = [
            AiLikelihoodIndicator(
                signal_name="perplexity_score",
                value=0.0,
                description="Placeholder — no model loaded.",
            ),
            AiLikelihoodIndicator(
                signal_name="burstiness_score",
                value=0.0,
                description="Placeholder — no model loaded.",
            ),
        ]

        return AiLikelihoodResult(
            document_id=document_id,
            indicators=indicators,
            ai_likeness_score=0.0,
        )
