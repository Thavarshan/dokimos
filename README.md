# Dokimos CLI

[![CI](https://github.com/Thavarshan/dokimos/actions/workflows/ci.yml/badge.svg)](https://github.com/Thavarshan/dokimos/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/Thavarshan/dokimos/blob/main/LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://github.com/Thavarshan/dokimos)

`dokimos` is a command-line tool for:

- searching free remote sources for plagiarism evidence
- optionally indexing a local source corpus for supplemental plagiarism comparison
- scoring documents for AI-likeness / automated-writing-risk heuristics
- emitting either human-readable summaries or structured JSON reports

The Python distribution name is still `dokimos-cli`, but the primary command is `dokimos`.

Repository:

- GitHub: <https://github.com/Thavarshan/dokimos>
- Issues: <https://github.com/Thavarshan/dokimos/issues>
- Contributing: [CONTRIBUTING.md](CONTRIBUTING.md)
- Security policy: [SECURITY.md](SECURITY.md)
- Code of conduct: [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)
- Changelog: [CHANGELOG.md](CHANGELOG.md)
- Citation metadata: [CITATION.cff](CITATION.cff)

## What It Does

Dokimos reads a document, extracts text, splits it into chunks, and runs up to two analyses:

- Plagiarism detection: searches free internet and academic sources, retrieves candidate text where possible, and verifies overlap locally using shingling, Jaccard similarity, and fuzzy reranking. In hybrid mode it also merges matches from an optional local indexed corpus.
- AI-likeness scoring: computes stylometric heuristics such as sentence-length uniformity, lexical diversity, and sentence-start repetition.

The tool is designed for practical CLI analysis workflows and downstream integrations that want a stable JSON output contract.

Important limitations:

- AI-likeness output is heuristic and statistical. It is not proof of AI authorship.
- Remote plagiarism coverage depends on what free providers can discover and what source text is publicly accessible.
- Paywalled, private, or blocked pages are outside the reach of the free remote backends.
- Local indexing is optional and only adds value when you have a private corpus you specifically want included.
- Short documents produce weaker AI-likeness signals and may include caveats.

## Installation

### Prerequisites

- Python 3.12+
- A virtual environment is strongly recommended

### Install From This Repository

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev,pdf,docx]"
```

Notes:

- `pdf` installs `pymupdf` so `.pdf` files can be read.
- `docx` installs `python-docx` so `.docx` files can be read.
- If you only need plain text and Markdown, `pip install -e ".[dev]"` is enough.

### Installed Command Names

After installation, these invocation forms are available:

- `dokimos ...`
- `python -m dokimos ...`

Compatibility forms also still work:

- `dokimos-cli ...`

If the `dokimos` shell command does not exist yet after packaging changes, rerun:

```bash
pip install -e .
```

### Run Directly From Source

If you have not installed the package into the environment, you can still run it from the repository root:

```bash
PYTHONPATH=src python -m dokimos --help
```

## Supported Input Formats

Dokimos currently supports:

- `.txt`
- `.md`
- `.docx`
- `.pdf`

Format support details:

- `.txt` and `.md` are read as UTF-8 text.
- `.docx` requires the `docx` extra.
- `.pdf` requires the `pdf` extra.

If a dependency is missing, the CLI returns a structured error and exits with status code `1`.

## Quick Start

### 1. Run a full analysis

By default, Dokimos now uses the `hybrid` plagiarism backend, which means:

- it searches free remote providers first
- it also consults a local corpus if you have indexed one
- if you have not indexed anything locally, the remote path still runs normally

```bash
dokimos analyze essay.txt --format json
```

### 2. Run against the example PDF in this repository

```bash
dokimos analyze examples/Research-Paper.pdf --format json
```

### 3. Optionally add a local corpus for hybrid comparison

If you want Dokimos to merge remote matches with your own local document set, build a corpus index:

```bash
dokimos index-sources ./corpus
```

By default the command scans recursively. It prints a summary like:

```text
Scanned 42 file(s) (recursive)
  Indexed: 38
  Skipped: 1
  Up-to-date: 3
  Index: corpus/index.json
```

### 4. Write a report to disk

```bash
dokimos analyze essay.txt --json-out reports/essay.json
```

## Command Reference

Top-level help:

```bash
dokimos --help
```

Global options:

- `--log-level TEXT`: set log level, for example `DEBUG`, `INFO`, `WARNING`, or `ERROR`
- `--install-completion`: install shell completion
- `--show-completion`: print completion for the current shell
- `--help`: show help and exit

Available commands:

- `analyze`
- `plagiarism`
- `ai-check`
- `index-sources`

### `dokimos analyze`

Runs both plagiarism and AI-likeness analysis unless one is explicitly disabled.

```bash
dokimos analyze FILE_PATH [OPTIONS]
```

Arguments:

- `FILE_PATH`: path to the document to analyze

Options:

- `--format [json|text]`: output format, default `text`
- `--json-out PATH`: write the JSON report to a file instead of stdout
- `--no-plagiarism`: skip plagiarism analysis
- `--no-ai-check`: skip AI-likeness analysis
- `--help`

Examples:

```bash
dokimos analyze paper.pdf
dokimos analyze paper.pdf --format json
dokimos analyze paper.pdf --json-out output/paper.json
dokimos analyze paper.pdf --no-plagiarism
dokimos analyze paper.pdf --no-ai-check
```

### `dokimos plagiarism`

Runs plagiarism-only analysis.

```bash
dokimos plagiarism FILE_PATH [OPTIONS]
```

Arguments:

- `FILE_PATH`: path to the document to analyze

Options:

- `--format [json|text]`: output format, default `text`
- `--json-out PATH`: write the JSON report to a file instead of stdout
- `--help`

Example:

```bash
dokimos plagiarism essay.txt --format json
```

### `dokimos ai-check`

Runs AI-likeness / automated-writing-risk analysis only.

```bash
dokimos ai-check FILE_PATH [OPTIONS]
```

Arguments:

- `FILE_PATH`: path to the document to analyze

Options:

- `--format [json|text]`: output format, default `text`
- `--json-out PATH`: write the JSON report to a file instead of stdout
- `--help`

Example:

```bash
dokimos ai-check essay.txt --format json
```

### `dokimos index-sources`

Indexes a directory of source documents into the optional local corpus index used by `local` and `hybrid` plagiarism backends.

```bash
dokimos index-sources DIRECTORY_PATH [OPTIONS]
```

Arguments:

- `DIRECTORY_PATH`: directory containing source documents

Options:

- `--recursive / --no-recursive`: recurse into subdirectories, default `--recursive`
- `--help`

Examples:

```bash
dokimos index-sources ./corpus
dokimos index-sources ./corpus --no-recursive
```

Behavior notes:

- Files are indexed only if they match supported extensions.
- Re-indexing is incremental and skips files that have not changed.
- The on-disk index is written to `corpus/index.json` by default.
- Remote plagiarism analysis does not require this index.

## Output Behavior

Dokimos supports two output modes.

### Text output

`--format text` is the default. It prints a human-readable summary using Rich.

Important behavior:

- Text output is written to stderr, not stdout.
- This is useful for interactive terminal use.
- If you are scripting, prefer `--format json`.

### JSON output

`--format json` prints strict JSON to stdout.

This is the best choice for:

- shell pipelines
- CI jobs
- API handoff
- storing analysis artifacts

### `--json-out`

`--json-out PATH` always writes JSON to the specified file, regardless of the selected `--format` value.

Example:

```bash
dokimos analyze essay.txt --format text --json-out reports/essay.json
```

In that case:

- the JSON report is written to the file
- the CLI prints a confirmation message
- JSON is not emitted to stdout

## JSON Report Shape

The report includes top-level fields like:

- `schema_version`
- `document_id`
- `version`
- `status`
- `generated_at`
- `document`
- `summary`
- `plagiarism`
- `ai_likelihood`
- `caveats`

Example:

```json
{
  "schema_version": "1.0",
  "document_id": "...",
  "status": "complete",
  "document": {
    "source_path": "essay.txt",
    "filename": "essay.txt",
    "file_format": ".txt",
    "character_count": 1234
  },
  "summary": {
    "analyses_run": ["plagiarism", "ai_check"],
    "plagiarism_match_count": 2,
    "plagiarism_overall_score": 0.85,
    "ai_likeness_score": 0.34,
    "automated_writing_risk": "medium",
    "human_review_recommended": true
  },
  "plagiarism": { "...": "..." },
  "ai_likelihood": { "...": "..." },
  "caveats": []
}
```

## Configuration

All settings can be overridden with `DOKIMOS_`-prefixed environment variables.

### Core settings

| Variable              | Default             | Description                                   |
| --------------------- | ------------------- | --------------------------------------------- |
| `DOKIMOS_LOG_LEVEL`   | `INFO`              | Default application log level                 |
| `DOKIMOS_CORPUS_PATH` | `corpus`            | Directory used for the internal source corpus |
| `DOKIMOS_INDEX_FILE`  | `corpus/index.json` | JSON index file path                          |
| `DOKIMOS_OUTPUT_DIR`  | `output`            | Default output directory for reports          |

### Chunking settings

| Variable                 | Default     | Description                                    |
| ------------------------ | ----------- | ---------------------------------------------- |
| `DOKIMOS_CHUNK_STRATEGY` | `paragraph` | One of `paragraph`, `sentence`, `fixed`        |
| `DOKIMOS_CHUNK_SIZE`     | `500`       | Approximate words per chunk for fixed chunking |
| `DOKIMOS_CHUNK_OVERLAP`  | `50`        | Overlap between fixed chunks                   |

### Plagiarism settings

| Variable                                         | Default  | Description                                                            |
| ------------------------------------------------ | -------- | ---------------------------------------------------------------------- |
| `DOKIMOS_PLAGIARISM_BACKEND`                     | `hybrid` | One of `local`, `remote`, or `hybrid`                                  |
| `DOKIMOS_SHINGLE_SIZE`                           | `5`      | Number of words per shingle                                            |
| `DOKIMOS_PLAGIARISM_JACCARD_THRESHOLD`           | `0.10`   | Minimum Jaccard similarity to retain a candidate                       |
| `DOKIMOS_PLAGIARISM_FUZZ_THRESHOLD`              | `60.0`   | Minimum RapidFuzz score to keep a reranked match                       |
| `DOKIMOS_PLAGIARISM_REMOTE_QUERY_MAX_CHUNKS`     | `5`      | Maximum input chunks used as remote search queries                     |
| `DOKIMOS_PLAGIARISM_REMOTE_QUERY_MAX_CHARS`      | `180`    | Maximum characters sent in each remote query                           |
| `DOKIMOS_PLAGIARISM_REMOTE_PER_PROVIDER_RESULTS` | `3`      | Maximum candidate sources requested from each provider per query       |
| `DOKIMOS_PLAGIARISM_REMOTE_TIMEOUT_SECONDS`      | `10.0`   | Remote request timeout                                                 |
| `DOKIMOS_PLAGIARISM_REMOTE_MAX_SOURCE_CHARS`     | `20000`  | Maximum retained text size per fetched remote source                   |
| `DOKIMOS_PLAGIARISM_REMOTE_FETCH_FULL_TEXT`      | `true`   | Attempt to fetch source pages or PDFs instead of relying on metadata   |
| `DOKIMOS_PLAGIARISM_REMOTE_CONTACT_EMAIL`        | unset    | Optional contact email included where provider etiquette recommends it |
| `DOKIMOS_PLAGIARISM_REMOTE_ENABLE_OPENALEX`      | `true`   | Enable OpenAlex provider                                               |
| `DOKIMOS_PLAGIARISM_REMOTE_ENABLE_CROSSREF`      | `true`   | Enable Crossref provider                                               |
| `DOKIMOS_PLAGIARISM_REMOTE_ENABLE_ARXIV`         | `true`   | Enable arXiv provider                                                  |
| `DOKIMOS_PLAGIARISM_REMOTE_ENABLE_DUCKDUCKGO`    | `true`   | Enable DuckDuckGo HTML web-search provider                             |

### AI-likeness settings

| Variable                              | Default | Description                                                 |
| ------------------------------------- | ------- | ----------------------------------------------------------- |
| `DOKIMOS_AI_SHORT_SENTENCE_THRESHOLD` | `8`     | Sentences at or below this word count are considered short  |
| `DOKIMOS_AI_LONG_SENTENCE_THRESHOLD`  | `40`    | Sentences at or above this word count are considered long   |
| `DOKIMOS_AI_SIGNAL_TRIGGER_THRESHOLD` | `0.5`   | Per-signal threshold to mark a signal as triggered          |
| `DOKIMOS_AI_RISK_HIGH_THRESHOLD`      | `0.6`   | Aggregate score threshold for `high` risk                   |
| `DOKIMOS_AI_RISK_MEDIUM_THRESHOLD`    | `0.3`   | Aggregate score threshold for `medium` risk                 |
| `DOKIMOS_AI_SHORT_DOCUMENT_WORDS`     | `80`    | Documents below this size receive the short-document caveat |

Example:

```bash
export DOKIMOS_INDEX_FILE=/tmp/dokimos-index.json
export DOKIMOS_PLAGIARISM_BACKEND=remote
export DOKIMOS_PLAGIARISM_REMOTE_CONTACT_EMAIL=you@example.com
export DOKIMOS_CHUNK_STRATEGY=sentence
export DOKIMOS_AI_RISK_HIGH_THRESHOLD=0.75

dokimos analyze essay.txt --format json
```

## Typical Workflows

### Analyze a single paper against free remote sources

```bash
dokimos analyze submissions/paper-01.pdf --format json
```

### Combine remote discovery with a local course corpus

```bash
export DOKIMOS_INDEX_FILE=/tmp/course-a-index.json
dokimos index-sources ./course-a-corpus
dokimos analyze submissions/paper-01.pdf --format json
```

### Force remote-only analysis

```bash
export DOKIMOS_PLAGIARISM_BACKEND=remote
dokimos analyze essay.txt --format json
```

### Force local-only offline analysis

```bash
export DOKIMOS_PLAGIARISM_BACKEND=local
dokimos index-sources ./course-a-corpus
dokimos analyze essay.txt --format json
```

### Use sentence chunking for a short-form writing set

```bash
export DOKIMOS_CHUNK_STRATEGY=sentence
dokimos analyze essay.txt --format json
```

### Generate a saved report for later inspection

```bash
dokimos analyze essay.txt --json-out reports/essay.json
```

## Troubleshooting

### `dokimos: command not found`

Install or refresh the editable install:

```bash
pip install -e .
```

If you are intentionally running directly from source instead of installing:

```bash
PYTHONPATH=src python -m dokimos --help
```

### `No module named dokimos`

You are likely running from source without an install and without `PYTHONPATH=src`.

Use one of these:

```bash
pip install -e .
```

```bash
PYTHONPATH=src python -m dokimos --help
```

### PDF or DOCX files fail to open

Install the required extras:

```bash
pip install -e ".[pdf,docx]"
```

### Plagiarism always returns zero matches

Check the basics:

- make sure the machine has internet access if you are using `remote` or `hybrid`
- make sure the remote providers you want are enabled
- try increasing `DOKIMOS_PLAGIARISM_REMOTE_QUERY_MAX_CHARS` slightly for longer phrases
- if you want local matches too, make sure you indexed the source corpus first
- make sure `DOKIMOS_INDEX_FILE` points to the expected index when using `local` or `hybrid`
- remember that paywalled or inaccessible pages cannot be fetched by the free providers

### The output is not appearing on stdout

That is expected in text mode. Use:

```bash
dokimos analyze essay.txt --format json
```

or redirect stderr if you want the text summary captured.

## AI-Likeness Disclaimer

The AI-likeness score reflects the statistical likelihood of automated writing patterns.
It is based on stylometric heuristics and should not be treated as definitive evidence.

Current signals include:

- sentence length uniformity
- short sentence ratio
- long sentence ratio
- lexical diversity
- sentence start repetition
- average word length uniformity

Human review is recommended, especially for medium- and high-risk results.

## Development

```bash
# Run the full test suite
./.venv/bin/python -m pytest -q

# Run coverage manually if desired
./.venv/bin/python -m pytest tests/ -v --cov=dokimos

# Lint
./.venv/bin/ruff check src tests README.md

# Format
./.venv/bin/ruff format src tests
```

## Community

- Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request.
- Report bugs and request features through GitHub Issues.
- Review [SECURITY.md](SECURITY.md) for vulnerability reporting guidance.

## Project Layout

```text
src/dokimos/           implementation package
corpus/                default local corpus directory and index location
examples/              example input documents
tests/                 automated test suite
```
