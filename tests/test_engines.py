"""Tests for engine protocol compliance and behaviour."""

from __future__ import annotations

import json
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from dokimos.config import Settings
from dokimos.engines.base import (AiLikelihoodEngine, PlagiarismEngine,
                                  SourceIndexer)
from dokimos.engines.local_indexer import LocalSourceIndexer
from dokimos.engines.placeholder_ai import PlaceholderAiEngine
from dokimos.engines.placeholder_indexer import PlaceholderSourceIndexer
from dokimos.engines.placeholder_plagiarism import PlaceholderPlagiarismEngine
from dokimos.engines.remote_plagiarism import (ArxivProvider,
                                               DuckDuckGoProvider,
                                               HybridPlagiarismEngine,
                                               RemoteCandidate,
                                               RemotePlagiarismEngine)
from dokimos.engines.shingling import make_shingles
from dokimos.engines.shingling_plagiarism import ShinglingPlagiarismEngine
from dokimos.engines.stylometric_ai import StylometricAiEngine
from dokimos.exceptions import CorruptIndexError
from dokimos.schemas.documents import Chunk
from dokimos.schemas.index import (ChunkRef, IndexedChunk, IndexedSource,
                                   InvertedShingleIndex, SourceIndex)


def _write_index(tmp_path: Path, index: SourceIndex) -> Path:
    idx_file = tmp_path / "index.json"
    idx_file.write_text(
        json.dumps(index.model_dump(mode="json"), indent=2),
        encoding="utf-8",
    )
    return idx_file


class TestProtocolCompliance:
    def test_placeholder_plagiarism_satisfies_protocol(self) -> None:
        assert isinstance(PlaceholderPlagiarismEngine(), PlagiarismEngine)

    def test_placeholder_ai_satisfies_protocol(self) -> None:
        assert isinstance(PlaceholderAiEngine(), AiLikelihoodEngine)

    def test_placeholder_indexer_satisfies_protocol(self) -> None:
        assert isinstance(PlaceholderSourceIndexer(), SourceIndexer)

    def test_shingling_satisfies_protocol(self) -> None:
        assert isinstance(ShinglingPlagiarismEngine(), PlagiarismEngine)

    def test_stylometric_satisfies_protocol(self) -> None:
        assert isinstance(StylometricAiEngine(), AiLikelihoodEngine)

    def test_local_indexer_satisfies_protocol(self) -> None:
        assert isinstance(LocalSourceIndexer(), SourceIndexer)

    def test_remote_plagiarism_satisfies_protocol(self) -> None:
        assert isinstance(RemotePlagiarismEngine(providers=[]), PlagiarismEngine)


class _FakeRemoteProvider:
    name = "fake"

    def __init__(
        self,
        candidates: list[RemoteCandidate],
        resolved_text: dict[str, str] | None = None,
        *,
        fail_search: bool = False,
    ) -> None:
        self._candidates = candidates
        self._resolved_text = resolved_text or {}
        self._fail_search = fail_search

    def search(self, query: str, max_results: int) -> list[RemoteCandidate]:
        del query
        if self._fail_search:
            raise OSError("search failed")
        return self._candidates[:max_results]

    def resolve_text(self, candidate: RemoteCandidate) -> str | None:
        return self._resolved_text.get(candidate.source_id, candidate.metadata_text)


class TestPlaceholderPlagiarismEngine:
    def test_returns_zero_score(self, sample_chunks: list[Chunk]) -> None:
        engine = PlaceholderPlagiarismEngine()
        result = engine.analyze(sample_chunks)
        assert result.overall_score == 0.0
        assert result.matches == []

    def test_handles_empty_chunks(self) -> None:
        engine = PlaceholderPlagiarismEngine()
        result = engine.analyze([])
        assert result.document_id == "unknown"


class TestPlaceholderAiEngine:
    def test_returns_zero_risk(self, sample_chunks: list[Chunk]) -> None:
        engine = PlaceholderAiEngine()
        result = engine.analyze(sample_chunks)
        assert result.ai_likeness_score == 0.0
        assert len(result.indicators) > 0

    def test_disclaimer_present(self, sample_chunks: list[Chunk]) -> None:
        engine = PlaceholderAiEngine()
        result = engine.analyze(sample_chunks)
        assert "not proof" in result.disclaimer.lower()


