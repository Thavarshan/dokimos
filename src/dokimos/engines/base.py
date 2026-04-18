"""Abstract engine protocols for analysis subsystems.

These use :class:`typing.Protocol` (structural subtyping) so that
concrete implementations do not need to import or inherit from this module.
They only have to match the method signatures.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from dokimos.schemas.documents import Chunk
from dokimos.schemas.results import AiLikelihoodResult, PlagiarismResult


@runtime_checkable
class PlagiarismEngine(Protocol):
    """Engine that compares document chunks against a corpus for plagiarism."""

    def analyze(
        self,
        chunks: list[Chunk],
        corpus_id: str | None = None,
    ) -> PlagiarismResult: ...


@runtime_checkable
class AiLikelihoodEngine(Protocol):
    """Engine that scores document chunks for AI-writing-risk indicators."""

    def analyze(self, chunks: list[Chunk]) -> AiLikelihoodResult: ...


@runtime_checkable
class SourceIndexer(Protocol):
    """Engine that indexes a directory of source documents into the corpus.

    Returns the number of documents successfully indexed.
    """

    def index(self, directory: Path, *, recursive: bool = True) -> int: ...
