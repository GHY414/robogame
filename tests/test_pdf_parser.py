"""Tests for the pdf_parser module and app.py API endpoints."""

from __future__ import annotations

import io
import json

import pypdf
import pytest

from pdf_parser import parse_pdf, parse_pdf_bytes
from app import app as flask_app


# ---------------------------------------------------------------------------
# Helper: build a minimal, valid PDF in memory with given text
# We embed each page's text using a simple PDF content stream written by hand
# so that pypdf can later extract it, without relying on pypdf internal APIs.
# ---------------------------------------------------------------------------

_PDF_HEADER = b"%PDF-1.4\n"

def _encode_obj(num: int, content: bytes) -> bytes:
    return f"{num} 0 obj\n".encode() + content + b"\nendobj\n"

def _make_pdf_bytes(pages_text: list[str]) -> bytes:
    """Build a minimal text-based PDF with one text object per page."""
    objects: list[bytes] = []
    offsets: list[int] = []
    buf = bytearray(_PDF_HEADER)

    def add_obj(content: bytes) -> int:
        obj_num = len(objects) + 1
        offsets.append(len(buf))
        raw = _encode_obj(obj_num, content)
        buf.extend(raw)
        objects.append(raw)
        return obj_num

    page_obj_nums: list[int] = []
    for text in pages_text:
        # Content stream
        stream_data = (
            b"BT\n/F1 12 Tf\n50 750 Td\n("
            + text.encode("latin-1", errors="replace")
            + b") Tj\nET"
        )
        stream_content = (
            f"<< /Length {len(stream_data)} >>\nstream\n".encode()
            + stream_data
            + b"\nendstream"
        )
        stream_num = add_obj(stream_content)

        # Font resource
        font_content = (
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"
        )
        font_num = add_obj(font_content)

        # Page object
        page_content = (
            f"<< /Type /Page /MediaBox [0 0 612 792]\n"
            f"   /Resources << /Font << /F1 {font_num} 0 R >> >>\n"
            f"   /Contents {stream_num} 0 R\n"
            f"   /Parent 1 0 R >>"
        ).encode()
        page_num = add_obj(page_content)
        page_obj_nums.append(page_num)

    # Pages dictionary (obj 1 — placeholder, we add it after pages)
    kids = " ".join(f"{n} 0 R" for n in page_obj_nums)
    pages_content = (
        f"<< /Type /Pages /Kids [{kids}] /Count {len(pages_text)} >>"
    ).encode()
    pages_num = add_obj(pages_content)

    # Catalog
    catalog_content = f"<< /Type /Catalog /Pages {pages_num} 0 R >>".encode()
    catalog_num = add_obj(catalog_content)

    # Cross-reference table
    xref_offset = len(buf)
    total = len(objects) + 1
    xref = f"xref\n0 {total}\n0000000000 65535 f \n".encode()
    for off in offsets:
        xref += f"{off:010d} 00000 n \n".encode()
    buf.extend(xref)

    trailer = (
        f"trailer\n<< /Size {total} /Root {catalog_num} 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n"
    ).encode()
    buf.extend(trailer)

    return bytes(buf)


# ---------------------------------------------------------------------------
# parse_pdf_bytes tests
# ---------------------------------------------------------------------------


def test_parse_pdf_bytes_single_page():
    data = _make_pdf_bytes(["Hello, World!"])
    result = parse_pdf_bytes(data)

    assert result["metadata"]["num_pages"] == 1
    assert isinstance(result["pages"], list)
    assert len(result["pages"]) == 1
    assert result["pages"][0]["page"] == 1
    assert "Hello" in result["pages"][0]["text"]


def test_parse_pdf_bytes_multiple_pages():
    data = _make_pdf_bytes(["Page one content", "Page two content", "Page three"])
    result = parse_pdf_bytes(data)

    assert result["metadata"]["num_pages"] == 3
    assert len(result["pages"]) == 3
    for i, page in enumerate(result["pages"], start=1):
        assert page["page"] == i


def test_parse_pdf_bytes_metadata_keys():
    data = _make_pdf_bytes(["Test"])
    result = parse_pdf_bytes(data)

    meta = result["metadata"]
    assert "num_pages" in meta
    assert "title" in meta
    assert "author" in meta
    assert "creation_date" in meta


def test_parse_pdf_bytes_warnings_list():
    data = _make_pdf_bytes(["Some text"])
    result = parse_pdf_bytes(data)
    assert isinstance(result["warnings"], list)


def test_parse_pdf_bytes_image_only_warning():
    """A blank PDF page (no text) should trigger a scanned-PDF warning."""
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=612, height=792)
    buf = io.BytesIO()
    writer.write(buf)
    data = buf.getvalue()

    result = parse_pdf_bytes(data)
    assert len(result["warnings"]) > 0
    assert any("scanned" in w.lower() or "image" in w.lower() for w in result["warnings"])


# ---------------------------------------------------------------------------
# parse_pdf (file path) tests
# ---------------------------------------------------------------------------


def test_parse_pdf_from_path(tmp_path):
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(_make_pdf_bytes(["File path test"]))

    result = parse_pdf(str(pdf_path))
    assert result["metadata"]["num_pages"] == 1


def test_parse_pdf_file_not_found():
    with pytest.raises(FileNotFoundError):
        parse_pdf("/nonexistent/path/file.pdf")


def test_parse_pdf_not_a_file(tmp_path):
    with pytest.raises(ValueError):
        parse_pdf(str(tmp_path))  # directory, not a file


# ---------------------------------------------------------------------------
# Flask API tests
# ---------------------------------------------------------------------------


@pytest.fixture()
def client():
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as c:
        yield c


def test_api_parse_upload_success(client):
    data = _make_pdf_bytes(["API upload test"])
    response = client.post(
        "/parse",
        data={"file": (io.BytesIO(data), "test.pdf")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["metadata"]["num_pages"] == 1
    assert len(body["pages"]) == 1


def test_api_parse_upload_no_file(client):
    response = client.post("/parse", data={}, content_type="multipart/form-data")
    assert response.status_code == 400
    assert "error" in response.get_json()


def test_api_parse_upload_wrong_extension(client):
    response = client.post(
        "/parse",
        data={"file": (io.BytesIO(b"not a pdf"), "file.txt")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 400
    assert "error" in response.get_json()


def test_api_parse_path_success(client, tmp_path):
    pdf_path = tmp_path / "api.pdf"
    pdf_path.write_bytes(_make_pdf_bytes(["Path API test"]))

    response = client.post(
        "/parse-url",
        data=json.dumps({"path": str(pdf_path)}),
        content_type="application/json",
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["metadata"]["num_pages"] == 1


def test_api_parse_path_missing(client):
    response = client.post(
        "/parse-url",
        data=json.dumps({}),
        content_type="application/json",
    )
    assert response.status_code == 400


def test_api_parse_path_not_found(client):
    response = client.post(
        "/parse-url",
        data=json.dumps({"path": "/nonexistent/file.pdf"}),
        content_type="application/json",
    )
    assert response.status_code == 404