class TestPlaceholderSourceIndexer:
    def test_returns_zero(self, tmp_path: Path) -> None:
        indexer = PlaceholderSourceIndexer()
        assert indexer.index(tmp_path) == 0


class TestShinglingPlagiarismEngine:
    def test_empty_chunks(self) -> None:
        engine = ShinglingPlagiarismEngine()
        result = engine.analyze([])
        assert result.document_id == "unknown"

    def test_no_index_returns_empty(self, sample_chunks: list[Chunk], tmp_path: Path) -> None:
        settings = Settings(index_file=tmp_path / "nonexistent.json")
        engine = ShinglingPlagiarismEngine(settings=settings)
        result = engine.analyze(sample_chunks)
        assert result.matches == []
        assert result.overall_score == 0.0

    def test_finds_match_with_populated_index(
        self, sample_chunks: list[Chunk], populated_index: Path
    ) -> None:
        settings = Settings(index_file=populated_index)
        engine = ShinglingPlagiarismEngine(settings=settings)
        result = engine.analyze(sample_chunks)
        # The sample text and indexed source share enough words to match
        assert result.document_id == sample_chunks[0].document_id

    def test_keeps_overlapping_matches_for_different_source_chunks(self, tmp_path: Path) -> None:
        source_text_0 = "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu"
        source_text_1 = "nu xi omicron pi rho sigma tau upsilon phi chi psi omega"

        shingles_0 = make_shingles(source_text_0, 5)
        shingles_1 = make_shingles(source_text_1, 5)
        idx_file = _write_index(
            tmp_path,
            SourceIndex(
                version="3",
                source_count=1,
                chunk_count=2,
                sources=[
                    IndexedSource(
                        source_id="src-1",
                        source_path="/tmp/source.txt",
                        label="source.txt",
                        chunks=[
                            IndexedChunk(chunk_index=0, text=source_text_0, shingles=shingles_0),
                            IndexedChunk(chunk_index=1, text=source_text_1, shingles=shingles_1),
                        ],
                    )
                ],
                inverted=InvertedShingleIndex(
                    entries={
                        **{s: [ChunkRef(source_idx=0, chunk_idx=0)] for s in shingles_0},
                        **{s: [ChunkRef(source_idx=0, chunk_idx=1)] for s in shingles_1},
                    }
                ),
            ),
        )

        engine = ShinglingPlagiarismEngine(settings=Settings(index_file=idx_file))
        result = engine.analyze(
            [
                Chunk(
                    document_id="doc-1",
                    text=source_text_0,
                    index=0,
                    start_offset=0,
                    end_offset=100,
                ),
                Chunk(
                    document_id="doc-1",
                    text=source_text_1,
                    index=1,
                    start_offset=50,
                    end_offset=150,
                ),
            ]
        )

        assert result.match_count == 2
        assert [m.source.chunk_index for m in result.matches] == [0, 1]

    def test_deduplicates_overlapping_matches_for_same_source_chunk(self, tmp_path: Path) -> None:
        source_text = "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu"
        shingles = make_shingles(source_text, 5)
        idx_file = _write_index(
            tmp_path,
            SourceIndex(
                version="3",
                source_count=1,
                chunk_count=1,
                sources=[
                    IndexedSource(
                        source_id="src-1",
                        source_path="/tmp/source.txt",
                        label="source.txt",
                        chunks=[IndexedChunk(chunk_index=0, text=source_text, shingles=shingles)],
                    )
                ],
                inverted=InvertedShingleIndex(
                    entries={s: [ChunkRef(source_idx=0, chunk_idx=0)] for s in shingles}
                ),
            ),
        )

        engine = ShinglingPlagiarismEngine(settings=Settings(index_file=idx_file))
        result = engine.analyze(
            [
                Chunk(
                    document_id="doc-1",
                    text=source_text,
                    index=0,
                    start_offset=0,
                    end_offset=100,
                ),
                Chunk(
                    document_id="doc-1",
                    text=source_text,
                    index=1,
                    start_offset=50,
                    end_offset=150,
                ),
            ]
        )

        assert result.match_count == 1
        assert [m.source.chunk_index for m in result.matches] == [0]


