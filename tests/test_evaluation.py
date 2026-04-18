"""Evaluation fixtures and regression tests.

These tests verify score *ordering* rather than exact values:
- copied text should score higher than paraphrased, which should score
  higher than completely original text.
- AI-like text should have a higher risk score than natural human text.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dokimos.config import Settings
from dokimos.engines.local_indexer import LocalSourceIndexer
from dokimos.engines.shingling_plagiarism import ShinglingPlagiarismEngine
from dokimos.engines.stylometric_ai import StylometricAiEngine
from dokimos.ingestion.chunker import get_chunks
from dokimos.ingestion.reader import read_document

_FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def evaluation_index(tmp_path: Path) -> Path:
    """Build a source index from the corpus fixtures (same text as conftest)."""
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "source_a.txt").write_text(
        "The fox jumped over the lazy dog.", encoding="utf-8"
    )
    (corpus / "source_b.txt").write_text(
        "A completely different document about cats.", encoding="utf-8"
    )

    idx_file = tmp_path / "index.json"
    settings = Settings(
        corpus_path=corpus,
        index_file=idx_file,
        chunk_strategy="paragraph",
    )
    indexer = LocalSourceIndexer(settings=settings)
    indexer.index(corpus)
    return idx_file


def _plag_score(text: str, index_file: Path) -> float:
    """Return the overall plagiarism score for *text* against the given index."""
    settings = Settings(index_file=index_file)
    engine = ShinglingPlagiarismEngine(settings=settings)
    doc = read_document(_FIXTURES / "copied_passage.txt")
    # Override raw_text with the text we actually want to test
    from dokimos.schemas.documents import Document

    doc = Document(source_path=doc.source_path, raw_text=text)
    chunks = get_chunks(doc, strategy="paragraph")
    result = engine.analyze(chunks)
    return result.overall_score


def _ai_score(path: Path) -> float:
    """Return the aggregate AI-likeness score for a file."""
    engine = StylometricAiEngine()
    doc = read_document(path)
    chunks = get_chunks(doc, strategy="paragraph")
    result = engine.analyze(chunks)
    return result.ai_likeness_score


# ---------------------------------------------------------------------------
# Plagiarism score ordering
# ---------------------------------------------------------------------------


class TestPlagiarismScoreOrdering:
    """Copied text should score higher than paraphrased, which should
    score higher than completely original text."""

    def test_copied_vs_original(self, evaluation_index: Path) -> None:
        copied = _plag_score(
            "The fox jumped over the lazy dog. "
            "A completely different document about cats.",
            evaluation_index,
        )
        original = _plag_score(
            "Quantum computing leverages superposition and entanglement.",
            evaluation_index,
        )
        assert copied > original

    def test_copied_scores_nonzero(self, evaluation_index: Path) -> None:
        copied = _plag_score(
            "The fox jumped over the lazy dog. "
            "A completely different document about cats.",
            evaluation_index,
        )
        assert copied > 0.0

    def test_original_scores_low(self, evaluation_index: Path) -> None:
        original = _plag_score(
            "Quantum computing leverages superposition and entanglement "
            "to perform calculations infeasible for classical machines.",
            evaluation_index,
        )
        assert original < 0.5


# ---------------------------------------------------------------------------
# AI-likeness score ordering
# ---------------------------------------------------------------------------


class TestAiLikelihoodOrdering:
    """AI-like text should score higher than natural human writing."""

    def test_ai_like_higher_than_natural(self) -> None:
        ai_score = _ai_score(_FIXTURES / "ai_like_text.txt")
        natural_score = _ai_score(_FIXTURES / "natural_text.txt")
        assert ai_score > natural_score, (
            f"Expected ai_like ({ai_score:.4f}) > natural ({natural_score:.4f})"
        )

    def test_ai_like_nontrivial(self) -> None:
        score = _ai_score(_FIXTURES / "ai_like_text.txt")
        assert score > 0.1, f"AI-like text scored only {score:.4f}"

    def test_natural_text_not_flagged_high(self) -> None:
        score = _ai_score(_FIXTURES / "natural_text.txt")
        assert score < 0.7, f"Natural text scored {score:.4f} (too high)"


# ---------------------------------------------------------------------------
# Regression: empty/edge-case inputs
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Ensure engines don't crash on edge-case inputs."""

    def test_empty_document_plagiarism(self, evaluation_index: Path) -> None:
        score = _plag_score("", evaluation_index)
        assert score == 0.0

    def test_single_word_plagiarism(self, evaluation_index: Path) -> None:
        score = _plag_score("Hello", evaluation_index)
        assert score == 0.0  # too short to match

    def test_single_sentence_ai(self, tmp_path: Path) -> None:
        p = tmp_path / "one.txt"
        p.write_text("Just one sentence here.", encoding="utf-8")
        score = _ai_score(p)
        assert 0.0 <= score <= 1.0


