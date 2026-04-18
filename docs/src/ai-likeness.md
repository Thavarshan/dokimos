# AI-Likeness

Dokimos includes a rule-based stylometric AI-likeness engine.

It computes six signals per chunk, aggregates them into a document-level score, and maps that score to a low, medium, or high automated-writing-risk band.

This score is heuristic and statistical. It is not proof of AI authorship and should not be treated as such.

## The Six Signals

The current engine computes these signals:

1. `sentence_length_uniformity`
   Measures how uniform sentence lengths are. Low variation can correlate with machine-generated text.

2. `short_sentence_ratio`
   Measures the fraction of very short sentences. A high ratio can suggest formulaic or list-like writing.

3. `long_sentence_ratio`
   Measures the fraction of very long sentences. A high ratio can also indicate auto-generated prose.

4. `lexical_diversity`
   Uses type-token ratio and inverts it into a risk contribution. Low vocabulary variety increases risk.

5. `sentence_start_repetition`
   Measures whether multiple sentences begin with the same word. Repeated openings can suggest template-driven generation.

6. `avg_word_length_uniformity`
   Measures how uniform average word length is across sentences. Unusually regular patterns can be a machine-writing indicator.

## Aggregation and Risk Bands

Each signal contributes to a weighted mean. Most signals use weight `1.0`. `sentence_start_repetition` uses a lower weight because it is less reliable on short text.

The document-level score is then mapped to the configured risk bands:

- `high` when score is at least `DOKIMOS_AI_RISK_HIGH_THRESHOLD` (default `0.6`)
- `medium` when score is at least `DOKIMOS_AI_RISK_MEDIUM_THRESHOLD` (default `0.3`)
- `low` otherwise

Chunk-level findings are also included so you can see where signals cluster inside the document.

## Caveats

The engine always emits a `stylometric_only` caveat:

- `Stylometric heuristics only — not a substitute for human review.`

It also emits a `short_document` caveat when total word count is below `DOKIMOS_AI_SHORT_DOCUMENT_WORDS` (default `80`):

- `Short documents produce less reliable signals.`

## Current Evaluation Status

Dokimos does not currently publish a formal benchmark with false-positive and false-negative rates.

What exists today is regression and ordering coverage in `tests/test_evaluation.py`. Those tests verify that:

- clearly AI-like fixture text scores higher than natural human text
- templated text scores higher than clearly human writing
- mixed text remains within a sensible range
- risk bands line up with configured thresholds
- caveats and explanations are present when expected
- edge cases such as empty documents and single-sentence input do not crash the engine

That is useful for guarding implementation drift, but it is not the same thing as a published accuracy study.

In other words:

- the current tests support relative ordering and stability claims
- they do not support a strong claim like “the AI detector is X% accurate”

## Practical Guidance

- Treat AI-likeness as a review signal, not a verdict.
- Expect domain, genre, and document length to affect the score.
- Use the JSON output when you want to inspect individual indicators, caveats, and chunk findings.
- For higher-stakes decisions, keep a human review step in the loop.
