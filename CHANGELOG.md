# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog, and this project follows Semantic Versioning.

## [0.1.0] - 2026-04-18

### Added

- Public `dokimos` CLI entrypoint for document analysis, plagiarism checks, AI-likeness checks, and source indexing.
- Remote plagiarism discovery across free providers including OpenAlex, Crossref, arXiv, and DuckDuckGo-backed search.
- Hybrid plagiarism mode that merges free remote evidence with optional local indexed corpora.
- Structured JSON reporting and human-readable CLI output for downstream automation and manual review.
- Support for `.txt`, `.md`, `.docx`, and `.pdf` inputs with optional extras for Office and PDF parsing.
- Automated test suite, GitHub Actions CI workflow, issue templates, CODEOWNERS, contribution guidance, security policy, code of conduct, and citation metadata.

### Changed

- Standardized the public CLI and module identity around `dokimos` while keeping the package distribution name as `dokimos-cli`.
- Defaulted plagiarism analysis to the `hybrid` backend so remote evidence remains available even without a local corpus.

### Notes

- This is the first public release of Dokimos.

[0.1.0]: https://github.com/Thavarshan/dokimos/releases/tag/v0.1.0
