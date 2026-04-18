"""JSON-based local source indexer.

Reads documents from a directory, chunks them, computes shingle sets,
and persists the index to a JSON file.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import logging
import os
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from dokimos.config import Settings, get_settings
from dokimos.engines.shingling import make_shingles
from dokimos.exceptions import CorruptIndexError
from dokimos.ingestion.chunker import get_chunks
from dokimos.ingestion.reader import read_document
from dokimos.schemas.index import (
    ChunkRef,
    IndexedChunk,
    IndexedSource,
    InvertedShingleIndex,
    SourceIndex,
)

logger = logging.getLogger(__name__)


@dataclass
class IndexStats:
    """Statistics from the last :meth:`LocalSourceIndexer.index` call."""

    indexed: int = 0
    skipped: int = 0
    up_to_date: int = 0
    total_files: int = 0
    recursive: bool = True
    index_path: Path = field(default_factory=lambda: Path())


def _normalize(text: str) -> str:
    """Lowercase and collapse whitespace."""
    return " ".join(text.lower().split())


def _content_hash(text: str) -> str:
    """SHA-256 hex digest of the raw text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _file_mtime(path: Path) -> datetime:
    """Return the file's last-modified time as a timezone-aware datetime."""
    return datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)


class LocalSourceIndexer:
    """Indexes a directory of source documents into a JSON file.

    Each source is chunked, and shingle sets are precomputed to allow
    fast Jaccard-based plagiarism lookups later.  When re-indexing,
    files whose mtime is newer than the stored ``modified_at`` are
    automatically refreshed.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self.last_stats: IndexStats | None = None

    def _load_index(self) -> SourceIndex:
        idx_path = self._settings.index_file
        if idx_path.exists():
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
        return SourceIndex()

    def _save_index(self, index: SourceIndex) -> None:
        idx_path = self._settings.index_file
        idx_path.parent.mkdir(parents=True, exist_ok=True)

        # (Re)build the inverted shingle index from the forward sources.
        index.inverted = self._build_inverted(index)
        index.version = "3"
        index.updated_at = datetime.now(UTC)
        index.source_count = len(index.sources)
        index.chunk_count = sum(len(s.chunks) for s in index.sources)

        payload = json.dumps(
            index.model_dump(mode="json"), indent=2, ensure_ascii=False,
        )

        # Atomic write: write to a temp file in the same directory, then
        # replace the target.  os.replace() is atomic on POSIX and
        # near-atomic on Windows.
        fd, tmp_name = tempfile.mkstemp(
            dir=str(idx_path.parent), suffix=".tmp",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(payload)
            os.replace(tmp_name, str(idx_path))
        except BaseException:
            # Clean up the temp file on any failure.
            with contextlib.suppress(OSError):
                os.unlink(tmp_name)
            raise

    @staticmethod
    def _build_inverted(index: SourceIndex) -> InvertedShingleIndex:
        """Create an inverted shingle → chunk-ref mapping."""
        entries: dict[str, list[ChunkRef]] = {}
        for src_idx, source in enumerate(index.sources):
            for chunk in source.chunks:
                ref = ChunkRef(source_idx=src_idx, chunk_idx=chunk.chunk_index)
                for shingle in chunk.shingles:
                    entries.setdefault(shingle, []).append(ref)
        return InvertedShingleIndex(entries=entries)

    def _build_indexed_source(self, file_path: Path, doc_text: str) -> IndexedSource:
        """Build an :class:`IndexedSource` from a file path and its text."""
        from dokimos.schemas.documents import Document

        doc = Document(source_path=file_path, raw_text=doc_text)
        chunks = get_chunks(
            doc,
            strategy=self._settings.chunk_strategy,
            chunk_size=self._settings.chunk_size,
            overlap=self._settings.chunk_overlap,
        )
        shingle_n = self._settings.shingle_size

        indexed_chunks = [
            IndexedChunk(
                chunk_index=c.index,
                text=c.text,
                normalized_text=_normalize(c.text),
                shingles=make_shingles(c.text, shingle_n),
                start_offset=c.start_offset,
                end_offset=c.end_offset,
            )
            for c in chunks
        ]

        return IndexedSource(
            source_id=str(uuid.uuid4()),
            source_path=str(file_path),
            label=file_path.name,
            modified_at=_file_mtime(file_path),
            content_hash=_content_hash(doc_text),
            chunks=indexed_chunks,
        )

    def index(self, directory: Path, *, recursive: bool = True) -> int:
        """Index all supported files under *directory*.

        Parameters
        ----------
        directory:
            Root directory to scan.
        recursive:
            If True (default), recurse into subdirectories via ``rglob``.
            If False, only scan the top-level directory via ``glob``.

        Returns the number of documents successfully indexed or re-indexed.
        """
        resolved = directory.resolve()
        if not resolved.is_dir():
            logger.error("Not a directory: %s", resolved)
            return 0

        source_index = self._load_index()
        existing: dict[str, int] = {
            s.source_path: i for i, s in enumerate(source_index.sources)
        }

        exts = self._settings.supported_extensions
        glob_fn = resolved.rglob if recursive else resolved.glob
        files = [
            f for f in sorted(glob_fn("*")) if f.is_file() and f.suffix.lower() in exts
        ]

        count = 0
        skipped = 0
        up_to_date = 0
        for file_path in files:
            str_path = str(file_path)

            # Check if already indexed and still fresh
            if str_path in existing:
                idx = existing[str_path]
                stored = source_index.sources[idx]
                if stored.modified_at is not None:
                    disk_mtime = _file_mtime(file_path)
                    if disk_mtime <= stored.modified_at:
                        logger.debug("Skipping up-to-date: %s", str_path)
                        up_to_date += 1
                        continue
                    # Stale — remove old entry so we re-index below
                    logger.info("Re-indexing modified file: %s", str_path)
                    source_index.sources.pop(idx)
                    # Rebuild lookup after mutation
                    existing = {
                        s.source_path: i for i, s in enumerate(source_index.sources)
                    }
                else:
                    logger.debug("Skipping already indexed (no mtime): %s", str_path)
                    up_to_date += 1
                    continue

            try:
                doc = read_document(file_path)
            except Exception:
                logger.warning("Failed to read %s, skipping", file_path)
                skipped += 1
                continue

            source_index.sources.append(self._build_indexed_source(file_path, doc.raw_text))
            count += 1

        self._save_index(source_index)
        self.last_stats = IndexStats(
            indexed=count,
            skipped=skipped,
            up_to_date=up_to_date,
            total_files=len(files),
            recursive=recursive,
            index_path=self._settings.index_file,
        )
        logger.info("Indexed %d document(s) from %s", count, resolved)
        return count
