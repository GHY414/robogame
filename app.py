#!/usr/bin/env python3
"""
app.py — PDF reader: Flask API + CLI

Flask API endpoints:
  POST /parse          — upload a PDF (multipart/form-data, field: "file")
  POST /parse-url      — parse a PDF from a local path (JSON body: {"path": "..."})

CLI usage:
  python app.py <path-to-pdf>           # pretty-print JSON to stdout
  python app.py <path-to-pdf> --no-pages  # metadata + warnings only

Server usage:
  python app.py --serve                 # start Flask API server on port 5000
"""

from __future__ import annotations

import json
import sys

import pypdf
from flask import Flask, jsonify, request

from pdf_parser import parse_pdf, parse_pdf_bytes

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB upload limit


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------


@app.route("/parse", methods=["POST"])
def api_parse_upload():
    """Parse an uploaded PDF file (multipart/form-data, field name: 'file')."""
    if "file" not in request.files:
        return jsonify({"error": "No file field in request"}), 400

    uploaded = request.files["file"]
    if uploaded.filename == "":
        return jsonify({"error": "Empty filename"}), 400
    if not uploaded.filename.lower().endswith(".pdf"):
        return jsonify({"error": "Uploaded file must be a PDF"}), 400

    try:
        result = parse_pdf_bytes(uploaded.read())
    except pypdf.errors.PdfReadError as exc:
        return jsonify({"error": f"Invalid or corrupted PDF: {exc}"}), 422
    except Exception as exc:  # pylint: disable=broad-except
        return jsonify({"error": str(exc)}), 500

    return jsonify(result)


@app.route("/parse-url", methods=["POST"])
def api_parse_path():
    """Parse a PDF from a local server-side path.

    Request body (JSON): {"path": "/absolute/or/relative/file.pdf"}
    """
    body = request.get_json(silent=True) or {}
    path = body.get("path", "").strip()
    if not path:
        return jsonify({"error": "Missing 'path' in JSON body"}), 400

    try:
        result = parse_pdf(path)
    except FileNotFoundError as exc:
        return jsonify({"error": str(exc)}), 404
    except pypdf.errors.PdfReadError as exc:
        return jsonify({"error": f"Invalid or corrupted PDF: {exc}"}), 422
    except Exception as exc:  # pylint: disable=broad-except
        return jsonify({"error": str(exc)}), 500

    return jsonify(result)


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------


def _cli():
    import argparse

    parser = argparse.ArgumentParser(
        description="Parse a PDF and output structured JSON."
    )
    parser.add_argument("pdf", help="Path to the PDF file")
    parser.add_argument(
        "--no-pages",
        action="store_true",
        help="Omit per-page text from output (show metadata + warnings only)",
    )
    args = parser.parse_args()

    try:
        result = parse_pdf(args.pdf)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.no_pages:
        result = {k: v for k, v in result.items() if k != "pages"}

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    # Use `--serve` flag to start the Flask server; default is CLI mode.
    if "--serve" in sys.argv:
        sys.argv.remove("--serve")
        app.run(debug=False, host="0.0.0.0", port=5000)
    else:
        _cli()
