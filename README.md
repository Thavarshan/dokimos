# Dokimos CLI

[![CI](https://github.com/Thavarshan/dokimos/actions/workflows/ci.yml/badge.svg)](https://github.com/Thavarshan/dokimos/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/Thavarshan/dokimos/blob/main/LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://github.com/Thavarshan/dokimos)

Dokimos discovers plagiarism evidence from free remote sources, optionally checks a local indexed corpus, and scores documents for AI-likeness using stylometric heuristics.

The Python distribution name is still `dokimos-cli`, but the primary command is `dokimos`.

Supports `.txt`, `.md`, `.docx`, and `.pdf` inputs.

```text
dokimos analyze essay.txt

Document: essay.txt
Status:   complete
Summary:  analyses=plagiarism, ai_check plagiarism=0.12 ai=0.63
```

## Important Caveats

- AI-likeness output is heuristic and statistical. It is not proof of AI authorship.
- Remote plagiarism coverage depends on what free providers can discover and what source text is publicly accessible.
- Paywalled, private, or blocked pages are outside the reach of the free remote backends.
- Local indexing is optional and only adds value when you have a private corpus you specifically want included.
- Short documents produce weaker AI-likeness signals and may include caveats.

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev,pdf,docx]"
```

If you only need plain text and Markdown, `pip install -e ".[dev]"` is enough.

## Quick Start

```bash
# Full analysis with structured output
dokimos analyze essay.txt --format json

# Build an optional local corpus index
dokimos index-sources ./corpus

# Write a JSON report to disk
dokimos analyze essay.txt --json-out reports/essay.json
```

Dokimos defaults to the `hybrid` plagiarism backend, which means it queries free remote providers and also consults a local corpus if you have indexed one.

## Documentation

Detailed documentation now lives under [docs/](docs/README.md):

- [Overview](docs/src/index.md)
- [Getting Started](docs/src/getting-started.md)
- [CLI Reference](docs/src/cli-reference.md)
- [Configuration](docs/src/configuration.md)
- [AI-Likeness](docs/src/ai-likeness.md)
- [Troubleshooting](docs/src/troubleshooting.md)

The docs tree is mdBook-ready. If `mdbook` is installed locally, preview it with:

```bash
mdbook serve docs
```

## Project Links

- GitHub: <https://github.com/Thavarshan/dokimos>
- Issues: <https://github.com/Thavarshan/dokimos/issues>
- Contributing: [CONTRIBUTING.md](CONTRIBUTING.md)
- Security policy: [SECURITY.md](SECURITY.md)
- Code of conduct: [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)
- Changelog: [CHANGELOG.md](CHANGELOG.md)
- Citation metadata: [CITATION.cff](CITATION.cff)
