# Troubleshooting

## dokimos: command not found

Refresh the editable install:

```bash
pip install -e .
```

If you are intentionally running directly from source instead of installing:

```bash
PYTHONPATH=src python -m dokimos --help
```

## No module named dokimos

You are likely running from source without an install and without `PYTHONPATH=src`.

Use one of these:

```bash
pip install -e .
```

```bash
PYTHONPATH=src python -m dokimos --help
```

## PDF or DOCX files fail to open

Install the required extras:

```bash
pip install -e ".[pdf,docx]"
```

## Plagiarism returns zero matches

Check the basics:

- make sure the machine has internet access if you are using `remote` or `hybrid`
- make sure the remote providers you want are enabled
- try increasing `DOKIMOS_PLAGIARISM_REMOTE_QUERY_MAX_CHARS` slightly for longer phrases
- if you want local matches too, make sure you indexed the source corpus first
- make sure `DOKIMOS_INDEX_FILE` points to the expected index when using `local` or `hybrid`
- remember that paywalled or inaccessible pages cannot be fetched by the free providers

## Output is not appearing on stdout

That is expected in text mode.

- `--format text` writes the human-readable summary to stderr
- `--format json` writes structured JSON to stdout

If you are scripting, use:

```bash
dokimos analyze essay.txt --format json
```

## AI-likeness score seems surprising

Remember the score is heuristic, not proof of authorship.

Common reasons for surprising results:

- very short documents produce weaker signals
- domain-specific or highly repetitive human writing can look stylometrically unusual
- mixed human and AI-assisted text can sit between the obvious extremes

Inspect the JSON output when you need more detail about individual indicators and caveats.