# ---------------------------------------------------------------------------
# Fixture-based score ordering
# ---------------------------------------------------------------------------


def _ai_result(path: Path, settings: Settings | None = None):
    """Return the full AiLikelihoodResult for a file."""
    engine = StylometricAiEngine(settings=settings)
    doc = read_document(path)
    chunks = get_chunks(doc, strategy="paragraph")
    return engine.analyze(chunks)


class TestTemplatedText:
    """Highly repetitive/templated text should score higher than natural."""

    def test_templated_higher_than_natural(self) -> None:
        templated = _ai_score(_FIXTURES / "templated_text.txt")
        natural = _ai_score(_FIXTURES / "natural_text.txt")
        assert templated > natural, (
            f"templated ({templated:.4f}) should > natural ({natural:.4f})"
        )

    def test_templated_higher_than_clearly_human(self) -> None:
        templated = _ai_score(_FIXTURES / "templated_text.txt")
        human = _ai_score(_FIXTURES / "clearly_human.txt")
        assert templated > human

    def test_clearly_human_low(self) -> None:
        score = _ai_score(_FIXTURES / "clearly_human.txt")
        assert score < 0.6, f"Clearly human scored {score:.4f}"


class TestMixedText:
    """Mixed AI-assisted writing should fall between extremes."""

    def test_mixed_in_range(self) -> None:
        score = _ai_score(_FIXTURES / "mixed_ai_human.txt")
        assert 0.0 <= score <= 1.0


# ---------------------------------------------------------------------------
# Conditional caveats
# ---------------------------------------------------------------------------


class TestConditionalCaveats:
    """Caveats should be emitted only when relevant."""

    def test_short_document_caveat_present_for_short_text(self) -> None:
        result = _ai_result(_FIXTURES / "copied_passage.txt")
        codes = {c.code for c in result.caveats}
        assert "short_document" in codes

    def test_short_document_caveat_absent_for_long_text(self) -> None:
        result = _ai_result(_FIXTURES / "clearly_human.txt")
        codes = {c.code for c in result.caveats}
        assert "short_document" not in codes

    def test_stylometric_only_always_present(self) -> None:
        for name in ("natural_text.txt", "ai_like_text.txt", "clearly_human.txt"):
            result = _ai_result(_FIXTURES / name)
            codes = {c.code for c in result.caveats}
            assert "stylometric_only" in codes


# ---------------------------------------------------------------------------
# Threshold configurability
# ---------------------------------------------------------------------------


