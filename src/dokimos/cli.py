"""Typer CLI application — thin command layer.

All business logic lives in :mod:`dokimos.pipeline` and the engine modules.
This module is responsible only for argument parsing, wiring, and output.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated, Literal

import typer
from rich.console import Console

from dokimos.config import get_settings
from dokimos.engines.base import PlagiarismEngine
from dokimos.engines.local_indexer import LocalSourceIndexer
from dokimos.engines.remote_plagiarism import HybridPlagiarismEngine, RemotePlagiarismEngine
from dokimos.engines.shingling_plagiarism import ShinglingPlagiarismEngine
from dokimos.engines.stylometric_ai import StylometricAiEngine
from dokimos.exceptions import CheckerError
from dokimos.logging import setup_logging
from dokimos.pipeline import AnalysisPipeline
from dokimos.reporting import report_to_json, report_to_text, write_json_report
from dokimos.schemas.requests import AnalyzeRequest
from dokimos.schemas.results import AnalysisReport

app = typer.Typer(
    name="dokimos",
    help="CLI engine for plagiarism checking and AI-writing-risk analysis.",
    no_args_is_help=True,
)
console = Console(stderr=True)

# Shared option types --------------------------------------------------------

_FormatOption = Annotated[
    Literal["json", "text"],
    typer.Option(
        "--format",
        help="Output format: 'json' for machine-readable JSON, 'text' for human summary.",
    ),
]

_JsonOutOption = Annotated[
    Path | None,
    typer.Option("--json-out", help="Write JSON report to this file instead of stdout."),
]


# Helpers --------------------------------------------------------------------


def _build_pipeline() -> AnalysisPipeline:
    """Construct the analysis pipeline with real engines."""
    settings = get_settings()
    plagiarism_engine: PlagiarismEngine
    if settings.plagiarism_backend == "remote":
        plagiarism_engine = RemotePlagiarismEngine(settings=settings)
    elif settings.plagiarism_backend == "hybrid":
        plagiarism_engine = HybridPlagiarismEngine(
            remote_engine=RemotePlagiarismEngine(settings=settings),
            local_engine=ShinglingPlagiarismEngine(settings=settings),
        )
    else:
        plagiarism_engine = ShinglingPlagiarismEngine(settings=settings)

    return AnalysisPipeline(
        plagiarism_engine=plagiarism_engine,
        ai_engine=StylometricAiEngine(settings=settings),
        settings=settings,
    )


def _emit_report(
    report: AnalysisReport,
    fmt: str,
    json_out: Path | None,
) -> None:
    """Output *report* according to the requested format.

    - ``json_out`` always writes JSON to the given path (regardless of *fmt*).
    - ``--format json`` writes strict JSON to stdout.
    - ``--format text`` writes a human summary to stderr only.
    """
    if json_out is not None:
        write_json_report(report, json_out)
        console.print(f"Report written to {json_out}")
        return

    if fmt == "json":
        sys.stdout.write(report_to_json(report) + "\n")
    else:
        console.print(report_to_text(report))


# Commands -------------------------------------------------------------------


@app.callback()
def _main_callback(
    log_level: Annotated[
        str,
        typer.Option("--log-level", help="Set log level (DEBUG, INFO, WARNING, ERROR)."),
    ] = "INFO",
) -> None:
    """Global options applied before any sub-command."""
    setup_logging(log_level)


@app.command()
def analyze(
    file_path: Annotated[Path, typer.Argument(help="Path to the document to analyse.")],
    fmt: _FormatOption = "text",
    json_out: _JsonOutOption = None,
    no_plagiarism: Annotated[
        bool,
        typer.Option("--no-plagiarism", help="Skip plagiarism analysis."),
    ] = False,
    no_ai_check: Annotated[
        bool,
        typer.Option("--no-ai-check", help="Skip AI-likeness analysis."),
    ] = False,
) -> None:
    """Run full analysis (plagiarism + AI-likeness) on a document."""
    try:
        request = AnalyzeRequest(
            file_path=file_path,
            run_plagiarism=not no_plagiarism,
            run_ai_check=not no_ai_check,
        )
        pipeline = _build_pipeline()
        report = pipeline.run(request)
        _emit_report(report, fmt, json_out)

    except CheckerError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc


@app.command()
def plagiarism(
    file_path: Annotated[Path, typer.Argument(help="Path to the document to analyse.")],
    fmt: _FormatOption = "text",
    json_out: _JsonOutOption = None,
) -> None:
    """Run plagiarism-only analysis on a document."""
    try:
        request = AnalyzeRequest(
            file_path=file_path,
            run_plagiarism=True,
            run_ai_check=False,
        )
        pipeline = _build_pipeline()
        report = pipeline.run(request)
        _emit_report(report, fmt, json_out)

    except CheckerError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc


@app.command(name="ai-check")
def ai_check(
    file_path: Annotated[Path, typer.Argument(help="Path to the document to analyse.")],
    fmt: _FormatOption = "text",
    json_out: _JsonOutOption = None,
) -> None:
    """Run AI-likeness / automated-writing-risk analysis on a document."""
    try:
        request = AnalyzeRequest(
            file_path=file_path,
            run_plagiarism=False,
            run_ai_check=True,
        )
        pipeline = _build_pipeline()
        report = pipeline.run(request)
        _emit_report(report, fmt, json_out)

    except CheckerError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc


@app.command(name="index-sources")
def index_sources(
    directory_path: Annotated[
        Path, typer.Argument(help="Directory of source documents to index.")
    ],
    recursive: Annotated[
        bool,
        typer.Option("--recursive/--no-recursive", help="Recurse into subdirectories."),
    ] = True,
) -> None:
    """Index a directory of source documents into the internal corpus."""
    try:
        resolved = directory_path.resolve()
        if not resolved.is_dir():
            console.print(f"[red]Error:[/red] Not a directory: {resolved}")
            raise typer.Exit(code=1)

        indexer = LocalSourceIndexer(settings=get_settings())
        count = indexer.index(resolved, recursive=recursive)

        stats = indexer.last_stats
        if stats is not None:
            mode = "recursive" if stats.recursive else "top-level"
            console.print(f"Scanned {stats.total_files} file(s) ({mode})")
            console.print(f"  Indexed: {stats.indexed}")
            console.print(f"  Skipped: {stats.skipped}")
            console.print(f"  Up-to-date: {stats.up_to_date}")
            console.print(f"  Index: {stats.index_path}")
        else:
            console.print(f"Indexed {count} document(s) from {resolved}")

    except CheckerError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc
