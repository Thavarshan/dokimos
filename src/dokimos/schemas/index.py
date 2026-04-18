"""Pydantic models for the local source index."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class IndexedChunk(BaseModel):
    """A chunk stored in the source index, with normalized lookup material."""

    chunk_index: int
    text: str
    normalized_text: str = ""
    shingles: list[str] = Field(default_factory=list)
    shingle_hashes: list[str] = Field(default_factory=list)
    start_offset: int = 0
    end_offset: int = 0


class IndexedSource(BaseModel):
    """A single source document entry in the index."""

    source_id: str
    source_path: str
    label: str
    modified_at: datetime | None = None
    content_hash: str = ""
    chunks: list[IndexedChunk] = Field(default_factory=list)
    indexed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ChunkRef(BaseModel):
    """Compact reference to a single chunk inside the source index."""

    source_idx: int
    chunk_idx: int


class InvertedShingleIndex(BaseModel):
    """Maps each shingle string to the chunks that contain it.

    Stored alongside the forward index so the plagiarism engine can
    retrieve candidate chunks in O(|query_shingles|) instead of
    scanning every indexed chunk.
    """

    entries: dict[str, list[ChunkRef]] = Field(default_factory=dict)


class SourceIndex(BaseModel):
    """Root model for the JSON source index file."""

    version: str = "3"
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source_count: int = 0
    chunk_count: int = 0
    sources: list[IndexedSource] = Field(default_factory=list)
    inverted: InvertedShingleIndex | None = None
