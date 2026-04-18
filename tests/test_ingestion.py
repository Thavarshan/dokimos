"""Tests for document ingestion and chunking."""

from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest

from dokimos.exceptions import IngestionError
from dokimos.ingestion.chunker import get_chunks
from dokimos.ingestion.reader import read_document
from dokimos.schemas.documents import Document


def _verify_offsets(raw: str, chunks: list) -> None:
    """Assert every chunk's offsets reconstruct its text from the raw document."""
    for chunk in chunks:
        extracted = raw[chunk.start_offset : chunk.end_offset]
        assert extracted == chunk.text, (
            f"Chunk {chunk.index}: offset slice {chunk.start_offset}:{chunk.end_offset} "
            f"gives {extracted!r}, expected {chunk.text!r}"
        )


class TestReadDocument:
    def test_reads_valid_txt_file(self, sample_file: Path) -> None:
        doc = read_document(sample_file)
        assert isinstance(doc, Document)
        assert doc.source_path == sample_file.resolve()
        assert len(doc.raw_text) > 0
        assert doc.metadata["format"] == ".txt"

    def test_reads_md_file(self, tmp_path: Path) -> None:
        md = tmp_path / "readme.md"
        md.write_text("# Hello\n\nWorld", encoding="utf-8")
        doc = read_document(md)
        assert doc.metadata["format"] == ".md"
        assert "Hello" in doc.raw_text

    def test_raises_on_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(IngestionError, match="not a file"):
            read_document(tmp_path / "nonexistent.txt")

    def test_raises_on_directory(self, tmp_path: Path) -> None:
        with pytest.raises(IngestionError, match="not a file"):
            read_document(tmp_path)

    def test_raises_on_unsupported_format(self, tmp_path: Path) -> None:
        f = tmp_path / "data.csv"
        f.write_text("a,b,c", encoding="utf-8")
        with pytest.raises(IngestionError, match="Unsupported file format"):
            read_document(f)

    def test_reads_docx_file(self, sample_docx: Path) -> None:
        doc = read_document(sample_docx)
        assert doc.metadata["format"] == ".docx"
        assert "fox" in doc.raw_text

    def test_reads_pdf_file(self, sample_pdf: Path) -> None:
        doc = read_document(sample_pdf)
        assert doc.metadata["format"] == ".pdf"
        assert "fox" in doc.raw_text

    def test_docx_missing_dependency(self, tmp_path: Path) -> None:
        p = tmp_path / "test.docx"
        p.write_bytes(b"not a real docx")
        with mock.patch.dict("sys.modules", {"docx": None}), pytest.raises(
            IngestionError, match="python-docx is required"
        ):
            read_document(p)

    def test_pdf_missing_dependency(self, tmp_path: Path) -> None:
        p = tmp_path / "test.pdf"
        p.write_bytes(b"not a real pdf")
        with mock.patch.dict("sys.modules", {"pymupdf": None}), pytest.raises(
            IngestionError, match="pymupdf is required"
        ):
            read_document(p)

    def test_docx_corrupt_file(self, tmp_path: Path) -> None:
        p = tmp_path / "corrupt.docx"
        p.write_bytes(b"this is not a valid docx file")
        with pytest.raises(IngestionError, match="Failed to read DOCX"):
            read_document(p)

    def test_pdf_corrupt_file(self, tmp_path: Path) -> None:
        p = tmp_path / "corrupt.pdf"
        p.write_bytes(b"this is not a valid pdf file")
        with pytest.raises(IngestionError, match="Failed to read PDF"):
            read_document(p)


class TestChunkDocument:
    def test_produces_at_least_one_chunk(self, sample_document: Document) -> None:
        chunks = get_chunks(sample_document, strategy="fixed", chunk_size=100, overlap=10)
        assert len(chunks) >= 1

    def test_chunks_have_correct_document_id(self, sample_document: Document) -> None:
        chunks = get_chunks(sample_document, strategy="fixed", chunk_size=100, overlap=10)
        for chunk in chunks:
            assert chunk.document_id == sample_document.id

    def test_empty_document_returns_no_chunks(self, sample_file: Path) -> None:
        doc = Document(source_path=sample_file, raw_text="", metadata={})
        chunks = get_chunks(doc, strategy="fixed")
        assert chunks == []

    def test_chunk_indices_are_sequential(self, sample_document: Document) -> None:
        chunks = get_chunks(sample_document, strategy="fixed", chunk_size=5, overlap=1)
        for i, chunk in enumerate(chunks):
            assert chunk.index == i


class TestGetChunks:
    def test_paragraph_strategy(self, tmp_path: Path, multi_paragraph_text: str) -> None:
        f = tmp_path / "para.txt"
        f.write_text(multi_paragraph_text, encoding="utf-8")
        doc = Document(source_path=f, raw_text=multi_paragraph_text, metadata={})
        chunks = get_chunks(doc, strategy="paragraph")
        assert len(chunks) == 3
        assert "First paragraph" in chunks[0].text
        assert "Third paragraph" in chunks[2].text

    def test_sentence_strategy(self, tmp_path: Path, multi_sentence_text: str) -> None:
        f = tmp_path / "sent.txt"
        f.write_text(multi_sentence_text, encoding="utf-8")
        doc = Document(source_path=f, raw_text=multi_sentence_text, metadata={})
        chunks = get_chunks(doc, strategy="sentence")
        assert len(chunks) == 3
        assert chunks[0].text.endswith("dog.")
        assert chunks[2].text.endswith("jump.")

    def test_fixed_strategy(self, sample_document: Document) -> None:
        chunks = get_chunks(sample_document, strategy="fixed", chunk_size=5, overlap=1)
        assert len(chunks) >= 1
        for i, chunk in enumerate(chunks):
            assert chunk.index == i

    def test_stable_ids(self, sample_document: Document) -> None:
        chunks_a = get_chunks(sample_document, strategy="paragraph")
        chunks_b = get_chunks(sample_document, strategy="paragraph")
        for a, b in zip(chunks_a, chunks_b, strict=True):
            assert a.id == b.id

    def test_empty_text(self, sample_file: Path) -> None:
        doc = Document(source_path=sample_file, raw_text="   ", metadata={})
        assert get_chunks(doc, strategy="paragraph") == []


