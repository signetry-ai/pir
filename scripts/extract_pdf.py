#!/usr/bin/env python3
"""Extract text and visual content from a PDF using Claude's native PDF vision.

Sends the full PDF to Claude, which sees every page as an image —
capturing diagrams, figure labels, control panels, and all text
that text-only extractors miss.

Returns a list of {"page": int, "text": str} dicts.
"""

import base64
import os
import tempfile
import urllib.request

import anthropic

MAX_PDF_BYTES = 50 * 1024 * 1024  # 50MB


EXTRACTION_PROMPT = """Extract ALL content from this PDF document, page by page.

For EACH page that contains content, output in this exact format:

--- PAGE N ---
[All text content on that page, preserving structure]
[For diagrams/figures: describe what the diagram shows and transcribe ALL labels, measurements, and annotations]
[For control panels/interfaces: describe every button, switch, display, and their labels]
[For step-by-step procedures: include every step with full detail]
[For tables: preserve the table structure]

RULES:
1. Include EVERY piece of text visible on each page — headings, body text, bullet points, figure captions, diagram labels, small print
2. For diagrams with measurements (e.g. ventilation gaps), transcribe the exact measurements shown
3. For control panel images, describe each button/switch and its label/function
4. For photos, briefly describe what they show (e.g. "Photo of a heavily blocked condenser")
5. Preserve section numbering (e.g. "1.3", "2.2.1")
6. Do NOT summarize — extract verbatim where possible
7. Do NOT skip pages even if they seem unimportant
8. Skip only truly blank pages"""


def extract_chunks_from_file(pdf_path: str) -> list[dict]:
    """Extract content from a local PDF using Claude vision."""
    client = anthropic.Anthropic()

    pdf_data = base64.standard_b64encode(open(pdf_path, "rb").read()).decode("utf-8")

    message = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=8192,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": pdf_data,
                    },
                },
                {
                    "type": "text",
                    "text": EXTRACTION_PROMPT,
                },
            ],
        }],
    )

    response_text = message.content[0].text

    # Parse the response into page-tagged chunks
    return _parse_page_chunks(response_text)


def extract_chunks_from_url(url: str) -> list[dict]:
    """Download a PDF from a URL and extract content using Claude vision."""
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


def _parse_page_chunks(response: str) -> list[dict]:
    """Parse '--- PAGE N ---' delimited response into chunks."""
    import re

    chunks = []
    # Split on page markers
    parts = re.split(r"---\s*PAGE\s+(\d+)\s*---", response)

    # parts[0] is text before first marker (usually empty)
    # parts[1] is page number, parts[2] is content, etc.
    i = 1
    while i < len(parts) - 1:
        page_num = int(parts[i])
        content = parts[i + 1].strip()
        if content:
            chunks.append({"page": page_num, "text": content})
        i += 2

    # If no page markers found, treat entire response as page 1
    if not chunks and response.strip():
        chunks.append({"page": 1, "text": response.strip()})

    return chunks