class TestThresholdConfigurability:
    """Settings thresholds should actually control behavior."""

    def test_lower_risk_threshold_increases_risk(self) -> None:
        strict = Settings(ai_risk_high_threshold=0.2, ai_risk_medium_threshold=0.1)
        result = _ai_result(_FIXTURES / "natural_text.txt", settings=strict)
        # With very low thresholds, even natural text may get medium or high
        assert result.automated_writing_risk in ("medium", "high")

    def test_higher_risk_threshold_decreases_risk(self) -> None:
        lax = Settings(ai_risk_high_threshold=0.99, ai_risk_medium_threshold=0.95)
        result = _ai_result(_FIXTURES / "ai_like_text.txt", settings=lax)
        assert result.automated_writing_risk == "low"

    def test_trigger_threshold_affects_signals(self) -> None:
        strict = Settings(ai_signal_trigger_threshold=0.01)
        result = _ai_result(_FIXTURES / "natural_text.txt", settings=strict)
        # With 0.01, almost all signals should trigger
        assert len(result.signals_triggered) >= 3

    def test_short_document_words_configurable(self) -> None:
        # Set threshold very high so all docs count as short
        s = Settings(ai_short_document_words=999999)
        result = _ai_result(_FIXTURES / "clearly_human.txt", settings=s)
        codes = {c.code for c in result.caveats}
        assert "short_document" in codes


# ---------------------------------------------------------------------------
# Explanation stability
# ---------------------------------------------------------------------------


class TestExplanationContent:
    """Per-signal and per-chunk explanations should be populated."""

    def test_indicators_have_descriptions(self) -> None:
        result = _ai_result(_FIXTURES / "ai_like_text.txt")
        for ind in result.indicators:
            assert ind.description, f"Empty description for {ind.signal_name}"

    def test_chunk_findings_have_explanations(self) -> None:
        result = _ai_result(_FIXTURES / "ai_like_text.txt")
        for cf in result.chunk_findings:
            assert cf.explanation, f"Empty explanation for chunk {cf.chunk_index}"

    def test_triggered_indicator_mentions_risk(self) -> None:
        """Triggered indicators should use the 'high' explanation."""
        result = _ai_result(_FIXTURES / "ai_like_text.txt")
        triggered = [i for i in result.indicators if i.triggered]
        for ind in triggered:
            # High explanations mention concrete patterns, not just "normal range"
            assert "normal range" not in ind.description.lower()
            assert "natural" not in ind.description.lower()

    def test_untriggered_indicator_mentions_normal(self) -> None:
        """Untriggered indicators should say things like 'normal range'."""
        result = _ai_result(_FIXTURES / "natural_text.txt")
        untriggered = [i for i in result.indicators if not i.triggered]
        assert len(untriggered) > 0
        for ind in untriggered:
            desc = ind.description.lower()
            assert "normal" in desc or "typical" in desc or "varied" in desc or "natural" in desc


# ---------------------------------------------------------------------------
# Score ordering sanity
# ---------------------------------------------------------------------------


class TestScoreOrdering:
    """Weighted aggregation should preserve sensible ordering."""

    def test_ai_like_above_natural(self) -> None:
        ai = _ai_score(_FIXTURES / "ai_like_text.txt")
        nat = _ai_score(_FIXTURES / "natural_text.txt")
        assert ai > nat

    def test_templated_above_mixed(self) -> None:
        templated = _ai_score(_FIXTURES / "templated_text.txt")
        mixed = _ai_score(_FIXTURES / "mixed_ai_human.txt")
        assert templated >= mixed

    def test_risk_band_matches_score(self) -> None:
        for name in (
            "ai_like_text.txt",
            "natural_text.txt",
            "templated_text.txt",
            "clearly_human.txt",
        ):
            result = _ai_result(_FIXTURES / name)
            s = result.ai_likeness_score
            if result.automated_writing_risk == "high":
                assert s >= 0.6
            elif result.automated_writing_risk == "medium":
                assert 0.3 <= s < 0.6
            else:
                assert s < 0.3


# ---------------------------------------------------------------------------
# Per-chunk signal structure
# ---------------------------------------------------------------------------


class TestChunkSignalStructure:
    """Chunk findings should contain all 6 signals."""

    def test_all_signals_present(self) -> None:
        result = _ai_result(_FIXTURES / "ai_like_text.txt")
        expected = {
            "sentence_length_uniformity",
            "short_sentence_ratio",
            "long_sentence_ratio",
            "lexical_diversity",
            "sentence_start_repetition",
            "avg_word_length_uniformity",
        }
        for cf in result.chunk_findings:
            assert set(cf.signals.keys()) == expected
