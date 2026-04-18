# Dokimos CLI

Dokimos is a command-line tool for:

- discovering plagiarism evidence from free remote sources
- optionally comparing against a locally indexed corpus
- scoring documents for AI-likeness using stylometric heuristics
- emitting either human-readable summaries or structured JSON reports

The Python distribution name is `dokimos-cli`, but the primary command is `dokimos`.

## What Dokimos Does

Dokimos reads a document, extracts text, splits it into chunks, and can run up to two analyses:

- Plagiarism Detection: queries free remote providers, fetches source text where possible, and verifies overlap locally using shingling, Jaccard similarity, and RapidFuzz reranking.
- AI-Likeness Scoring: computes stylometric signals that may indicate unusually uniform, repetitive, or templated writing.

## Important Caveats

- AI-likeness output is heuristic and statistical. It is not proof of AI authorship.
- Remote plagiarism coverage depends on what free providers can discover and what source text is publicly accessible.
- Paywalled, private, or blocked pages are outside the reach of the free remote backends.
- Local indexing is optional and only helps when you have a private corpus you want to compare against.
- Short documents produce weaker AI-likeness signals and receive an explicit caveat.

## Read Next

- [Getting Started](getting-started.md)
- [CLI Reference](cli-reference.md)
- [Configuration](configuration.md)
- [AI-Likeness](ai-likeness.md)
- [Troubleshooting](troubleshooting.md)
