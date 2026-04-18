"""Placeholder source indexer — logs only, indexes nothing.

Swap this out for a real implementation backed by SQLite or a vector store
once corpus management is ready.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class PlaceholderSourceIndexer:
    """No-op indexer that logs the request and returns zero."""

    def index(self, directory: Path, *, recursive: bool = True) -> int:
        logger.info(
            "PlaceholderSourceIndexer: would index directory %s (not implemented)",
            directory,
        )
        # TODO: Implement real source indexing (SQLite, vector store, etc.)
        return 0
