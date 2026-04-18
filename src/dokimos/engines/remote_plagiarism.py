"""Remote plagiarism engine backed by free academic search providers.

This engine performs candidate discovery against free remote sources,
retrieves candidate text where possible, then verifies matches locally
using the same shingling and fuzzy reranking approach as the local engine.
"""

from __future__ import annotations

import json
import logging
import re
import tempfile
from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Protocol
from urllib.parse import parse_qs, unquote, urlencode, urlsplit
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

from rapidfuzz import fuzz

from dokimos.config import Settings, get_settings
from dokimos.engines.shingling import make_shingles
from dokimos.engines.shingling_plagiarism import _merge_overlapping
from dokimos.exceptions import IngestionError
from dokimos.ingestion.chunker import get_chunks
from dokimos.ingestion.reader import read_document
from dokimos.schemas.documents import Chunk, Document
from dokimos.schemas.results import (
    OffsetSpan,
    PlagiarismMatch,
    PlagiarismResult,
    SourceMetadata,
    build_finding_id,
)

logger = logging.getLogger(__name__)

_MIN_CHUNK_WORDS = 8
_ATOM_NAMESPACE = {"atom": "http://www.w3.org/2005/Atom"}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 0.0
    return len(a & b) / len(a | b)


def _collapse_whitespace(text: str) -> str:
    return " ".join(text.split())


def _strip_markup(text: str) -> str:
    without_tags = re.sub(r"<[^>]+>", " ", text)
    return _collapse_whitespace(unescape(without_tags))


def _truncate_text(text: str, max_chars: int) -> str:
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    return text[:max_chars]


def _quoted_query(text: str) -> str:
    escaped = text.replace('"', "")
    return f'"{escaped}"'


def _abstract_from_inverted_index(payload: dict[str, list[int]] | None) -> str:
    if not payload:
        return ""

    positions: dict[int, str] = {}
    for token, indexes in payload.items():
        for index in indexes:
            positions[index] = token

    return " ".join(token for _, token in sorted(positions.items()))


class _HtmlTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        stripped = data.strip()
        if stripped:
            self._parts.append(stripped)

    def get_text(self) -> str:
        return _collapse_whitespace(" ".join(self._parts))


class _DuckDuckGoResultsParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._inside_result_link = False
        self._current_href = ""
        self._current_parts: list[str] = []
        self._results: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return

        attr_map = {key: value or "" for key, value in attrs}
        classes = attr_map.get("class", "").split()
        if "result__a" not in classes:
            return

        self._inside_result_link = True
        self._current_href = attr_map.get("href", "")
        self._current_parts = []

    def handle_data(self, data: str) -> None:
        if not self._inside_result_link:
            return

        stripped = data.strip()
        if stripped:
            self._current_parts.append(stripped)

    def handle_endtag(self, tag: str) -> None:
        if tag != "a" or not self._inside_result_link:
            return

        title = _collapse_whitespace(" ".join(self._current_parts))
        if title and self._current_href:
            self._results.append((title, self._current_href))

        self._inside_result_link = False
        self._current_href = ""
        self._current_parts = []

    def get_results(self) -> list[tuple[str, str]]:
        return self._results


@dataclass(frozen=True)
class RemoteCandidate:
    provider: str
    source_id: str
    source_label: str
    source_path: str
    metadata_text: str
    full_text_url: str | None = None


@dataclass(frozen=True)
class _ResolvedRemoteChunk:
    source_id: str
    source_label: str
    source_path: str
    chunk_index: int
    text: str
    shingles: set[str]


class RemoteSourceProvider(Protocol):
    name: str

    def search(self, query: str, max_results: int) -> list[RemoteCandidate]: ...

    def resolve_text(self, candidate: RemoteCandidate) -> str | None: ...


