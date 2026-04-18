# Configuration

All settings can be overridden with `DOKIMOS_`-prefixed environment variables.

## Core Settings

| Variable              | Default             | Description                                   |
| --------------------- | ------------------- | --------------------------------------------- |
| `DOKIMOS_LOG_LEVEL`   | `INFO`              | Default application log level                 |
| `DOKIMOS_CORPUS_PATH` | `corpus`            | Directory used for the internal source corpus |
| `DOKIMOS_INDEX_FILE`  | `corpus/index.json` | JSON index file path                          |
| `DOKIMOS_OUTPUT_DIR`  | `output`            | Default output directory for reports          |

## Chunking Settings

| Variable                 | Default     | Description                                    |
| ------------------------ | ----------- | ---------------------------------------------- |
| `DOKIMOS_CHUNK_STRATEGY` | `paragraph` | One of `paragraph`, `sentence`, `fixed`        |
| `DOKIMOS_CHUNK_SIZE`     | `500`       | Approximate words per chunk for fixed chunking |
| `DOKIMOS_CHUNK_OVERLAP`  | `50`        | Overlap between fixed chunks                   |

## Plagiarism Settings

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

## AI-Likeness Settings

| Variable                              | Default | Description                                                 |
| ------------------------------------- | ------- | ----------------------------------------------------------- |
| `DOKIMOS_AI_SHORT_SENTENCE_THRESHOLD` | `8`     | Sentences at or below this word count are considered short  |
| `DOKIMOS_AI_LONG_SENTENCE_THRESHOLD`  | `40`    | Sentences at or above this word count are considered long   |
| `DOKIMOS_AI_SIGNAL_TRIGGER_THRESHOLD` | `0.5`   | Per-signal threshold to mark a signal as triggered          |
| `DOKIMOS_AI_RISK_HIGH_THRESHOLD`      | `0.6`   | Aggregate score threshold for `high` risk                   |
| `DOKIMOS_AI_RISK_MEDIUM_THRESHOLD`    | `0.3`   | Aggregate score threshold for `medium` risk                 |
| `DOKIMOS_AI_SHORT_DOCUMENT_WORDS`     | `80`    | Documents below this size receive the short-document caveat |

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