class TestRemotePlagiarismEngine:
    def test_returns_empty_for_no_chunks(self) -> None:
        engine = RemotePlagiarismEngine(providers=[])
        result = engine.analyze([])
        assert result.document_id == "unknown"

    def test_finds_verified_match_from_remote_candidate(self) -> None:
        chunk_text = "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu"
        candidate = RemoteCandidate(
            provider="fake",
            source_id="fake:1",
            source_label="Remote source",
            source_path="https://example.test/source",
            metadata_text=chunk_text,
        )
        provider = _FakeRemoteProvider(
            [candidate],
            resolved_text={"fake:1": chunk_text},
        )
        engine = RemotePlagiarismEngine(
            settings=Settings(
                plagiarism_remote_query_max_chunks=1,
                plagiarism_remote_per_provider_results=1,
                plagiarism_jaccard_threshold=0.1,
                plagiarism_fuzz_threshold=60.0,
            ),
            providers=[provider],
        )

        result = engine.analyze(
            [
                Chunk(
                    document_id="doc-1",
                    text=chunk_text,
                    index=0,
                    start_offset=0,
                    end_offset=100,
                )
            ]
        )

        assert result.document_id == "doc-1"
        assert result.match_count == 1
        assert result.matches[0].source.source_id == "fake:1"
        assert result.matches[0].source.source_path == "https://example.test/source"

    def test_ignores_provider_search_failures(self, sample_chunks: list[Chunk]) -> None:
        provider = _FakeRemoteProvider([], fail_search=True)
        engine = RemotePlagiarismEngine(providers=[provider])
        result = engine.analyze(sample_chunks)
        assert result.matches == []
        assert result.overall_score == 0.0

    def test_default_backend_is_hybrid_ready(self) -> None:
        assert Settings().plagiarism_backend == "hybrid"