class _RemoteProviderBase:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def _headers(self, accept: str = "application/json") -> dict[str, str]:
        suffix = ""
        if self._settings.plagiarism_remote_contact_email:
            suffix = f" ({self._settings.plagiarism_remote_contact_email})"
        return {
            "Accept": accept,
            "User-Agent": f"dokimos/0.1.0{suffix}",
        }

    def _fetch_json(self, base_url: str, params: dict[str, str | int]) -> dict:
        url = f"{base_url}?{urlencode(params)}"
        request = Request(url, headers=self._headers("application/json"))
        with urlopen(request, timeout=self._settings.plagiarism_remote_timeout_seconds) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _fetch_xml(self, base_url: str, params: dict[str, str | int]) -> ET.Element:
        url = f"{base_url}?{urlencode(params)}"
        request = Request(url, headers=self._headers("application/atom+xml,application/xml"))
        with urlopen(request, timeout=self._settings.plagiarism_remote_timeout_seconds) as resp:
            return ET.fromstring(resp.read().decode("utf-8"))

    def _fetch_html(self, url: str) -> str:
        request = Request(
            url,
            headers=self._headers("text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"),
        )
        with urlopen(request, timeout=self._settings.plagiarism_remote_timeout_seconds) as resp:
            return resp.read().decode("utf-8", errors="ignore")

    def _fetch_text(self, url: str) -> str | None:
        request = Request(
            url,
            headers=self._headers("text/html,application/pdf;q=0.9,text/plain;q=0.8,*/*;q=0.7"),
        )
        with urlopen(request, timeout=self._settings.plagiarism_remote_timeout_seconds) as resp:
            payload = resp.read()
            content_type = resp.headers.get_content_type().lower()

        if content_type == "application/pdf" or url.lower().endswith(".pdf"):
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(payload)
                tmp_path = Path(tmp.name)
            try:
                return read_document(tmp_path).raw_text
            except (IngestionError, OSError, ValueError) as exc:
                logger.debug("Failed to read remote PDF %s: %s", url, exc)
                return None
            finally:
                tmp_path.unlink(missing_ok=True)

        text = payload.decode("utf-8", errors="ignore")
        parser = _HtmlTextExtractor()
        parser.feed(text)
        extracted = parser.get_text()
        content = extracted or _strip_markup(text)
        return _truncate_text(content, self._settings.plagiarism_remote_max_source_chars)


class OpenAlexProvider(_RemoteProviderBase):
    name = "openalex"

    def search(self, query: str, max_results: int) -> list[RemoteCandidate]:
        params: dict[str, str | int] = {
            "search": query,
            "per-page": max_results,
        }
        if self._settings.plagiarism_remote_contact_email:
            params["mailto"] = self._settings.plagiarism_remote_contact_email

        data = self._fetch_json("https://api.openalex.org/works", params)
        candidates: list[RemoteCandidate] = []
        for item in data.get("results", []):
            title = item.get("display_name") or "OpenAlex work"
            abstract = _abstract_from_inverted_index(item.get("abstract_inverted_index"))
            metadata_text = "\n\n".join(part for part in (title, abstract) if part)
            source_path = (
                item.get("doi")
                or item.get("id")
                or item.get("primary_location", {}).get("landing_page_url")
                or title
            )
            full_text_url = (
                item.get("open_access", {}).get("oa_url")
                or item.get("primary_location", {}).get("pdf_url")
                or item.get("primary_location", {}).get("landing_page_url")
            )
            candidates.append(
                RemoteCandidate(
                    provider=self.name,
                    source_id=f"openalex:{item.get('id', source_path)}",
                    source_label=title,
                    source_path=source_path,
                    metadata_text=metadata_text,
                    full_text_url=full_text_url,
                )
            )
        return candidates

    def resolve_text(self, candidate: RemoteCandidate) -> str | None:
        if self._settings.plagiarism_remote_fetch_full_text and candidate.full_text_url:
            try:
                fetched = self._fetch_text(candidate.full_text_url)
            except (OSError, ValueError) as exc:
                logger.debug(
                    "OpenAlex full-text fetch failed for %s: %s",
                    candidate.source_id,
                    exc,
                )
                fetched = None
            if fetched:
                return fetched
        return candidate.metadata_text or None


