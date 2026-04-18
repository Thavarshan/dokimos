"""Report serialisation and output utilities."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from dokimos.schemas.results import AnalysisReport

logger = logging.getLogger(__name__)


def report_to_dict(report: AnalysisReport) -> dict[str, Any]:
    """Serialise an :class:`AnalysisReport` to a JSON-compatible dict."""
    return report.model_dump(mode="json")


def report_to_json(report: AnalysisReport) -> str:
    """Serialise an :class:`AnalysisReport` to a JSON string."""
    return json.dumps(report_to_dict(report), indent=2, ensure_ascii=False)


def report_to_text(report: AnalysisReport) -> str:
    """Render a human-readable text summary of a report."""
    lines: list[str] = []
    rendered_caveats: set[tuple[str, str]] = set()

    def _render_caveat(prefix: str, code: str, message: str) -> None:
        lines.append(f"{prefix}[{code}] {message}")
        rendered_caveats.add((code, message))

    lines.append(f"Document: {report.document.source_path}")
    lines.append(f"Status:   {report.status}")
    lines.append(
        "Summary:  "
        f"analyses={', '.join(report.summary.analyses_run) or 'none'} "
        f"plagiarism={report.summary.plagiarism_overall_score:.2f} "
        f"ai={report.summary.ai_likeness_score:.2f}"
    )

    if report.plagiarism is not None:
        p = report.plagiarism
        lines.append("")
        lines.append(f"Plagiarism — overall score: {p.overall_score:.2f}")
        if p.matches:
            lines.append(f"  {len(p.matches)} match(es):")
            for m in p.matches[:10]:
                lines.append(
                    f"    [{m.match_type}] score={m.similarity_score:.2f}"
                    f"  source={m.source.source_label}  chunk#{m.source.chunk_index}"
                )
            if len(p.matches) > 10:
                lines.append(f"    ... and {len(p.matches) - 10} more")
        else:
            lines.append("  No matches found.")

    if report.ai_likelihood is not None:
        a = report.ai_likelihood
        lines.append("")
        lines.append(
            "AI-likeness — "
            f"score: {a.ai_likeness_score:.2f}  risk: {a.automated_writing_risk}"
        )
        for ind in a.indicators:
            lines.append(f"  {ind.signal_name}: {ind.value:.2f}")
        if a.caveats:
            lines.append("  Caveats:")
            for c in a.caveats:
                _render_caveat("    - ", c.code, c.message)
        lines.append(f"  Disclaimer: {a.disclaimer}")

    if report.caveats:
        report_only = [c for c in report.caveats if (c.code, c.message) not in rendered_caveats]
    else:
        report_only = []

    if report_only:
        lines.append("")
        lines.append("Report caveats:")
        for c in report_only:
            _render_caveat("  - ", c.code, c.message)

    return "\n".join(lines)


def write_json_report(report: AnalysisReport, output_path: Path) -> None:
    """Write an :class:`AnalysisReport` to a JSON file.

    Creates parent directories if they do not exist.
    """
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report_to_json(report), encoding="utf-8")
    logger.info("Report written to %s", output_path)
