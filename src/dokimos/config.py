"""Application configuration via environment variables."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Global application settings.

    All values can be overridden with environment variables prefixed ``DOKIMOS_``.
    For example, ``DOKIMOS_LOG_LEVEL=DEBUG``.
    """

    model_config = {"env_prefix": "DOKIMOS_"}

    # Logging
    log_level: str = "INFO"

    # Chunking
    chunk_strategy: Literal["paragraph", "sentence", "fixed"] = "paragraph"
    chunk_size: int = 500
    """Approximate number of words per chunk (used by 'fixed' strategy)."""

    chunk_overlap: int = 50
    """Number of overlapping words between consecutive chunks (used by 'fixed' strategy)."""

    # Shingling / plagiarism
    shingle_size: int = 5
    """Number of words per shingle for plagiarism comparison."""

    plagiarism_jaccard_threshold: float = 0.10
    """Minimum Jaccard similarity to consider a candidate match."""

    plagiarism_fuzz_threshold: float = 60.0
    """Minimum RapidFuzz score to keep a reranked match."""

    plagiarism_backend: Literal["local", "remote", "hybrid"] = "hybrid"
    """Select the plagiarism backend implementation."""

    plagiarism_remote_query_max_chunks: int = 5
    """Maximum number of input chunks to use as remote search queries."""

    plagiarism_remote_query_max_chars: int = 180
    """Maximum number of characters to send in each remote search query."""

    plagiarism_remote_per_provider_results: int = 3
    """Maximum number of candidate sources to request from each provider per query."""

    plagiarism_remote_timeout_seconds: float = 10.0
    """Timeout for remote plagiarism provider requests."""

    plagiarism_remote_max_source_chars: int = 20000
    """Maximum number of characters retained from a fetched remote source."""

    plagiarism_remote_fetch_full_text: bool = True
    """Attempt to retrieve full-text source content when a provider exposes it."""

    plagiarism_remote_contact_email: str | None = None
    """Optional contact email included with free academic API requests."""

    plagiarism_remote_enable_openalex: bool = True
    """Enable OpenAlex as a remote plagiarism candidate provider."""

    plagiarism_remote_enable_crossref: bool = True
    """Enable Crossref as a remote plagiarism candidate provider."""

    plagiarism_remote_enable_arxiv: bool = True
    """Enable arXiv as a remote plagiarism candidate provider."""

    plagiarism_remote_enable_duckduckgo: bool = True
    """Enable DuckDuckGo HTML search as a remote plagiarism candidate provider."""

    # AI-likeness thresholds
    ai_short_sentence_threshold: int = 8
    """Sentences with ≤ this many words are considered short."""

    ai_long_sentence_threshold: int = 40
    """Sentences with ≥ this many words are considered long."""

    ai_signal_trigger_threshold: float = 0.5
    """Per-signal value at or above which the signal is considered triggered."""

    ai_risk_high_threshold: float = 0.6
    """Aggregate AI-likeness score at or above which risk is 'high'."""

    ai_risk_medium_threshold: float = 0.3
    """Aggregate AI-likeness score at or above which risk is 'medium'."""

    ai_short_document_words: int = 80
    """Documents with fewer total words receive the short-document caveat."""

    # Paths
    output_dir: Path = Path("output")
    """Default directory for JSON report output."""

    corpus_path: Path = Path("corpus")
    """Directory used for the internal source corpus."""

    index_file: Path = Path("corpus/index.json")
    """Path to the JSON source index file."""

    # File formats
    supported_extensions: tuple[str, ...] = (".txt", ".md", ".docx", ".pdf")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton ``Settings`` instance."""
    return Settings()
