"""Tests for CLI commands via Typer's CliRunner."""

from __future__ import annotations

import importlib
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


class TestCliIdentity:
    def test_public_cli_name_is_dokimos(self) -> None:
        assert app.info.name == "dokimos"

    def test_dokimos_module_alias_exposes_version(self) -> None:
        module = importlib.import_module("dokimos")
        assert module.__version__


class TestAnalyzeCommand:
    def test_analyze_json_format(self, sample_file: Path) -> None:
        result = runner.invoke(app, ["analyze", str(sample_file), "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert "document_id" in data
        assert "plagiarism" in data
        assert "ai_likelihood" in data
        assert "version" in data
        assert "summary" in data
        assert "document" in data

    def test_analyze_text_format(self, sample_file: Path) -> None:
        result = runner.invoke(app, ["analyze", str(sample_file)])
        assert result.exit_code == 0
        # Text mode writes to stderr via console; stdout should be empty
        assert "document_id" not in result.stdout

    def test_analyze_json_out(self, sample_file: Path, tmp_path: Path) -> None:
        out = tmp_path / "report.json"
        result = runner.invoke(app, ["analyze", str(sample_file), "--json-out", str(out)])
        assert result.exit_code == 0
        assert out.exists()
        data = json.loads(out.read_text())
        assert "document_id" in data

    def test_analyze_missing_file(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["analyze", str(tmp_path / "nope.txt")])
        assert result.exit_code == 1


class TestPlagiarismCommand:
    def test_plagiarism_json(self, sample_file: Path) -> None:
        result = runner.invoke(
            app, ["plagiarism", str(sample_file), "--format", "json"]
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["plagiarism"] is not None
        assert data["ai_likelihood"] is None

    def test_plagiarism_text(self, sample_file: Path) -> None:
        result = runner.invoke(app, ["plagiarism", str(sample_file)])
        assert result.exit_code == 0


class TestAiCheckCommand:
    def test_ai_check_json(self, sample_file: Path) -> None:
        result = runner.invoke(
            app, ["ai-check", str(sample_file), "--format", "json"]
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["ai_likelihood"] is not None
        assert data["plagiarism"] is None
        assert len(data["ai_likelihood"]["indicators"]) == 6

    def test_ai_check_has_caveats(self, sample_file: Path) -> None:
        result = runner.invoke(
            app, ["ai-check", str(sample_file), "--format", "json"]
        )
        data = json.loads(result.stdout)
        assert len(data["ai_likelihood"]["caveats"]) > 0

    def test_ai_check_text(self, sample_file: Path) -> None:
        result = runner.invoke(app, ["ai-check", str(sample_file)])
        assert result.exit_code == 0

    def test_ai_check_text_renders_each_caveat_once(self, sample_file: Path) -> None:
        result = runner.invoke(app, ["ai-check", str(sample_file)])
        assert result.exit_code == 0
        assert result.output.count("Stylometric heuristics only") == 1
        assert result.output.count("Short documents produce less reliable signals") == 1


class TestIndexSourcesCommand:
    def test_index_sources_directory(self, corpus_dir: Path) -> None:
        result = runner.invoke(app, ["index-sources", str(corpus_dir)])
        assert result.exit_code == 0
        assert "Scanned 2 file(s) (recursive)" in result.output
        assert "Indexed: 2" in result.output

    def test_index_sources_missing_dir(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["index-sources", str(tmp_path / "nope")])
        assert result.exit_code == 1

    def test_index_sources_no_recursive(self, tmp_path: Path) -> None:
        """--no-recursive should skip files in subdirectories."""
        root = tmp_path / "corpus_root"
        root.mkdir()
        (root / "top.txt").write_text("Top-level file.", encoding="utf-8")
        sub = root / "sub"
        sub.mkdir()
        (sub / "nested.txt").write_text("Nested file.", encoding="utf-8")

        result = runner.invoke(app, ["index-sources", str(root), "--no-recursive"])
        assert result.exit_code == 0
        assert "Scanned 1 file(s) (top-level)" in result.output
        assert "Indexed: 1" in result.output

    def test_index_sources_recursive_default(self, tmp_path: Path) -> None:
        """Default (recursive) should find files in subdirectories."""
        root = tmp_path / "corpus_root"
        root.mkdir()
        (root / "top.txt").write_text("Top-level file.", encoding="utf-8")
        sub = root / "sub"
        sub.mkdir()
        (sub / "nested.txt").write_text("Nested file.", encoding="utf-8")

        result = runner.invoke(app, ["index-sources", str(root)])
        assert result.exit_code == 0
        assert "Scanned 2 file(s) (recursive)" in result.output
        assert "Indexed: 2" in result.output


class TestFormatValidation:
    def test_invalid_format_rejected(self, sample_file: Path) -> None:
        result = runner.invoke(app, ["analyze", str(sample_file), "--format", "xml"])
        assert result.exit_code != 0

    def test_json_format_accepted(self, sample_file: Path) -> None:
        result = runner.invoke(app, ["analyze", str(sample_file), "--format", "json"])
        assert result.exit_code == 0

    def test_text_format_accepted(self, sample_file: Path) -> None:
        result = runner.invoke(app, ["analyze", str(sample_file), "--format", "text"])
        assert result.exit_code == 0