class TestRemoteProviders:
    def test_arxiv_provider_parses_atom_feed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        provider = ArxivProvider(Settings())
        feed = ET.fromstring(
            """
            <feed xmlns="http://www.w3.org/2005/Atom">
              <entry>
                <id>http://arxiv.org/abs/1234.5678</id>
                <title>Sample arXiv Paper</title>
                <summary>Matching abstract text for verification.</summary>
                                <link
                                    href="http://arxiv.org/abs/1234.5678"
                                    rel="alternate"
                                    type="text/html"
                                />
                                <link
                                    title="pdf"
                                    href="http://arxiv.org/pdf/1234.5678v1"
                                    rel="related"
                                    type="application/pdf"
                                />
              </entry>
            </feed>
            """
        )
        monkeypatch.setattr(provider, "_fetch_xml", lambda base_url, params: feed)

        results = provider.search("matching abstract text", max_results=3)

        assert len(results) == 1
        assert results[0].source_id == "arxiv:http://arxiv.org/abs/1234.5678"
        assert results[0].full_text_url == "http://arxiv.org/pdf/1234.5678v1"

    def test_duckduckgo_provider_decodes_redirect_links(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        provider = DuckDuckGoProvider(Settings())
        html = """
        <html>
          <body>
                        <a
                            class="result__a"
                            href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.test%2Fpaper.pdf"
                        >
              Example PDF Result
            </a>
          </body>
        </html>
        """
        monkeypatch.setattr(provider, "_fetch_html", lambda url: html)

        results = provider.search("matching abstract text", max_results=3)

        assert len(results) == 1
        assert results[0].source_path == "https://example.test/paper.pdf"
        assert results[0].source_label == "Example PDF Result"


class TestHybridPlagiarismEngine:
    def test_combines_remote_and_local_matches(self, tmp_path: Path) -> None:
        shared_text = "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu"
        shingles = make_shingles(shared_text, 5)
        idx_file = _write_index(
            tmp_path,
            SourceIndex(
                version="3",
                source_count=1,
                chunk_count=1,
                sources=[
                    IndexedSource(
                        source_id="local-1",
                        source_path="/tmp/source.txt",
                        label="source.txt",
                        chunks=[IndexedChunk(chunk_index=0, text=shared_text, shingles=shingles)],
                    )
                ],
                inverted=InvertedShingleIndex(
                    entries={s: [ChunkRef(source_idx=0, chunk_idx=0)] for s in shingles}
                ),
            ),
        )
        remote_candidate = RemoteCandidate(
            provider="fake",
            source_id="remote-1",
            source_label="Remote source",
            source_path="https://example.test/remote",
            metadata_text=shared_text,
        )
        remote_engine = RemotePlagiarismEngine(
            settings=Settings(index_file=idx_file),
            providers=[
                _FakeRemoteProvider(
                    [remote_candidate],
                    resolved_text={"remote-1": shared_text},
                )
            ],
        )
        local_engine = ShinglingPlagiarismEngine(settings=Settings(index_file=idx_file))
        engine = HybridPlagiarismEngine(remote_engine=remote_engine, local_engine=local_engine)

        result = engine.analyze(
            [
                Chunk(
                    document_id="doc-1",
                    text=shared_text,
                    index=0,
                    start_offset=0,
                    end_offset=100,
                )
            ]
        )

        assert result.match_count == 2
        assert {match.source.source_id for match in result.matches} == {"local-1", "remote-1"}


class TestStylometricAiEngine:
    def test_empty_chunks(self) -> None:
        engine = StylometricAiEngine()
        result = engine.analyze([])
        assert result.document_id == "unknown"

    def test_produces_indicators(self, sample_chunks: list[Chunk]) -> None:
        engine = StylometricAiEngine()
        result = engine.analyze(sample_chunks)
        assert len(result.indicators) == 6
        assert result.ai_likeness_score >= 0.0
        assert len(result.caveats) > 0

    def test_chunk_findings_populated(self, sample_chunks: list[Chunk]) -> None:
        engine = StylometricAiEngine()
        result = engine.analyze(sample_chunks)
        assert len(result.chunk_findings) == len(sample_chunks)
        for cf in result.chunk_findings:
            assert len(cf.signals) == 6

    def test_disclaimer_present(self, sample_chunks: list[Chunk]) -> None:
        engine = StylometricAiEngine()
        result = engine.analyze(sample_chunks)
        assert "not proof" in result.disclaimer.lower()

    def test_sentence_start_repetition_signal_tracks_repeated_openings(self) -> None:
        engine = StylometricAiEngine()
        repeated = engine.analyze(
            [
                Chunk(
                    document_id="doc-1",
                    text=(
                        "Repeat this sentence with similar words. "
                        "Repeat another sentence with similar words. "
                        "Repeat a third sentence with similar words."
                    ),
                    index=0,
                    start_offset=0,
                    end_offset=119,
                )
            ]
        )
        varied = engine.analyze(
            [
                Chunk(
                    document_id="doc-2",
                    text=(
                        "Alpha starts this sentence naturally. "
                        "Beta starts the next sentence differently. "
                        "Gamma opens the third sentence uniquely."
                    ),
                    index=0,
                    start_offset=0,
                    end_offset=119,
                )
            ]
        )

        repeated_indicator = next(
            ind for ind in repeated.indicators if ind.signal_name == "sentence_start_repetition"
        )
        varied_indicator = next(
            ind for ind in varied.indicators if ind.signal_name == "sentence_start_repetition"
        )

        assert repeated_indicator.value > 0.0
        assert varied_indicator.value == 0.0


class TestLocalSourceIndexer:
    def test_indexes_directory(
        self, corpus_dir: Path, settings_with_index: Settings
    ) -> None:
        indexer = LocalSourceIndexer(settings=settings_with_index)
        count = indexer.index(corpus_dir)
        assert count == 2
        # Index file should be created
        assert settings_with_index.index_file.exists()

    def test_skips_already_indexed(
        self, corpus_dir: Path, settings_with_index: Settings
    ) -> None:
        indexer = LocalSourceIndexer(settings=settings_with_index)
        first = indexer.index(corpus_dir)
        second = indexer.index(corpus_dir)
        assert first == 2
        assert second == 0  # all already indexed

    def test_reindexes_modified_file(
        self, corpus_dir: Path, settings_with_index: Settings
    ) -> None:
        import time

        indexer = LocalSourceIndexer(settings=settings_with_index)
        indexer.index(corpus_dir)

        # Touch a file to make it newer
        time.sleep(0.05)
        target = corpus_dir / "source_a.txt"
        target.write_text("Updated content for re-indexing.", encoding="utf-8")

        count = indexer.index(corpus_dir)
        assert count == 1  # only the modified file

        # Verify updated content is in the index
        data = json.loads(settings_with_index.index_file.read_text())
        texts = [
            c["text"]
            for s in data["sources"]
            for c in s["chunks"]
            if "Updated" in c["text"]
        ]
        assert len(texts) == 1

    def test_stores_metadata_fields(
        self, corpus_dir: Path, settings_with_index: Settings
    ) -> None:
        indexer = LocalSourceIndexer(settings=settings_with_index)
        indexer.index(corpus_dir)

        data = json.loads(settings_with_index.index_file.read_text())
        for source in data["sources"]:
            assert source["modified_at"] is not None
            assert source["content_hash"] != ""
            for chunk in source["chunks"]:
                assert chunk["normalized_text"] != ""
                assert chunk["start_offset"] >= 0

    def test_returns_zero_for_nonexistent_dir(
        self, tmp_path: Path, settings_with_index: Settings
    ) -> None:
        indexer = LocalSourceIndexer(settings=settings_with_index)
        assert indexer.index(tmp_path / "nope") == 0


class TestMakeShingles:
    """Tests for the shared shingling utility."""

    def test_basic_shingles(self) -> None:
        result = make_shingles("the quick brown fox jumps", 3)
        assert result == [
            "the quick brown",
            "quick brown fox",
            "brown fox jumps",
        ]

    def test_short_text_returns_single_shingle(self) -> None:
        assert make_shingles("hello world", 5) == ["hello world"]

    def test_empty_text(self) -> None:
        assert make_shingles("", 5) == []

    def test_lowercases(self) -> None:
        result = make_shingles("The Quick BROWN", 2)
        assert all(s == s.lower() for s in result)


class TestInvertedIndex:
    """Tests for the inverted shingle index built during indexing."""

    def test_index_contains_inverted_field(
        self, corpus_dir: Path, settings_with_index: Settings
    ) -> None:
        indexer = LocalSourceIndexer(settings=settings_with_index)
        indexer.index(corpus_dir)

        data = json.loads(settings_with_index.index_file.read_text())
        assert "inverted" in data
        assert data["inverted"] is not None
        assert "entries" in data["inverted"]

    def test_inverted_entries_reference_valid_chunks(
        self, corpus_dir: Path, settings_with_index: Settings
    ) -> None:
        indexer = LocalSourceIndexer(settings=settings_with_index)
        indexer.index(corpus_dir)

        data = json.loads(settings_with_index.index_file.read_text())
        idx = SourceIndex.model_validate(data)
        assert idx.inverted is not None

        for shingle, refs in idx.inverted.entries.items():
            for ref in refs:
                source = idx.sources[ref.source_idx]
                matching = [c for c in source.chunks if c.chunk_index == ref.chunk_idx]
                assert len(matching) == 1
                assert shingle in matching[0].shingles

    def test_version_is_3(
        self, corpus_dir: Path, settings_with_index: Settings
    ) -> None:
        indexer = LocalSourceIndexer(settings=settings_with_index)
        indexer.index(corpus_dir)

        data = json.loads(settings_with_index.index_file.read_text())
        assert data["version"] == "3"

    def test_inverted_roundtrip(self) -> None:
        """InvertedShingleIndex survives JSON serialization roundtrip."""
        inv = InvertedShingleIndex(
            entries={"hello world": [ChunkRef(source_idx=0, chunk_idx=0)]}
        )
        dumped = inv.model_dump(mode="json")
        restored = InvertedShingleIndex.model_validate(dumped)
        assert restored.entries["hello world"][0].source_idx == 0

    def test_reindex_rebuilds_inverted(
        self, corpus_dir: Path, settings_with_index: Settings
    ) -> None:
        """After re-indexing a modified file the inverted index is refreshed."""
        import time

        indexer = LocalSourceIndexer(settings=settings_with_index)
        indexer.index(corpus_dir)

        time.sleep(0.05)
        (corpus_dir / "source_a.txt").write_text(
            "Brand new unique content for test.", encoding="utf-8"
        )
        indexer.index(corpus_dir)

        data = json.loads(settings_with_index.index_file.read_text())
        idx = SourceIndex.model_validate(data)
        assert idx.inverted is not None
        # The new shingles should appear in the inverted index
        new_shingles = make_shingles("Brand new unique content for test.", 5)
        for s in new_shingles:
            assert s in idx.inverted.entries


class TestCandidateRetrieval:
    """Tests that the inverted index narrows the comparison set."""

    def test_candidate_retrieval_finds_match(
        self, sample_chunks: list[Chunk], populated_index: Path
    ) -> None:
        """With inverted index, engine still finds matches (regression)."""
        settings = Settings(index_file=populated_index)
        engine = ShinglingPlagiarismEngine(settings=settings)
        result = engine.analyze(sample_chunks)
        assert result.document_id == sample_chunks[0].document_id

    def test_candidate_retrieval_skips_unrelated(self, tmp_path: Path) -> None:
        """Only source chunks sharing shingles are considered."""
        # Build an index with 2 sources: one matching, one completely unrelated
        matching_shingles = make_shingles("the quick brown fox jumps over the lazy dog", 5)
        unrelated_shingles = make_shingles("alpha beta gamma delta epsilon zeta eta", 5)

        idx = SourceIndex(
            version="3",
            sources=[
                IndexedSource(
                    source_id="match-src",
                    source_path="/tmp/match.txt",
                    label="match.txt",
                    chunks=[
                        IndexedChunk(
                            chunk_index=0,
                            text="the quick brown fox jumps over the lazy dog",
                            shingles=matching_shingles,
                        ),
                    ],
                ),
                IndexedSource(
                    source_id="unrelated-src",
                    source_path="/tmp/unrelated.txt",
                    label="unrelated.txt",
                    chunks=[
                        IndexedChunk(
                            chunk_index=0,
                            text="alpha beta gamma delta epsilon zeta eta theta iota kappa",
                            shingles=unrelated_shingles,
                        ),
                    ],
                ),
            ],
            inverted=InvertedShingleIndex(
                entries={
                    **{s: [ChunkRef(source_idx=0, chunk_idx=0)] for s in matching_shingles},
                    **{s: [ChunkRef(source_idx=1, chunk_idx=0)] for s in unrelated_shingles},
                }
            ),
        )

        idx_file = tmp_path / "index.json"
        idx_file.write_text(
            json.dumps(idx.model_dump(mode="json"), indent=2),
            encoding="utf-8",
        )

        settings = Settings(index_file=idx_file)
        engine = ShinglingPlagiarismEngine(settings=settings)

        chunk = Chunk(
            document_id="test-doc",
            text="the quick brown fox jumps over the lazy dog and more words here",
            index=0,
            start_offset=0,
            end_offset=63,
        )
        result = engine.analyze([chunk])

        # Should match the first source, not the unrelated one
        matched_sources = {m.source.source_id for m in result.matches}
        assert "unrelated-src" not in matched_sources
        if result.matches:
            assert "match-src" in matched_sources

    def test_legacy_v2_index_falls_back_to_brute_force(self, tmp_path: Path) -> None:
        """A v2 index without inverted field still works via brute-force."""
        shingles = make_shingles("the quick brown fox jumps over the lazy dog", 5)
        idx = SourceIndex(
            version="2",
            sources=[
                IndexedSource(
                    source_id="src-1",
                    source_path="/tmp/a.txt",
                    label="a.txt",
                    chunks=[
                        IndexedChunk(
                            chunk_index=0,
                            text="the quick brown fox jumps over the lazy dog",
                            shingles=shingles,
                        ),
                    ],
                ),
            ],
            inverted=None,
        )

        idx_file = tmp_path / "index.json"
        idx_file.write_text(
            json.dumps(idx.model_dump(mode="json"), indent=2),
            encoding="utf-8",
        )

        settings = Settings(index_file=idx_file)
        engine = ShinglingPlagiarismEngine(settings=settings)

        chunk = Chunk(
            document_id="test-doc",
            text="the quick brown fox jumps over the lazy dog and some extra words here",
            index=0,
            start_offset=0,
            end_offset=68,
        )
        result = engine.analyze([chunk])
        assert result.document_id == "test-doc"
        # Brute force should still find the match
        assert result.overall_score > 0.0


# -- Operational-hardening tests -----------------------------------------


class TestAtomicIndexWrite:
    """The index file should never be left in a partial state."""

    def test_no_temp_files_left_after_write(
        self, corpus_dir: Path, settings_with_index: Settings
    ) -> None:
        indexer = LocalSourceIndexer(settings=settings_with_index)
        indexer.index(corpus_dir)

        parent = settings_with_index.index_file.parent
        temps = list(parent.glob("*.tmp"))
        assert temps == [], f"Leftover temp files: {temps}"

    def test_index_valid_json_after_write(
        self, corpus_dir: Path, settings_with_index: Settings
    ) -> None:
        indexer = LocalSourceIndexer(settings=settings_with_index)
        indexer.index(corpus_dir)

        raw = settings_with_index.index_file.read_text(encoding="utf-8")
        data = json.loads(raw)  # must not raise
        assert data["version"] == "3"

    def test_reindex_replaces_atomically(
        self, corpus_dir: Path, settings_with_index: Settings
    ) -> None:
        """Second indexing run replaces the file cleanly."""
        import time

        indexer = LocalSourceIndexer(settings=settings_with_index)
        indexer.index(corpus_dir)

        time.sleep(0.05)
        (corpus_dir / "source_a.txt").write_text(
            "Replaced content.", encoding="utf-8"
        )
        indexer.index(corpus_dir)

        data = json.loads(settings_with_index.index_file.read_text())
        texts = [
            c["text"]
            for s in data["sources"]
            for c in s["chunks"]
        ]
        assert any("Replaced" in t for t in texts)


class TestCorruptIndexHandling:
    """Corrupt or invalid index files produce structured errors."""

    def test_corrupt_json_raises_indexer(self, tmp_path: Path) -> None:
        idx = tmp_path / "index.json"
        idx.write_text("{not valid json!!!", encoding="utf-8")

        settings = Settings(index_file=idx)
        indexer = LocalSourceIndexer(settings=settings)
        with pytest.raises(CorruptIndexError, match="not valid JSON"):
            indexer.index(tmp_path)

    def test_invalid_schema_raises_indexer(self, tmp_path: Path) -> None:
        idx = tmp_path / "index.json"
        # Valid JSON but wrong schema (sources must be a list)
        idx.write_text('{"version": "3", "sources": "not-a-list"}', encoding="utf-8")

        settings = Settings(index_file=idx)
        indexer = LocalSourceIndexer(settings=settings)
        with pytest.raises(CorruptIndexError, match="invalid schema"):
            indexer.index(tmp_path)

    def test_missing_fields_raises_indexer(self, tmp_path: Path) -> None:
        idx = tmp_path / "index.json"
        # sources contains objects missing required fields
        idx.write_text(
            '{"version": "3", "sources": [{"bad": true}]}',
            encoding="utf-8",
        )

        settings = Settings(index_file=idx)
        indexer = LocalSourceIndexer(settings=settings)
        with pytest.raises(CorruptIndexError, match="invalid schema"):
            indexer.index(tmp_path)

    def test_corrupt_json_raises_plagiarism_engine(self, tmp_path: Path) -> None:
        idx = tmp_path / "index.json"
        idx.write_text("<<<garbage>>>", encoding="utf-8")

        settings = Settings(index_file=idx)
        engine = ShinglingPlagiarismEngine(settings=settings)
        chunk = Chunk(
            document_id="d",
            text="enough words here for the minimum chunk length threshold test",
            index=0,
            start_offset=0,
            end_offset=60,
        )
        with pytest.raises(CorruptIndexError, match="not valid JSON"):
            engine.analyze([chunk])

    def test_invalid_schema_raises_plagiarism_engine(self, tmp_path: Path) -> None:
        idx = tmp_path / "index.json"
        idx.write_text('{"sources": "wrong-type"}', encoding="utf-8")

        settings = Settings(index_file=idx)
        engine = ShinglingPlagiarismEngine(settings=settings)
        chunk = Chunk(
            document_id="d",
            text="enough words here for the minimum chunk length threshold test",
            index=0,
            start_offset=0,
            end_offset=60,
        )
        with pytest.raises(CorruptIndexError, match="invalid schema"):
            engine.analyze([chunk])


class TestIndexMetadata:
    """The source index records useful metadata."""

    def test_metadata_present_after_indexing(
        self, corpus_dir: Path, settings_with_index: Settings
    ) -> None:
        indexer = LocalSourceIndexer(settings=settings_with_index)
        indexer.index(corpus_dir)

        data = json.loads(settings_with_index.index_file.read_text())
        assert data["version"] == "3"
        assert "updated_at" in data
        assert data["source_count"] == 2
        assert data["chunk_count"] >= 2

    def test_metadata_updates_on_reindex(
        self, corpus_dir: Path, settings_with_index: Settings
    ) -> None:
        import time

        indexer = LocalSourceIndexer(settings=settings_with_index)
        indexer.index(corpus_dir)

        data1 = json.loads(settings_with_index.index_file.read_text())
        ts1 = data1["updated_at"]

        time.sleep(0.05)
        (corpus_dir / "source_c.txt").write_text(
            "New file for metadata test.", encoding="utf-8"
        )
        indexer.index(corpus_dir)

        data2 = json.loads(settings_with_index.index_file.read_text())
        assert data2["updated_at"] > ts1
        assert data2["source_count"] == 3

    def test_source_count_and_chunk_count_schema(self) -> None:
        idx = SourceIndex(
            sources=[
                IndexedSource(
                    source_id="s1",
                    source_path="/a.txt",
                    label="a.txt",
                    chunks=[
                        IndexedChunk(chunk_index=0, text="hello"),
                        IndexedChunk(chunk_index=1, text="world"),
                    ],
                ),
            ],
            source_count=1,
            chunk_count=2,
        )
        dumped = idx.model_dump(mode="json")
        assert dumped["source_count"] == 1
        assert dumped["chunk_count"] == 2


class TestIndexStats:
    """IndexStats tracks what the indexer did."""

    def test_stats_populated_after_indexing(
        self, corpus_dir: Path, settings_with_index: Settings
    ) -> None:
        indexer = LocalSourceIndexer(settings=settings_with_index)
        indexer.index(corpus_dir)

        stats = indexer.last_stats
        assert stats is not None
        assert stats.indexed == 2
        assert stats.skipped == 0
        assert stats.up_to_date == 0
        assert stats.total_files == 2
        assert stats.recursive is True

    def test_stats_after_reindex(
        self, corpus_dir: Path, settings_with_index: Settings
    ) -> None:
        indexer = LocalSourceIndexer(settings=settings_with_index)
        indexer.index(corpus_dir)
        indexer.index(corpus_dir)

        stats = indexer.last_stats
        assert stats is not None
        assert stats.indexed == 0
        assert stats.up_to_date == 2

    def test_stats_nonrecursive(
        self, corpus_dir: Path, settings_with_index: Settings
    ) -> None:
        indexer = LocalSourceIndexer(settings=settings_with_index)
        indexer.index(corpus_dir, recursive=False)

        stats = indexer.last_stats
        assert stats is not None
        assert stats.recursive is False

    def test_stats_tracks_skipped(self, tmp_path: Path) -> None:
        d = tmp_path / "corpus"
        d.mkdir()
        # Write a file with an unsupported extension — it won't even be glob'd.
        # Instead, create a .txt that triggers a read error.
        bad = d / "bad.txt"
        bad.mkdir()  # directory masquerading as .txt — read_document will fail

        idx = tmp_path / "index.json"
        settings = Settings(index_file=idx, corpus_path=d)
        indexer = LocalSourceIndexer(settings=settings)
        indexer.index(d)

        # bad.txt is a directory so glob("*") with is_file() filter skips it
        stats = indexer.last_stats
        assert stats is not None
        assert stats.total_files == 0
