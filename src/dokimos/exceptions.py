"""Structured exception hierarchy for dokimos-cli."""

from __future__ import annotations


class CheckerError(Exception):
    """Base exception for all dokimos-cli errors."""


class IngestionError(CheckerError):
    """Raised when document reading or parsing fails."""


class AnalysisError(CheckerError):
    """Raised when an analysis engine encounters an unrecoverable error."""


class ConfigurationError(CheckerError):
    """Raised when application configuration is invalid or missing."""


class IndexingError(CheckerError):
    """Raised when corpus indexing fails."""


class CorruptIndexError(CheckerError):
    """Raised when the source index file is corrupt or invalid."""
