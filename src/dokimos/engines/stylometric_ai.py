"""Rule-based stylometric AI-likeness engine.

Computes 6 per-chunk signals that correlate with machine-generated text,
then aggregates into a document-level risk score.  This is a heuristic
baseline — it is **not proof** of AI authorship.

Signals
-------
1. sentence_length_uniformity — low variance in sentence lengths
2. short_sentence_ratio — fraction of very short sentences
3. long_sentence_ratio — fraction of very long sentences
4. lexical_diversity — type-token ratio (inverted: low diversity → high risk)
5. sentence_start_repetition — repeated opening words across sentences
6. avg_word_length_uniformity — low variance in mean word length per sentence
"""

from __future__ import annotations

import logging
import re
import statistics

from dokimos.config import Settings, get_settings
from dokimos.schemas.documents import Chunk
from dokimos.schemas.results import (AiChunkFinding, AiLikelihoodIndicator,
                                     AiLikelihoodResult, Caveat,
                                     build_finding_id)

logger = logging.getLogger(__name__)

_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")

_SIGNAL_NAMES: list[str] = [
    "sentence_length_uniformity",
    "short_sentence_ratio",
    "long_sentence_ratio",
    "lexical_diversity",
    "sentence_start_repetition",
    "avg_word_length_uniformity",
]

# Weights balance the signal contributions.  Sentence-start repetition is
# less reliable for short texts so it gets a lower weight.
_SIGNAL_WEIGHTS: dict[str, float] = {
    "sentence_length_uniformity": 1.0,
    "short_sentence_ratio": 1.0,
    "long_sentence_ratio": 1.0,
    "lexical_diversity": 1.0,
    "sentence_start_repetition": 0.6,
    "avg_word_length_uniformity": 1.0,
}


def _explain_signal(name: str, value: float, triggered: bool) -> str:
    """Return a concise, user-facing explanation for a single signal."""
    if not triggered:
        return _SIGNAL_LOW.get(name, "Signal within normal range.")
    return _SIGNAL_HIGH.get(name, "Signal elevated — may warrant review.")


_SIGNAL_HIGH: dict[str, str] = {
    "sentence_length_uniformity": (
        "Sentence lengths are unusually uniform, a pattern sometimes seen"
        " in machine-generated text."
    ),
    "short_sentence_ratio": (
        "A high proportion of very short sentences suggests formulaic or list-like writing."
    ),
    "long_sentence_ratio": (
        "A high proportion of very long sentences may indicate auto-generated prose."
    ),
    "lexical_diversity": (
        "Vocabulary variety is low, which can occur in repetitive machine output."
    ),
    "sentence_start_repetition": (
        "Multiple sentences begin with the same word, suggesting template-driven generation."
    ),
    "avg_word_length_uniformity": (
        "Average word length per sentence is unusually uniform,"
        " a possible machine-writing indicator."
    ),
}

_SIGNAL_LOW: dict[str, str] = {
    "sentence_length_uniformity": "Sentence lengths show typical human variation.",
    "short_sentence_ratio": "Short-sentence proportion is within normal range.",
    "long_sentence_ratio": "Long-sentence proportion is within normal range.",
    "lexical_diversity": "Vocabulary variety appears normal.",
    "sentence_start_repetition": "Sentence openings are varied.",
    "avg_word_length_uniformity": "Word-length patterns appear natural.",
}


