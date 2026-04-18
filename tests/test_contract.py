"""Golden-file style tests that freeze the JSON report contract.

These tests validate the deterministic key structure of every report
variant so that downstream consumers (e.g. the Laravel backend) can
rely on a stable schema without surprises.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

import dokimos.cli as cli_module
from dokimos.cli import app
from dokimos.config import Settings

runner = CliRunner()


@pytest.fixture(autouse=True)
def _isolate_cli_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    settings = Settings(
        plagiarism_backend="local",
        corpus_path=tmp_path / "corpus",
        index_file=tmp_path / "index.json",
    )
    monkeypatch.setattr(cli_module, "get_settings", lambda: settings)

# -- expected key sets -------------------------------------------------------

_REPORT_TOP_KEYS = {
    "schema_version",
    "document_id",
    "version",
    "status",
    "plagiarism",
    "ai_likelihood",
    "generated_at",
    "document",
    "summary",
    "caveats",
}

_DOCUMENT_METADATA_KEYS = {
    "source_path",
    "filename",
    "file_format",
    "character_count",
}

_SUMMARY_KEYS = {
    "analyses_run",
    "plagiarism_match_count",
    "plagiarism_overall_score",
    "ai_likeness_score",
    "automated_writing_risk",
    "human_review_recommended",
}

_PLAGIARISM_RESULT_KEYS = {
    "document_id",
    "matches",
    "overall_score",
    "match_count",
}

_PLAGIARISM_MATCH_KEYS = {
    "finding_id",
    "source",
    "similarity_score",
    "matched_excerpt",
    "source_excerpt",
    "match_type",
    "offsets",
}

_SOURCE_METADATA_KEYS = {
    "source_id",
    "source_label",
    "source_path",
    "chunk_index",
    "modified_at",
}

_OFFSET_SPAN_KEYS = {
    "start",
    "end",
    "unit",
    "basis",
    "end_exclusive",
}

_AI_RESULT_KEYS = {
    "document_id",
    "indicators",
    "chunk_findings",
    "ai_likeness_score",
    "automated_writing_risk",
    "signals_triggered",
    "human_review_recommended",
    "disclaimer",
    "caveats",
}

_AI_INDICATOR_KEYS = {
    "signal_name",
    "value",
    "description",
    "triggered",
}

_AI_CHUNK_FINDING_KEYS = {
    "finding_id",
    "chunk_index",
    "ai_likeness_score",
    "signals",
    "signals_triggered",
    "explanation",
}

_CAVEAT_KEYS = {
    "code",
    "message",
    "severity",
    "scope",
}

_EXPECTED_INDICATOR_NAMES = {
    "sentence_length_uniformity",
    "short_sentence_ratio",
    "long_sentence_ratio",
    "lexical_diversity",
    "sentence_start_repetition",
    "avg_word_length_uniformity",
}


# -- helpers -----------------------------------------------------------------


def _parse_json_output(args: list[str]) -> dict:
    """Invoke a CLI command with --format json and return parsed output."""
    result = runner.invoke(app, args)
    assert result.exit_code == 0, f"CLI failed: {result.output}"
    return json.loads(result.stdout)


# -- contract tests ----------------------------------------------------------


class TestAnalyzeContract:
    """Validate the full analyze report JSON structure."""

    def test_top_level_keys(self, sample_file: Path) -> None:
        data = _parse_json_output(["analyze", str(sample_file), "--format", "json"])
        assert set(data.keys()) == _REPORT_TOP_KEYS

    def test_plagiarism_section_keys(self, sample_file: Path) -> None:
        data = _parse_json_output(["analyze", str(sample_file), "--format", "json"])
        assert data["plagiarism"] is not None
        assert set(data["plagiarism"].keys()) == _PLAGIARISM_RESULT_KEYS

    def test_ai_section_keys(self, sample_file: Path) -> None:
        data = _parse_json_output(["analyze", str(sample_file), "--format", "json"])
        ai = data["ai_likelihood"]
        assert ai is not None
        assert set(ai.keys()) == _AI_RESULT_KEYS

    def test_ai_indicator_keys(self, sample_file: Path) -> None:
        data = _parse_json_output(["analyze", str(sample_file), "--format", "json"])
        for ind in data["ai_likelihood"]["indicators"]:
            assert set(ind.keys()) == _AI_INDICATOR_KEYS

    def test_ai_indicator_names(self, sample_file: Path) -> None:
        data = _parse_json_output(["analyze", str(sample_file), "--format", "json"])
        names = {ind["signal_name"] for ind in data["ai_likelihood"]["indicators"]}
        assert names == _EXPECTED_INDICATOR_NAMES

    def test_ai_chunk_finding_keys(self, sample_file: Path) -> None:
        data = _parse_json_output(["analyze", str(sample_file), "--format", "json"])
        for cf in data["ai_likelihood"]["chunk_findings"]:
            assert set(cf.keys()) == _AI_CHUNK_FINDING_KEYS

    def test_document_metadata_keys(self, sample_file: Path) -> None:
        data = _parse_json_output(["analyze", str(sample_file), "--format", "json"])
        assert set(data["document"].keys()) == _DOCUMENT_METADATA_KEYS

    def test_summary_keys(self, sample_file: Path) -> None:
        data = _parse_json_output(["analyze", str(sample_file), "--format", "json"])
        assert set(data["summary"].keys()) == _SUMMARY_KEYS

    def test_value_types(self, sample_file: Path) -> None:
        data = _parse_json_output(["analyze", str(sample_file), "--format", "json"])
        assert isinstance(data["document_id"], str)
        assert isinstance(data["version"], str)
        assert isinstance(data["schema_version"], str)
        assert data["status"] in ("complete", "partial", "error")
        assert isinstance(data["generated_at"], str)
        assert isinstance(data["document"], dict)
        assert isinstance(data["summary"], dict)
        assert isinstance(data["caveats"], list)

    def test_plagiarism_value_types(self, sample_file: Path) -> None:
        data = _parse_json_output(["analyze", str(sample_file), "--format", "json"])
        p = data["plagiarism"]
        assert isinstance(p["document_id"], str)
        assert isinstance(p["matches"], list)
        assert isinstance(p["overall_score"], (int, float))
        assert 0.0 <= p["overall_score"] <= 1.0

    def test_ai_value_types(self, sample_file: Path) -> None:
        data = _parse_json_output(["analyze", str(sample_file), "--format", "json"])
        ai = data["ai_likelihood"]
        assert isinstance(ai["document_id"], str)
        assert isinstance(ai["indicators"], list)
        assert isinstance(ai["chunk_findings"], list)
        assert isinstance(ai["ai_likeness_score"], (int, float))
        assert 0.0 <= ai["ai_likeness_score"] <= 1.0
        assert ai["automated_writing_risk"] in ("low", "medium", "high")
        assert isinstance(ai["signals_triggered"], list)
        assert isinstance(ai["human_review_recommended"], bool)
        assert isinstance(ai["disclaimer"], str)
        assert len(ai["disclaimer"]) > 0
        assert isinstance(ai["caveats"], list)
        for c in ai["caveats"]:
            assert set(c.keys()) == _CAVEAT_KEYS


class TestPlagiarismContract:
    """Validate plagiarism-only report structure."""

    def test_top_level_keys(self, sample_file: Path) -> None:
        data = _parse_json_output(
            ["plagiarism", str(sample_file), "--format", "json"]
        )
        assert set(data.keys()) == _REPORT_TOP_KEYS

    def test_ai_is_null(self, sample_file: Path) -> None:
        data = _parse_json_output(
            ["plagiarism", str(sample_file), "--format", "json"]
        )
        assert data["ai_likelihood"] is None

    def test_plagiarism_present(self, sample_file: Path) -> None:
        data = _parse_json_output(
            ["plagiarism", str(sample_file), "--format", "json"]
        )
        assert data["plagiarism"] is not None
        assert set(data["plagiarism"].keys()) == _PLAGIARISM_RESULT_KEYS


class TestAiCheckContract:
    """Validate ai-check-only report structure."""

    def test_top_level_keys(self, sample_file: Path) -> None:
        data = _parse_json_output(
            ["ai-check", str(sample_file), "--format", "json"]
        )
        assert set(data.keys()) == _REPORT_TOP_KEYS

    def test_plagiarism_is_null(self, sample_file: Path) -> None:
        data = _parse_json_output(
            ["ai-check", str(sample_file), "--format", "json"]
        )
        assert data["plagiarism"] is None

    def test_ai_present(self, sample_file: Path) -> None:
        data = _parse_json_output(
            ["ai-check", str(sample_file), "--format", "json"]
        )
        ai = data["ai_likelihood"]
        assert ai is not None
        assert set(ai.keys()) == _AI_RESULT_KEYS
        assert len(ai["indicators"]) == 6


class TestJsonOutContract:
    """Validate --json-out produces the same structure as --format json."""

    def test_json_out_matches_format_json(
        self, sample_file: Path, tmp_path: Path
    ) -> None:
        out = tmp_path / "report.json"
        result = runner.invoke(
            app,
            ["analyze", str(sample_file), "--json-out", str(out)],
        )
        assert result.exit_code == 0
        data = json.loads(out.read_text())
        assert set(data.keys()) == _REPORT_TOP_KEYS