class TestParagraphOffsetTracking:
    """Regression tests: paragraph offsets must be exact even with repeated text."""

    def test_repeated_paragraphs(self, sample_file: Path) -> None:
        raw = "Hello world.\n\nHello world.\n\nGoodbye."
        doc = Document(source_path=sample_file, raw_text=raw, metadata={})
        chunks = get_chunks(doc, strategy="paragraph")
        assert len(chunks) == 3
        _verify_offsets(raw, chunks)
        # The two "Hello world." chunks must have different offsets
        assert chunks[0].start_offset != chunks[1].start_offset

    def test_three_identical_paragraphs(self, sample_file: Path) -> None:
        raw = "Same text.\n\nSame text.\n\nSame text."
        doc = Document(source_path=sample_file, raw_text=raw, metadata={})
        chunks = get_chunks(doc, strategy="paragraph")
        assert len(chunks) == 3
        _verify_offsets(raw, chunks)
        offsets = [(c.start_offset, c.end_offset) for c in chunks]
        assert len(set(offsets)) == 3  # all unique

    def test_paragraph_with_leading_whitespace(self, sample_file: Path) -> None:
        raw = "  Alpha.\n\n  Beta."
        doc = Document(source_path=sample_file, raw_text=raw, metadata={})
        chunks = get_chunks(doc, strategy="paragraph")
        _verify_offsets(raw, chunks)
        assert chunks[0].text == "Alpha."
        assert chunks[1].text == "Beta."


class TestSentenceOffsetTracking:
    """Regression tests: sentence offsets must be exact even with repeated text."""

    def test_repeated_sentences(self, sample_file: Path) -> None:
        raw = "Hello world. Hello world. Goodbye."
        doc = Document(source_path=sample_file, raw_text=raw, metadata={})
        chunks = get_chunks(doc, strategy="sentence")
        assert len(chunks) == 3
        _verify_offsets(raw, chunks)
        assert chunks[0].start_offset != chunks[1].start_offset

    def test_three_identical_sentences(self, sample_file: Path) -> None:
        raw = "Same. Same. Same."
        doc = Document(source_path=sample_file, raw_text=raw, metadata={})
        chunks = get_chunks(doc, strategy="sentence")
        assert len(chunks) == 3
        _verify_offsets(raw, chunks)


class TestFixedOffsetTracking:
    """Regression tests: fixed-strategy offsets must be exact."""

    def test_repeated_words(self, sample_file: Path) -> None:
        raw = "the the the the the the the the"
        doc = Document(source_path=sample_file, raw_text=raw, metadata={})
        chunks = get_chunks(doc, strategy="fixed", chunk_size=3, overlap=0)
        _verify_offsets(raw, chunks)

    def test_fixed_preserves_internal_whitespace(self, sample_file: Path) -> None:
        raw = "word1  word2\tword3  word4  word5"
        doc = Document(source_path=sample_file, raw_text=raw, metadata={})
        chunks = get_chunks(doc, strategy="fixed", chunk_size=3, overlap=0)
        _verify_offsets(raw, chunks)
        # First chunk should preserve the double-space and tab from the raw text
        assert chunks[0].text == "word1  word2\tword3"


class TestSentenceAbbreviations:
    """Abbreviations should not cause sentence splits."""

    def test_dr_mr_mrs_not_split(self, sample_file: Path) -> None:
        raw = "Dr. Smith met Mr. Jones and Mrs. Brown at the clinic."
        doc = Document(source_path=sample_file, raw_text=raw, metadata={})
        chunks = get_chunks(doc, strategy="sentence")
        assert len(chunks) == 1
        assert chunks[0].text == raw

    def test_us_abbreviation(self, sample_file: Path) -> None:
        raw = "The U.S. government held a meeting. It was productive."
        doc = Document(source_path=sample_file, raw_text=raw, metadata={})
        chunks = get_chunks(doc, strategy="sentence")
        assert len(chunks) == 2
        assert "U.S. government" in chunks[0].text

    def test_eg_ie_abbreviation(self, sample_file: Path) -> None:
        raw = "Use punctuation, e.g. commas. Also use i.e. for clarification."
        doc = Document(source_path=sample_file, raw_text=raw, metadata={})
        chunks = get_chunks(doc, strategy="sentence")
        assert len(chunks) == 2
        assert "e.g. commas" in chunks[0].text
        assert "i.e. for" in chunks[1].text

    def test_initial_not_split(self, sample_file: Path) -> None:
        raw = "J. K. Rowling wrote Harry Potter. It became very popular."
        doc = Document(source_path=sample_file, raw_text=raw, metadata={})
        chunks = get_chunks(doc, strategy="sentence")
        assert len(chunks) == 2
        assert "J. K. Rowling" in chunks[0].text

    def test_real_sentence_end_still_splits(self, sample_file: Path) -> None:
        raw = "This is the end. This is the beginning."
        doc = Document(source_path=sample_file, raw_text=raw, metadata={})
        chunks = get_chunks(doc, strategy="sentence")
        assert len(chunks) == 2
