# Getting Started

## Prerequisites

- Python 3.12+
- A virtual environment is strongly recommended

## Install From This Repository

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev,pdf,docx]"
```

Optional extras:

- `pdf` installs `pymupdf` so `.pdf` files can be read.
- `docx` installs `python-docx` so `.docx` files can be read.
- If you only need plain text and Markdown, `pip install -e ".[dev]"` is enough.

## Installed Command Names

After installation, these invocation forms are available:

- `dokimos ...`
- `python -m dokimos ...`
- `dokimos-cli ...`

If `dokimos` is not on your shell path yet, refresh the editable install:

```bash
pip install -e .
```

## Run Directly From Source

If you have not installed the package into the environment, run from the repository root:

```bash
PYTHONPATH=src python -m dokimos --help
```

## Supported Input Formats

Dokimos currently supports:

- `.txt`
- `.md`
- `.docx`
- `.pdf`

Format support notes:

- `.txt` and `.md` are read as UTF-8 text.
- `.docx` requires the `docx` extra.
- `.pdf` requires the `pdf` extra.

If a dependency is missing, the CLI returns a structured error and exits with status code `1`.

## Quick Start

### Run a full analysis

By default, Dokimos uses the `hybrid` plagiarism backend. That means:

- it queries free remote providers
- it also checks a local corpus if you have indexed one
- if you have not indexed anything locally, the remote path still runs normally

```bash
dokimos analyze essay.txt --format json
```

### Analyze the example PDF

```bash
dokimos analyze examples/Research-Paper.pdf --format json
```

### Build a local corpus index

If you want Dokimos to merge remote matches with your own document set, build a corpus index:

```bash
dokimos index-sources ./corpus
```

Typical output:

```text
Scanned 42 file(s) (recursive)
  Indexed: 38
  Skipped: 1
  Up-to-date: 3
  Index: corpus/index.json
```

### Write a report to disk

```bash
dokimos analyze essay.txt --json-out reports/essay.json
```

For command details, see [CLI Reference](cli-reference.md). For environment variables, see [Configuration](configuration.md).
