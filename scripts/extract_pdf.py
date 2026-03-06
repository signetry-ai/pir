#!/usr/bin/env python3
"""Extract text chunks from a PDF, tagged with page numbers.

Returns a list of {"page": int, "text": str} dicts.
Empty pages are excluded.
"""

import os
import tempfile
import urllib.request

MAX_PDF_BYTES = 50 * 1024 * 1024  # 50MB


def extract_chunks_from_file(pdf_path: str) -> list[dict]:
    """Extract text chunks from a local PDF file."""
    import pdfplumber

    chunks = []
    with pdfplumber.open(pdf_path) as doc:
        for i, page in enumerate(doc.pages):
            text = page.extract_text()
            if text and text.strip():
                chunks.append({"page": i + 1, "text": text.strip()})
    return chunks


def extract_chunks_from_url(url: str) -> list[dict]:
    """Download a PDF from a URL and extract text chunks."""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        req = urllib.request.Request(url, headers={"User-Agent": "PIR-Intake/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            total = 0
            while True:
                chunk = resp.read(8192)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_PDF_BYTES:
                    os.unlink(tmp.name)
                    raise ValueError(f"PDF exceeds {MAX_PDF_BYTES // (1024*1024)}MB limit")
                tmp.write(chunk)
        tmp_path = tmp.name

    try:
        return extract_chunks_from_file(tmp_path)
    finally:
        os.unlink(tmp_path)