class StylometricAiEngine:
    """Heuristic AI-likeness engine based on 6 stylometric signals."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def analyze(self, chunks: list[Chunk]) -> AiLikelihoodResult:
        if not chunks:
            return AiLikelihoodResult(document_id="unknown")

        document_id = chunks[0].document_id
        trigger = self._settings.ai_signal_trigger_threshold

        chunk_findings: list[AiChunkFinding] = []
        all_signals: dict[str, list[float]] = {k: [] for k in _SIGNAL_NAMES}
        total_words = 0

        for chunk in chunks:
            signals = self._compute_signals(chunk.text)
            total_words += len(chunk.text.split())

            # Weighted chunk-level risk
            risk = self._weighted_mean(signals)
            triggered = [k for k, v in signals.items() if v >= trigger]

            explanation = self._chunk_explanation(triggered)

            chunk_findings.append(
                AiChunkFinding(
                    finding_id=build_finding_id("ai", document_id, chunk.index),
                    chunk_index=chunk.index,
                    ai_likeness_score=round(min(risk, 1.0), 4),
                    signals={k: round(v, 4) for k, v in signals.items()},
                    signals_triggered=triggered,
                    explanation=explanation,
                )
            )

            for k, v in signals.items():
                all_signals[k].append(v)

        # Document-level indicators: mean of each signal across chunks
        indicators: list[AiLikelihoodIndicator] = []
        for name in _SIGNAL_NAMES:
            vals = all_signals[name]
            avg = statistics.mean(vals) if vals else 0.0
            trig = avg >= trigger
            desc = _explain_signal(name, avg, trig)
            indicators.append(
                AiLikelihoodIndicator(
                    signal_name=name,
                    value=round(min(avg, 1.0), 4),
                    description=desc,
                    triggered=trig,
                )
            )

        # Document-level aggregate: weighted mean of indicator values
        indicator_map = {i.signal_name: i.value for i in indicators}
        aggregate = self._weighted_mean(indicator_map)
        aggregate = round(min(aggregate, 1.0), 4)

        # Risk tier from configurable thresholds
        if aggregate >= self._settings.ai_risk_high_threshold:
            risk_tier = "high"
        elif aggregate >= self._settings.ai_risk_medium_threshold:
            risk_tier = "medium"
        else:
            risk_tier = "low"

        doc_signals_triggered = [i.signal_name for i in indicators if i.triggered]

        caveats = self._build_caveats(total_words)

        logger.info(
            "AI-likeness analysis: ai_likeness_score=%.2f for document %s",
            aggregate,
            document_id,
        )

        return AiLikelihoodResult(
            document_id=document_id,
            indicators=indicators,
            chunk_findings=chunk_findings,
            ai_likeness_score=aggregate,
            automated_writing_risk=risk_tier,
            signals_triggered=doc_signals_triggered,
            human_review_recommended=risk_tier in ("medium", "high"),
            caveats=caveats,
        )

    # ---- aggregation helpers -----------------------------------------------

    @staticmethod
    def _weighted_mean(signals: dict[str, float]) -> float:
        """Compute a weighted mean over the signal dict."""
        total_w = 0.0
        total_v = 0.0
        for name, val in signals.items():
            w = _SIGNAL_WEIGHTS.get(name, 1.0)
            total_w += w
            total_v += val * w
        return total_v / total_w if total_w else 0.0

    def _build_caveats(self, total_words: int) -> list[Caveat]:
        """Emit only the caveats relevant to the analysed document."""
        caveats = [
            Caveat(
                code="stylometric_only",
                message="Stylometric heuristics only — not a substitute for human review.",
                severity="warning",
                scope="ai_likelihood",
            ),
        ]
        if total_words < self._settings.ai_short_document_words:
            caveats.append(
                Caveat(
                    code="short_document",
                    message="Short documents produce less reliable signals.",
                    severity="info",
                    scope="ai_likelihood",
                ),
            )
        return caveats

    @staticmethod
    def _chunk_explanation(triggered: list[str]) -> str:
        """Build a concise explanation for a chunk finding."""
        if not triggered:
            return "No unusual writing patterns detected in this chunk."
        parts = [_SIGNAL_HIGH.get(s, s) for s in triggered[:3]]
        return " ".join(parts)

    # ---- signal computation ------------------------------------------------

    def _compute_signals(self, text: str) -> dict[str, float]:
        sentences = [s.strip() for s in _SENTENCE_RE.split(text) if s.strip()]
        if not sentences:
            return {k: 0.0 for k in _SIGNAL_NAMES}

        word_counts = [len(s.split()) for s in sentences]
        words_flat = text.lower().split()

        return {
            "sentence_length_uniformity": self._sentence_length_uniformity(word_counts),
            "short_sentence_ratio": self._short_sentence_ratio(word_counts),
            "long_sentence_ratio": self._long_sentence_ratio(word_counts),
            "lexical_diversity": self._lexical_diversity(words_flat),
            "sentence_start_repetition": self._sentence_start_repetition(sentences),
            "avg_word_length_uniformity": self._avg_word_length_uniformity(sentences),
        }

    @staticmethod
    def _sentence_length_uniformity(word_counts: list[int]) -> float:
        if len(word_counts) < 2:
            return 0.0
        std = statistics.stdev(word_counts)
        mean = statistics.mean(word_counts)
        if mean == 0:
            return 0.0
        cv = std / mean  # coefficient of variation
        # Low CV → high uniformity → higher risk
        return max(0.0, min(1.0, 1.0 - cv))

    def _short_sentence_ratio(self, word_counts: list[int]) -> float:
        threshold = self._settings.ai_short_sentence_threshold
        short = sum(1 for wc in word_counts if wc <= threshold)
        return short / len(word_counts)

    def _long_sentence_ratio(self, word_counts: list[int]) -> float:
        threshold = self._settings.ai_long_sentence_threshold
        long_count = sum(1 for wc in word_counts if wc >= threshold)
        return long_count / len(word_counts)

    @staticmethod
    def _lexical_diversity(words: list[str]) -> float:
        if not words:
            return 0.0
        ttr = len(set(words)) / len(words)
        # Low TTR → less diverse → higher risk
        return max(0.0, min(1.0, 1.0 - ttr))

    @staticmethod
    def _sentence_start_repetition(sentences: list[str]) -> float:
        if len(sentences) < 2:
            return 0.0
        first_words = [s.split()[0].lower() for s in sentences if s.split()]
        if not first_words:
            return 0.0
        most_common_count = max(first_words.count(w) for w in set(first_words))
        return (most_common_count - 1) / len(first_words)

    @staticmethod
    def _avg_word_length_uniformity(sentences: list[str]) -> float:
        avg_lengths: list[float] = []
        for s in sentences:
            ws = s.split()
            if ws:
                avg_lengths.append(statistics.mean(len(w) for w in ws))
        if len(avg_lengths) < 2:
            return 0.0
        std = statistics.stdev(avg_lengths)
        mean = statistics.mean(avg_lengths)
        if mean == 0:
            return 0.0
        cv = std / mean
        return max(0.0, min(1.0, 1.0 - cv))
