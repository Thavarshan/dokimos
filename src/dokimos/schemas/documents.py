"""Pydantic models for documents and text chunks."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field


class Document(BaseModel):
    """A document ingested for analysis."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_path: Path
    raw_text: str
    metadata: dict[str, str] = Field(default_factory=dict)
    ingested_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Chunk(BaseModel):
    """A contiguous text segment extracted from a document."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    document_id: str
    text: str
    index: int
    """Zero-based position of this chunk within the document."""

    start_offset: int
    """Character offset where this chunk begins in the raw text."""

    end_offset: int
    """Character offset where this chunk ends in the raw text."""
