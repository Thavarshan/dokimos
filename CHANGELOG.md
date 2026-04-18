# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog, and this project follows Semantic Versioning.

## [0.1.3] - 2026-04-18

### Fixed

- Removed the unsupported `multilingual` key from the mdBook configuration so `mdbook build docs` and `mdbook serve docs` work on the installed mdBook release.
- Ignored generated `docs/book/` output so local docs builds do not pollute the repository status.
- Repaired accidental duplicate export and unreachable error-raise drift in the CLI and engine package files, and re-normalized import formatting across the touched Python modules.

## [0.1.2] - 2026-04-18

### Added

- mdBook-ready project documentation under `docs/` covering setup, CLI usage, configuration, AI-likeness caveats, and troubleshooting.

### Changed

- Reduced the top-level README to a concise landing page that links readers into the dedicated documentation tree.
- Pointed the package metadata documentation URL at the new `docs/README.md` entry page.

### Fixed

- Removed duplicate trailing exports from `dokimos.engines` and duplicate error raises in the CLI source index command.
- Re-normalized import formatting in engine modules and tests to keep the repository validation clean.

## [0.1.1] - 2026-04-18

### Fixed

- Restored a valid export list in `dokimos.engines` so the CLI can import and run again.
- Corrected the README quick example to use the real `dokimos analyze` command and output shape.
- Normalized several import blocks in engine modules and tests to keep the repository Ruff-clean.

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

[0.1.3]: https://github.com/Thavarshan/dokimos/releases/tag/v0.1.3
[0.1.1]: https://github.com/Thavarshan/dokimos/releases/tag/v0.1.1
[0.1.2]: https://github.com/Thavarshan/dokimos/releases/tag/v0.1.2
[0.1.0]: https://github.com/Thavarshan/dokimos/releases/tag/v0.1.0
