"""Shingling-based plagiarism engine with inverted-index candidate retrieval.

For each input chunk the engine first consults the inverted shingle index
(if present) to find only those source chunks that share at least one
shingle.  It then runs Jaccard similarity + RapidFuzz ``token_sort_ratio``
reranking on the narrowed candidate set.  For legacy v2 indexes that lack
the inverted index, it falls back transparently to a full brute-force scan.
"""

from __future__ import annotations

import json
import logging

from pydantic import ValidationError
from rapidfuzz import fuzz

from dokimos.config import Settings, get_settings
from dokimos.engines.shingling import make_shingles
from dokimos.exceptions import CorruptIndexError
from dokimos.schemas.documents import Chunk
from dokimos.schemas.index import SourceIndex
from dokimos.schemas.results import (
    OffsetSpan,
    PlagiarismMatch,
    PlagiarismResult,
    SourceMetadata,
    build_finding_id,
)

logger = logging.getLogger(__name__)


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 0.0
    return len(a & b) / len(a | b)


# Minimum word count for a chunk to be worth plagiarism comparison.
_MIN_CHUNK_WORDS = 8


def _merge_overlapping(matches: list[PlagiarismMatch]) -> list[PlagiarismMatch]:
    """Merge matches that overlap on the same source document.

    When two matches refer to the same source chunk and their query offsets
    overlap, keep only the higher-scoring match.
    """
    if len(matches) <= 1:
        return matches

    # Group by source chunk so overlapping query chunks that match different
    # portions of the same source document are preserved.
    by_source: dict[tuple[str, int], list[PlagiarismMatch]] = {}
    for m in matches:
        key = (m.source.source_id, m.source.chunk_index)
        by_source.setdefault(key, []).append(m)

    merged: list[PlagiarismMatch] = []
    for group in by_source.values():
        # Sort by offset start
        group.sort(key=lambda m: m.offsets.start)
        current = group[0]
        for nxt in group[1:]:
            if nxt.offsets.start < current.offsets.end:
                # Overlapping — keep the higher-scoring match
                if nxt.similarity_score > current.similarity_score:
                    current = nxt
            else:
                merged.append(current)
                current = nxt
        merged.append(current)

    # Preserve original ordering by score desc
    merged.sort(key=lambda m: m.similarity_score, reverse=True)
    return merged


class ShinglingPlagiarismEngine:
    """Plagiarism detector using shingle Jaccard + RapidFuzz reranking."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def _load_index(self) -> SourceIndex | None:
        idx_path = self._settings.index_file
        if not idx_path.exists():
            return None
        raw = idx_path.read_text(encoding="utf-8")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise CorruptIndexError(
                f"Index file is not valid JSON: {idx_path} ({exc})"
            ) from exc
        try:
            return SourceIndex.model_validate(data)
        except ValidationError as exc:
            raise CorruptIndexError(
                f"Index file has invalid schema: {idx_path} ({exc})"
            ) from exc

    def analyze(
        self,
        chunks: list[Chunk],
        corpus_id: str | None = None,
    ) -> PlagiarismResult:
        if not chunks:
            return PlagiarismResult(document_id="unknown")

        document_id = chunks[0].document_id
        source_index = self._load_index()

        if source_index is None or not source_index.sources:
            logger.info("No source index available — returning empty plagiarism result")
            return PlagiarismResult(document_id=document_id)

        shingle_n = self._settings.shingle_size
        jaccard_thresh = self._settings.plagiarism_jaccard_threshold
        fuzz_thresh = self._settings.plagiarism_fuzz_threshold

        # Decide whether we can use the inverted index for fast retrieval.
        inverted = source_index.inverted
        use_inverted = inverted is not None and bool(inverted.entries)
        if use_inverted:
            logger.debug("Using inverted shingle index for candidate retrieval")
        else:
            logger.debug("Inverted index unavailable — falling back to brute-force scan")

        matches: list[PlagiarismMatch] = []

        for chunk in chunks:
            # Skip very short chunks — too prone to false positives
            if len(chunk.text.split()) < _MIN_CHUNK_WORDS:
                continue

            chunk_shingles = set(make_shingles(chunk.text, shingle_n))

            if use_inverted:
                candidates = self._retrieve_candidates(
                    chunk_shingles, source_index, inverted,
                )
            else:
                # Legacy brute-force: every (source_idx, chunk) pair
                candidates = [
                    (src_idx, idx_chunk)
                    for src_idx, source in enumerate(source_index.sources)
                    for idx_chunk in source.chunks
                ]

            for src_idx, idx_chunk in candidates:
                source = source_index.sources[src_idx]
                src_shingles = set(idx_chunk.shingles)
                jac = _jaccard(chunk_shingles, src_shingles)

                if jac < jaccard_thresh:
                    continue

                # Rerank with RapidFuzz
                fuzz_score = fuzz.token_sort_ratio(chunk.text, idx_chunk.text)
                if fuzz_score < fuzz_thresh:
                    continue

                similarity = fuzz_score / 100.0

                if similarity >= 0.95:
                    match_type = "exact"
                elif similarity >= 0.70:
                    match_type = "near"
                else:
                    match_type = "paraphrase"

                matches.append(
                    PlagiarismMatch(
                        finding_id=build_finding_id(
                            "plag", source.source_id, idx_chunk.chunk_index, chunk.index,
                        ),
                        source=SourceMetadata(
                            source_id=source.source_id,
                            source_label=source.label,
                            source_path=source.source_path,
                            chunk_index=idx_chunk.chunk_index,
                        ),
                        similarity_score=round(similarity, 4),
                        matched_excerpt=chunk.text[:300],
                        source_excerpt=idx_chunk.text[:300],
                        match_type=match_type,
                        offsets=OffsetSpan(
                            start=chunk.start_offset,
                            end=chunk.end_offset,
                        ),
                    )
                )

        # Merge overlapping matches against the same source
        matches = _merge_overlapping(matches)

        # Overall score: max similarity across all matches (or 0)
        overall = max((m.similarity_score for m in matches), default=0.0)

        logger.info(
            "Plagiarism analysis: %d matches for document %s (overall=%.2f)",
            len(matches),
            document_id,
            overall,
        )
        return PlagiarismResult(
            document_id=document_id,
            matches=matches,
            overall_score=round(overall, 4),
            match_count=len(matches),
        )

    @staticmethod
    def _retrieve_candidates(
        chunk_shingles: set[str],
        source_index: SourceIndex,
        inverted,
    ) -> list[tuple[int, object]]:
        """Return deduplicated (source_idx, IndexedChunk) pairs sharing shingles."""
        seen: set[tuple[int, int]] = set()
        candidates: list[tuple[int, object]] = []
        for shingle in chunk_shingles:
            refs = inverted.entries.get(shingle)
            if refs is None:
                continue
            for ref in refs:
                key = (ref.source_idx, ref.chunk_idx)
                if key in seen:
                    continue
                seen.add(key)
                source = source_index.sources[ref.source_idx]
                # Find the matching chunk by index
                for idx_chunk in source.chunks:
                    if idx_chunk.chunk_index == ref.chunk_idx:
                        candidates.append((ref.source_idx, idx_chunk))
                        break
        return candidates
