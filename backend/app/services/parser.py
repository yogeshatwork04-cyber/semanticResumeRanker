"""Document parsing service supporting PDF and DOCX formats.

Handles multi-column layouts, table cells, and scanned/empty document detection
with explicit, graceful error handling.
"""

from io import BytesIO
from pathlib import Path
from typing import BinaryIO

import docx
import pdfplumber


class DocumentParseError(Exception):
    """Base exception for document parsing failures."""
    pass


class EmptyDocumentError(DocumentParseError):
    """Raised when a document contains no extractable text (e.g., scanned image or empty)."""
    pass


def _detect_column_gutter_split(words: list[dict], page_width: float) -> float | None:
    """Detect horizontal split point in a multi-column page layout.

    Finds a vertical gutter (continuous vertical band with zero/minimal word overlap)
    between 20% and 70% of page width with substantial words on both sides.
    """
    if len(words) < 20:
        return None

    min_x = int(0.20 * page_width)
    max_x = int(0.70 * page_width)

    # Track horizontal word coverage across page width
    coverage = [0] * int(page_width + 1)
    for w in words:
        x0 = max(0, int(w["x0"]))
        x1 = min(int(page_width), int(w["x1"]))
        for x in range(x0, x1 + 1):
            coverage[x] += 1

    # Find the largest continuous gap where word coverage is minimal (<= 1)
    best_gap_start = None
    best_gap_len = 0
    cur_start = None

    for x in range(min_x, max_x):
        if coverage[x] <= 1:
            if cur_start is None:
                cur_start = x
        else:
            if cur_start is not None:
                gap_len = x - cur_start
                if gap_len > best_gap_len:
                    best_gap_len = gap_len
                    best_gap_start = cur_start
                cur_start = None

    # Check if a meaningful column gutter exists (at least 8 points wide)
    if best_gap_start is not None and best_gap_len >= 8:
        split_x = float(best_gap_start + best_gap_len / 2.0)
        left_words = [w for w in words if w["x1"] <= split_x]
        right_words = [w for w in words if w["x0"] >= split_x]

        # Both columns must hold at least 15% of total words
        if len(left_words) >= 0.15 * len(words) and len(right_words) >= 0.15 * len(words):
            return split_x

    return None


def _extract_page_text(page: pdfplumber.page.Page) -> str:
    """Extract text from a single PDF page with multi-column awareness."""
    words = page.extract_words(
        keep_blank_chars=False,
        x_tolerance=3,
        y_tolerance=3,
    )
    if not words:
        return ""

    width = float(page.width)
    height = float(page.height)

    split_x = _detect_column_gutter_split(words, width)
    if split_x is not None:
        # Extract left column then right column
        left_bbox = (0, 0, split_x, height)
        right_bbox = (split_x, 0, width, height)

        left_crop = page.crop(left_bbox)
        right_crop = page.crop(right_bbox)

        left_text = left_crop.extract_text(layout=False) or ""
        right_text = right_crop.extract_text(layout=False) or ""

        return f"{left_text}\n\n{right_text}"

    # Default single column extraction
    return page.extract_text(layout=False) or ""


def parse_pdf(source: str | Path | BinaryIO | bytes) -> str:
    """Parse a PDF document from a file path, file-like object, or raw bytes."""
    stream: str | Path | BinaryIO
    if isinstance(source, bytes):
        stream = BytesIO(source)
    else:
        stream = source

    try:
        page_texts: list[str] = []
        with pdfplumber.open(stream) as pdf:
            if not pdf.pages:
                raise EmptyDocumentError("PDF contains no pages.")

            for page in pdf.pages:
                page_str = _extract_page_text(page)
                if page_str.strip():
                    page_texts.append(page_str.strip())

        full_text = "\n\n".join(page_texts).strip()
        if not full_text or len(full_text) < 15:
            raise EmptyDocumentError(
                "Document contains no extractable text. It may be scanned or empty."
            )
        return full_text
    except EmptyDocumentError:
        raise
    except Exception as exc:
        raise DocumentParseError(f"Failed to parse PDF document: {exc}") from exc


def parse_docx(source: str | Path | BinaryIO | bytes) -> str:
    """Parse a DOCX document from a file path, file-like object, or raw bytes."""
    stream: str | Path | BinaryIO
    if isinstance(source, bytes):
        stream = BytesIO(source)
    else:
        stream = source

    try:
        doc = docx.Document(stream)
        lines: list[str] = []

        # Extract text from paragraphs
        for para in doc.paragraphs:
            text = para.text.strip()
            if text:
                lines.append(text)

        # Extract text from tables
        for table in doc.tables:
            for row in table.rows:
                row_cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if row_cells:
                    lines.append(" | ".join(row_cells))

        full_text = "\n".join(lines).strip()
        if not full_text or len(full_text) < 15:
            raise EmptyDocumentError(
                "Document contains no extractable text. It may be empty."
            )
        return full_text
    except EmptyDocumentError:
        raise
    except Exception as exc:
        raise DocumentParseError(f"Failed to parse DOCX document: {exc}") from exc


def parse_document(
    source: str | Path | BinaryIO | bytes,
    filename: str,
) -> str:
    """Parse any supported document (PDF, DOCX, TXT) based on file extension."""
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        return parse_pdf(source)
    elif ext in [".docx", ".doc"]:
        return parse_docx(source)
    elif ext in [".txt", ".md"]:
        if isinstance(source, bytes):
            text = source.decode("utf-8", errors="replace")
        elif isinstance(source, (str, Path)):
            text = Path(source).read_text(encoding="utf-8", errors="replace")
        else:
            text = source.read().decode("utf-8", errors="replace")  # type: ignore
        if not text.strip():
            raise EmptyDocumentError("Text document is empty.")
        return text.strip()
    else:
        raise DocumentParseError(f"Unsupported file format: '{ext}'. Allowed: .pdf, .docx, .txt")
