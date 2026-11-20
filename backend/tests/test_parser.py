"""Unit tests for document parsing (PDF, DOCX, text) and error handling."""

from pathlib import Path

import pytest

from app.services.parser import (
    EmptyDocumentError,
    parse_document,
    parse_docx,
    parse_pdf,
)

SAMPLE_DIR = Path(__file__).resolve().parent.parent.parent / "sample_data" / "resumes"


def test_parse_single_column_pdf():
    """Verify single-column PDF parsing extracts readable text."""
    pdf_path = SAMPLE_DIR / "01_strong_match_alex_chen.pdf"
    assert pdf_path.exists(), "Sample PDF must exist"

    text = parse_pdf(pdf_path)
    assert "Alex Chen" in text
    assert "FastAPI" in text
    assert "PostgreSQL" in text


def test_parse_two_column_pdf():
    """Verify two-column PDF is parsed without crashing and retains text from both columns."""
    pdf_path = SAMPLE_DIR / "10_two_column_david_kim.pdf"
    assert pdf_path.exists(), "Two column sample PDF must exist"

    text = parse_pdf(pdf_path)
    assert "David Kim" in text
    assert "FastAPI" in text
    assert "StreamLine Media" in text


def test_parse_docx():
    """Verify DOCX parser extracts text cleanly."""
    docx_path = SAMPLE_DIR / "02_good_match_jordan_taylor.docx"
    assert docx_path.exists(), "Sample DOCX must exist"

    text = parse_docx(docx_path)
    assert "Jordan Taylor" in text
    assert "FastAPI" in text
    assert "FinTech Innovations" in text


def test_parse_scanned_empty_pdf_raises_error():
    """Empty or scanned PDFs with no text layer should raise EmptyDocumentError gracefully."""
    empty_pdf_path = SAMPLE_DIR / "13_scanned_empty_edge_case.pdf"
    assert empty_pdf_path.exists(), "Edge case empty PDF must exist"

    with pytest.raises(EmptyDocumentError):
        parse_pdf(empty_pdf_path)


def test_parse_document_dispatch():
    """Verify parse_document routes by file extension properly."""
    docx_path = SAMPLE_DIR / "04_wrong_domain_liam_oconnor.docx"
    text = parse_document(docx_path, filename="resume.docx")
    assert "Liam O'Connor" in text
