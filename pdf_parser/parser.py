"""
PDF parser module: extract text (page-by-page) and metadata from PDF files.

Supports:
- Reading from a local file path
- Reading from raw bytes (e.g. uploaded via multipart/form-data)

Returns a structured dict:
{
    "metadata": {
        "title": str | None,
        "author": str | None,
        "creation_date": str | None,
        "num_pages": int,
    },
    "pages": [
        {"page": 1, "text": "..."},
        ...
    ],
    "warnings": ["..."],   # e.g. scanned/image-only PDF warning
}
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Union

import pypdf


def _extract_metadata(reader: pypdf.PdfReader) -> dict:
    meta = reader.metadata or {}

    def _clean(value) -> Union[str, None]:
        if value is None:
            return None
        return str(value).strip() or None

    return {
        "title": _clean(meta.get("/Title")),
        "author": _clean(meta.get("/Author")),
        "creation_date": _clean(meta.get("/CreationDate")),
        "num_pages": len(reader.pages),
    }


def _extract_pages(reader: pypdf.PdfReader) -> tuple[list[dict], list[str]]:
    pages = []
    warnings: list[str] = []
    image_only_pages = 0

    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        text = text.strip()
        if not text:
            image_only_pages += 1
        pages.append({"page": i, "text": text})

    if image_only_pages > 0:
        total = len(reader.pages)
        if image_only_pages == total:
            warnings.append(
                "This PDF appears to be a scanned/image-only document. "
                "No text could be extracted. Consider using an OCR tool "
                "(e.g. ocrmypdf or Tesseract) to convert it first."
            )
        else:
            warnings.append(
                f"{image_only_pages} of {total} page(s) appear to be "
                "image-only and yielded no extractable text."
            )

    return pages, warnings


def parse_pdf_bytes(data: bytes) -> dict:
    """Parse a PDF from raw bytes and return structured result."""
    reader = pypdf.PdfReader(io.BytesIO(data))
    metadata = _extract_metadata(reader)
    pages, warnings = _extract_pages(reader)
    return {"metadata": metadata, "pages": pages, "warnings": warnings}


def parse_pdf(path: Union[str, Path]) -> dict:
    """Parse a PDF from a local file path and return structured result."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"PDF file not found: {path}")
    if not path.is_file():
        raise ValueError(f"Path is not a file: {path}")
    return parse_pdf_bytes(path.read_bytes())
