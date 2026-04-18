# Contributing

## Development Setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev,pdf,docx]"
```

## Local Quality Checks

Run these before opening a pull request:

```bash
./.venv/bin/ruff check src tests README.md
./.venv/bin/python -m pytest
```

If you are changing formatting-sensitive files, also run:

```bash
./.venv/bin/ruff format src tests
```

If you are changing long-form documentation and have `mdbook` installed locally, preview the docs with:

```bash
mdbook serve docs
```

## Pull Requests

- Keep changes focused and explain the user-facing impact.
- Add or update tests when behavior changes.
- Update README or other docs when commands, defaults, or configuration change.
- Prefer small PRs over broad refactors.

## Issue Reports

When reporting a bug, include:

- the command you ran
- the input file type
- relevant `DOKIMOS_*` environment variables
- the observed output or stack trace