class CrossrefProvider(_RemoteProviderBase):
    name = "crossref"

    def search(self, query: str, max_results: int) -> list[RemoteCandidate]:
        data = self._fetch_json(
            "https://api.crossref.org/works",
            {"query.bibliographic": query, "rows": max_results},
        )
        candidates: list[RemoteCandidate] = []
        for item in data.get("message", {}).get("items", []):
            title = " ".join(item.get("title") or []) or "Crossref work"
            abstract = _strip_markup(item.get("abstract") or "")
            metadata_text = "\n\n".join(part for part in (title, abstract) if part)
            doi = item.get("DOI")
            source_path = item.get("URL") or (f"https://doi.org/{doi}" if doi else title)
            candidates.append(
                RemoteCandidate(
                    provider=self.name,
                    source_id=f"crossref:{doi or source_path}",
                    source_label=title,
                    source_path=source_path,
                    metadata_text=metadata_text,
                    full_text_url=None,
                )
            )
        return candidates

    def resolve_text(self, candidate: RemoteCandidate) -> str | None:
        return candidate.metadata_text or None


class ArxivProvider(_RemoteProviderBase):
    name = "arxiv"

    def search(self, query: str, max_results: int) -> list[RemoteCandidate]:
        feed = self._fetch_xml(
            "https://export.arxiv.org/api/query",
            {
                "search_query": f"all:{_quoted_query(query)}",
                "start": 0,
                "max_results": max_results,
            },
        )
        candidates: list[RemoteCandidate] = []
        for entry in feed.findall("atom:entry", _ATOM_NAMESPACE):
            title = _collapse_whitespace(
                entry.findtext("atom:title", default="", namespaces=_ATOM_NAMESPACE)
            )
            summary = _collapse_whitespace(
                entry.findtext("atom:summary", default="", namespaces=_ATOM_NAMESPACE)
            )
            identifier = entry.findtext("atom:id", default="", namespaces=_ATOM_NAMESPACE)
            full_text_url = None
            for link in entry.findall("atom:link", _ATOM_NAMESPACE):
                if link.attrib.get("title") == "pdf":
                    full_text_url = link.attrib.get("href")
                    break
            candidates.append(
                RemoteCandidate(
                    provider=self.name,
                    source_id=f"arxiv:{identifier or title}",
                    source_label=title or "arXiv work",
                    source_path=identifier or title or "arXiv work",
                    metadata_text="\n\n".join(part for part in (title, summary) if part),
                    full_text_url=full_text_url,
                )
            )
        return candidates

    def resolve_text(self, candidate: RemoteCandidate) -> str | None:
        if self._settings.plagiarism_remote_fetch_full_text and candidate.full_text_url:
            try:
                fetched = self._fetch_text(candidate.full_text_url)
            except (OSError, ValueError) as exc:
                logger.debug("arXiv full-text fetch failed for %s: %s", candidate.source_id, exc)
                fetched = None
            if fetched:
                return fetched
        return candidate.metadata_text or None


class DuckDuckGoProvider(_RemoteProviderBase):
    name = "duckduckgo"

    def search(self, query: str, max_results: int) -> list[RemoteCandidate]:
        html = self._fetch_html(
            f"https://html.duckduckgo.com/html/?{urlencode({'q': _quoted_query(query)})}"
        )
        parser = _DuckDuckGoResultsParser()
        parser.feed(html)

        candidates: list[RemoteCandidate] = []
        for title, raw_url in parser.get_results()[:max_results]:
            resolved_url = self._resolve_result_url(raw_url)
            if not resolved_url:
                continue

            candidates.append(
                RemoteCandidate(
                    provider=self.name,
                    source_id=f"duckduckgo:{resolved_url}",
                    source_label=title,
                    source_path=resolved_url,
                    metadata_text=title,
                    full_text_url=resolved_url,
                )
            )

        return candidates

    def resolve_text(self, candidate: RemoteCandidate) -> str | None:
        if not candidate.full_text_url:
            return candidate.metadata_text or None
        try:
            fetched = self._fetch_text(candidate.full_text_url)
        except (OSError, ValueError) as exc:
            logger.debug(
                "DuckDuckGo candidate fetch failed for %s: %s",
                candidate.source_id,
                exc,
            )
            return candidate.metadata_text or None
        return fetched or candidate.metadata_text or None

    def _resolve_result_url(self, raw_url: str) -> str | None:
        if not raw_url:
            return None

        if raw_url.startswith("//"):
            raw_url = f"https:{raw_url}"
        elif raw_url.startswith("/"):
            raw_url = f"https://duckduckgo.com{raw_url}"

        parsed = urlsplit(raw_url)
        if parsed.netloc.endswith("duckduckgo.com") and parsed.path.startswith("/l/"):
            target = parse_qs(parsed.query).get("uddg", [""])[0]
            raw_url = unquote(target) if target else ""

        if not raw_url:
            return None

        parsed_target = urlsplit(raw_url)
        if parsed_target.netloc.endswith("duckduckgo.com"):
            return None
        if parsed_target.scheme not in {"http", "https"}:
            return None
        return raw_url


