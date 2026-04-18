"""Pydantic models for incoming requests / commands."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel


class AnalyzeRequest(BaseModel):
    """Parameters for a document analysis run."""

    file_path: Path
    run_plagiarism: bool = True
    run_ai_check: bool = True
