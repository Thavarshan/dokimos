"""Document chunking utilities with multiple strategies."""

from __future__ import annotations

import hashlib
import logging
import re
from typing import Literal

from dokimos.schemas.documents import Chunk, Document

logger = logging.getLogger(__name__)

# Abbreviations that should NOT be treated as sentence boundaries.
_ABBREVIATIONS = frozenset(
    {"dr", "mr", "mrs", "ms", "prof", "sr", "jr", "st", "vs", "gen", "gov", "sgt", "cpl",
     "pvt", "capt", "lt", "col", "maj", "cmdr", "adm"}
)
_ABBR_TOKENS = frozenset({"u.s", "e.g", "i.e", "a.m", "p.m", "etc"})

_PARAGRAPH_RE = re.compile(r"\n\s*\n")
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


def _stable_id(document_id: str, index: int) -> str:
    """Generate a deterministic chunk ID from the document ID and chunk index."""
    return hashlib.sha256(f"{document_id}:{index}".encode()).hexdigest()[:16]


def get_chunks(
    document: Document,
    strategy: Literal["paragraph", "sentence", "fixed"] = "paragraph",
    chunk_size: int = 500,
    overlap: int = 50,
) -> list[Chunk]:
    """Split a document into chunks using the specified strategy.

    Parameters
    ----------
    document:
        The document to chunk.
    strategy:
        ``"paragraph"`` splits on blank lines, ``"sentence"`` splits on sentence
        boundaries, ``"fixed"`` uses a sliding word window.
    chunk_size:
        Approximate number of words per chunk (used by ``"fixed"`` strategy).
    overlap:
        Number of overlapping words between consecutive chunks (``"fixed"`` only).
    """
    if not document.raw_text.strip():
        logger.warning("Document %s has no text to chunk", document.id)
        return []

    if strategy == "paragraph":
        return _chunk_paragraphs(document)
    elif strategy == "sentence":
        return _chunk_sentences(document)
    else:
        return _chunk_fixed(document, chunk_size, overlap)


def _chunk_paragraphs(document: Document) -> list[Chunk]:
    """Split on blank lines (two or more consecutive newlines)."""
    raw = document.raw_text
    chunks: list[Chunk] = []

    # Use finditer to get the positions of paragraph delimiters, then derive
    # each paragraph's span from the gaps between delimiters.
    parts: list[tuple[int, int]] = []
    prev_end = 0
    for m in _PARAGRAPH_RE.finditer(raw):
        parts.append((prev_end, m.start()))
        prev_end = m.end()
    parts.append((prev_end, len(raw)))

    for span_start, span_end in parts:
        text = raw[span_start:span_end].strip()
        if not text:
            continue

        # Compute offsets of the stripped text within the raw slice
        lstripped = raw[span_start:span_end].lstrip()
        leading_ws = (span_end - span_start) - len(lstripped)
        start = span_start + leading_ws
        end = start + len(text)

        idx = len(chunks)
        chunks.append(
            Chunk(
                id=_stable_id(document.id, idx),
                document_id=document.id,
                text=text,
                index=idx,
                start_offset=start,
                end_offset=end,
            )
        )

    logger.info("Chunked document %s into %d paragraphs", document.id, len(chunks))
    return chunks


def _chunk_sentences(document: Document) -> list[Chunk]:
    """Split on sentence-ending punctuation followed by whitespace.

    Handles common abbreviations (Dr., Mr., U.S., e.g., etc.) by rejoining
    fragments that end with a known abbreviation period.
    """
    raw = document.raw_text
    chunks: list[Chunk] = []

    # Phase 1: regex split, keeping track of span offsets.
    raw_parts: list[tuple[int, int]] = []
    prev_end = 0
    for m in _SENTENCE_RE.finditer(raw):
        raw_parts.append((prev_end, m.start()))
        prev_end = m.end()
    raw_parts.append((prev_end, len(raw)))

    # Phase 2: merge fragments that were incorrectly split on abbreviations.
    merged: list[tuple[int, int]] = []
    for span_start, span_end in raw_parts:
        if merged and _ends_with_abbreviation(raw[merged[-1][0]:merged[-1][1]]):
            # Re-attach this fragment to the previous one (absorb the
            # whitespace gap between them as well).
            merged[-1] = (merged[-1][0], span_end)
        else:
            merged.append((span_start, span_end))

    for span_start, span_end in merged:
        text = raw[span_start:span_end].strip()
        if not text:
            continue

        lstripped = raw[span_start:span_end].lstrip()
        leading_ws = (span_end - span_start) - len(lstripped)
        start = span_start + leading_ws
        end = start + len(text)

        idx = len(chunks)
        chunks.append(
            Chunk(
                id=_stable_id(document.id, idx),
                document_id=document.id,
                text=text,
                index=idx,
                start_offset=start,
                end_offset=end,
            )
        )

    logger.info("Chunked document %s into %d sentences", document.id, len(chunks))
    return chunks


def _ends_with_abbreviation(text: str) -> bool:
    """Return True if *text* ends with a known abbreviation period."""
    # Fast path: must end with a period
    stripped = text.rstrip()
    if not stripped or stripped[-1] != ".":
        return False

    # Check for multi-part abbreviation tokens like "U.S." / "e.g."
    # Extract the last whitespace-delimited token
    last_token = stripped.rsplit(None, 1)[-1].lower().rstrip(".")
    if last_token in _ABBR_TOKENS:
        return True

    # Check single-word abbreviations: "Dr." "Mr." etc.
    if last_token in _ABBREVIATIONS:
        return True

    # Single uppercase letter followed by period (initial): "J."
    return len(last_token) == 1 and last_token.isalpha()


def _chunk_fixed(
    document: Document, chunk_size: int = 500, overlap: int = 50
) -> list[Chunk]:
    """Sliding-window word-based chunking with stable IDs."""
    raw = document.raw_text
    if not raw.strip():
        return []

    # Pre-compute word positions once so we never need str.find().
    word_spans: list[tuple[int, int]] = [
        (m.start(), m.end()) for m in re.finditer(r"\S+", raw)
    ]
    if not word_spans:
        return []

    chunks: list[Chunk] = []
    step = max(chunk_size - overlap, 1)

    for i in range(0, len(word_spans), step):
        window = word_spans[i : i + chunk_size]
        start_offset = window[0][0]
        end_offset = window[-1][1]
        chunk_text = raw[start_offset:end_offset]

        idx = len(chunks)
        chunks.append(
            Chunk(
                id=_stable_id(document.id, idx),
                document_id=document.id,
                text=chunk_text,
                index=idx,
                start_offset=start_offset,
                end_offset=end_offset,
            )
        )

    logger.info(
        "Chunked document %s into %d chunks (size=%d, overlap=%d)",
        document.id,
        len(chunks),
        chunk_size,
        overlap,
    )
    return chunks