class RemotePlagiarismEngine:
    """Plagiarism engine that uses free remote providers for candidate discovery."""

    def __init__(
        self,
        settings: Settings | None = None,
        providers: list[RemoteSourceProvider] | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._providers = providers or self._build_default_providers()
        self._provider_map = {provider.name: provider for provider in self._providers}

    def _build_default_providers(self) -> list[RemoteSourceProvider]:
        providers: list[RemoteSourceProvider] = []
        if self._settings.plagiarism_remote_enable_openalex:
            providers.append(OpenAlexProvider(self._settings))
        if self._settings.plagiarism_remote_enable_crossref:
            providers.append(CrossrefProvider(self._settings))
        if self._settings.plagiarism_remote_enable_arxiv:
            providers.append(ArxivProvider(self._settings))
        if self._settings.plagiarism_remote_enable_duckduckgo:
            providers.append(DuckDuckGoProvider(self._settings))
        return providers

    def analyze(
        self,
        chunks: list[Chunk],
        corpus_id: str | None = None,
    ) -> PlagiarismResult:
        del corpus_id
        if not chunks:
            return PlagiarismResult(document_id="unknown")

        document_id = chunks[0].document_id
        remote_chunks = self._resolve_remote_chunks(chunks)
        if not remote_chunks:
            logger.info("Remote plagiarism analysis found no candidate source text")
            return PlagiarismResult(document_id=document_id)

        matches: list[PlagiarismMatch] = []
        shingle_n = self._settings.shingle_size
        jaccard_thresh = self._settings.plagiarism_jaccard_threshold
        fuzz_thresh = self._settings.plagiarism_fuzz_threshold

        for chunk in chunks:
            if len(chunk.text.split()) < _MIN_CHUNK_WORDS:
                continue

            chunk_shingles = set(make_shingles(chunk.text, shingle_n))
            for source_chunk in remote_chunks:
                jac = _jaccard(chunk_shingles, source_chunk.shingles)
                if jac < jaccard_thresh:
                    continue

                fuzz_score = fuzz.token_sort_ratio(chunk.text, source_chunk.text)
                if fuzz_score < fuzz_thresh:
                    continue

                similarity = round(fuzz_score / 100.0, 4)
                if similarity >= 0.95:
                    match_type = "exact"
                elif similarity >= 0.70:
                    match_type = "near"
                else:
                    match_type = "paraphrase"

                matches.append(
                    PlagiarismMatch(
                        finding_id=build_finding_id(
                            "plag",
                            source_chunk.source_id,
                            source_chunk.chunk_index,
                            chunk.index,
                        ),
                        source=SourceMetadata(
                            source_id=source_chunk.source_id,
                            source_label=source_chunk.source_label,
                            source_path=source_chunk.source_path,
                            chunk_index=source_chunk.chunk_index,
                        ),
                        similarity_score=similarity,
                        matched_excerpt=chunk.text[:300],
                        source_excerpt=source_chunk.text[:300],
                        match_type=match_type,
                        offsets=OffsetSpan(start=chunk.start_offset, end=chunk.end_offset),
                    )
                )

        matches = _merge_overlapping(matches)
        overall = max((m.similarity_score for m in matches), default=0.0)
        return PlagiarismResult(
            document_id=document_id,
            matches=matches,
            overall_score=round(overall, 4),
            match_count=len(matches),
        )

    def _resolve_remote_chunks(self, chunks: list[Chunk]) -> list[_ResolvedRemoteChunk]:
        candidates = self._search_candidates(chunks)
        resolved_chunks: list[_ResolvedRemoteChunk] = []
        for candidate in candidates.values():
            provider = self._provider_map.get(candidate.provider)
            if provider is None:
                continue
            try:
                text = provider.resolve_text(candidate)
            except (OSError, RuntimeError, ValueError) as exc:
                logger.warning(
                    "Provider %s failed to resolve %s: %s",
                    candidate.provider,
                    candidate.source_id,
                    exc,
                )
                continue

            if not text or len(text.split()) < _MIN_CHUNK_WORDS:
                continue
            resolved_chunks.extend(self._chunk_remote_source(candidate, text))
        return resolved_chunks

    def _search_candidates(self, chunks: list[Chunk]) -> dict[str, RemoteCandidate]:
        candidates: dict[str, RemoteCandidate] = {}
        query_chunks = sorted(chunks, key=lambda chunk: len(chunk.text), reverse=True)[
            : self._settings.plagiarism_remote_query_max_chunks
        ]

        for chunk in query_chunks:
            if len(chunk.text.split()) < _MIN_CHUNK_WORDS:
                continue

            query = _collapse_whitespace(chunk.text)
            query = query[: self._settings.plagiarism_remote_query_max_chars]
            for provider in self._providers:
                try:
                    results = provider.search(
                        query,
                        self._settings.plagiarism_remote_per_provider_results,
                    )
                except (OSError, RuntimeError, ValueError) as exc:
                    logger.warning("Provider %s search failed: %s", provider.name, exc)
                    continue

                for candidate in results:
                    candidates.setdefault(candidate.source_id, candidate)

        return candidates

    def _chunk_remote_source(
        self,
        candidate: RemoteCandidate,
        text: str,
    ) -> list[_ResolvedRemoteChunk]:
        virtual_path = Path(f"/virtual/{candidate.source_id.replace('/', '_')}.txt")
        document = Document(
            source_path=virtual_path,
            raw_text=text,
            metadata={"filename": candidate.source_label, "format": ".txt"},
        )
        chunks = get_chunks(
            document,
            strategy=self._settings.chunk_strategy,
            chunk_size=self._settings.chunk_size,
            overlap=self._settings.chunk_overlap,
        )
        return [
            _ResolvedRemoteChunk(
                source_id=candidate.source_id,
                source_label=candidate.source_label,
                source_path=candidate.source_path,
                chunk_index=chunk.index,
                text=chunk.text,
                shingles=set(make_shingles(chunk.text, self._settings.shingle_size)),
            )
            for chunk in chunks
            if len(chunk.text.split()) >= _MIN_CHUNK_WORDS
        ]


class HybridPlagiarismEngine:
    """Combine remote discovery with optional local-corpus verification."""

    def __init__(
        self,
        remote_engine: RemotePlagiarismEngine,
        local_engine,
    ) -> None:
        self._remote_engine = remote_engine
        self._local_engine = local_engine

    def analyze(
        self,
        chunks: list[Chunk],
        corpus_id: str | None = None,
    ) -> PlagiarismResult:
        remote = self._remote_engine.analyze(chunks, corpus_id=corpus_id)
        local = self._local_engine.analyze(chunks, corpus_id=corpus_id)
        document_id = remote.document_id if remote.document_id != "unknown" else local.document_id
        matches = _merge_overlapping([*remote.matches, *local.matches])
        overall = max((m.similarity_score for m in matches), default=0.0)
        return PlagiarismResult(
            document_id=document_id,
            matches=matches,
            overall_score=round(overall, 4),
            match_count=len(matches),
        )
