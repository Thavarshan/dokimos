# CLI Reference

Top-level help:

```bash
dokimos --help
```

## Global Options

- `--log-level TEXT`: set log level such as `DEBUG`, `INFO`, `WARNING`, or `ERROR`
- `--install-completion`: install shell completion
- `--show-completion`: print completion for the current shell
- `--help`: show help and exit

## Commands

- `analyze`
- `plagiarism`
- `ai-check`
- `index-sources`

## analyze

Runs both Plagiarism Detection and AI-Likeness Scoring unless one is explicitly disabled.

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

## plagiarism

Runs Plagiarism Detection only.

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

## ai-check

Runs AI-Likeness Scoring only.

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

## index-sources

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

### Text Output

`--format text` is the default. It prints a human-readable summary using Rich.

Important behavior:

- Text output is written to stderr, not stdout.
- This is useful for interactive terminal use.
- If you are scripting, prefer `--format json`.

### JSON Output

`--format json` prints strict JSON to stdout.

This is the best choice for:

- shell pipelines
- CI jobs
- API handoff
- storing analysis artifacts

### json-out

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
