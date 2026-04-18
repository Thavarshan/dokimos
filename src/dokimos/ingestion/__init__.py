"""Document ingestion: reading and chunking."""

from dokimos.ingestion.chunker import get_chunks
from dokimos.ingestion.reader import read_document

__all__ = ["get_chunks", "read_document"]
