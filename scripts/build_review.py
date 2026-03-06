#!/usr/bin/env python3
"""Build an HTML review page for manual ingestion quality assessment.

Usage:
    python3 scripts/build_review.py 9351886006350

Generates records/{gtin}.review.html — shows actual PDF page images
alongside extracted notes so you can visually compare what the LLM
saw vs what it extracted.
"""

import base64
import html
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RECORDS_DIR = os.path.join(ROOT, "records")


def load_page_image_b64(assets_dir: str, page_num: int):
    """Load a page image as base64, or None if missing."""
    path = os.path.join(assets_dir, f"page-{page_num:02d}.png")
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def build_review_html(gtin: str) -> str:
    """Build the review HTML page with PDF images + extracted notes."""
    record_path = os.path.join(RECORDS_DIR, f"{gtin}.json")
    notes_path = os.path.join(RECORDS_DIR, f"{gtin}.notes.json")
    chunks_path = os.path.join(RECORDS_DIR, f"{gtin}.chunks.json")
    assets_dir = os.path.join(RECORDS_DIR, gtin)

    with open(record_path) as f:
        record = json.load(f)
    with open(notes_path) as f:
        notes_data = json.load(f)

    # Load extracted chunks
    if os.path.exists(chunks_path):
        with open(chunks_path) as f:
            chunks = json.load(f)
    else:
        chunks = []
    chunks_by_page = {c["page"]: c["text"] for c in chunks}

    # Count page images
    if os.path.isdir(assets_dir):
        page_files = sorted(f for f in os.listdir(assets_dir) if f.startswith("page-") and f.endswith(".png"))
        total_pages = len(page_files)
    else:
        page_files = []
        total_pages = max((c["page"] for c in chunks), default=0)
    print(f"Found {total_pages} page images in {assets_dir}")

    # Group notes by page
    notes_by_page = {}
    for note in notes_data["notes"]:
        page = note["source_page"]
        notes_by_page.setdefault(page, []).append(note)

    # Build HTML for each page
    pages_html = []

    for page_num in range(1, total_pages + 1):
        page_notes = notes_by_page.get(page_num, [])
        page_b64 = load_page_image_b64(assets_dir, page_num)
        extracted_text = chunks_by_page.get(page_num, "")

        # Notes cards
        notes_html = ""
        for note in page_notes:
            verified = note.get("verified", False)
            status_class = "grounded" if verified else "ungrounded"
            status_icon = "&#x2705;" if verified else "&#x274C;"
            reason = html.escape(note.get("reason", ""))

            notes_html += f'''
            <div class="note-card {status_class}">
                <div class="note-header">
                    <span class="status">{status_icon}</span>
                    <span class="topic">{html.escape(note["topic"])}</span>
                </div>
                <div class="note-text">{html.escape(note["text"])}</div>
                <div class="note-quote">
                    <span class="label">Source quote:</span>
                    "{html.escape(note["source_quote"])}"
                </div>
                <div class="note-verdict">{reason}</div>
            </div>'''

        # Extracted text (collapsible)
        extracted_html = ""
        if extracted_text:
            escaped = html.escape(extracted_text)
            extracted_html = f'''
            <details class="extracted-text">
                <summary>Extracted text ({len(extracted_text)} chars)</summary>
                <pre>{escaped}</pre>
            </details>'''

        img_tag = f'<img src="data:image/png;base64,{page_b64}" alt="Page {page_num}" />' if page_b64 else '<p class="empty">No image available</p>'

        pages_html.append(f'''
        <div class="page-section">
            <div class="page-header">
                <h2>Page {page_num}</h2>
                <span class="note-count">{len(page_notes)} note{"s" if len(page_notes) != 1 else ""} extracted</span>
            </div>
            <div class="page-row">
                <div class="pdf-column">
                    {img_tag}
                </div>
                <div class="notes-column">
                    {notes_html if notes_html else '<p class="empty">No notes extracted from this page</p>'}
                    {extracted_html}
                </div>
            </div>
        </div>''')

    # Stats
    total = len(notes_data["notes"])
    grounded = sum(1 for n in notes_data["notes"] if n.get("verified"))
    ungrounded = total - grounded
    topics = {}
    for n in notes_data["notes"]:
        topics[n["topic"]] = topics.get(n["topic"], 0) + 1
    topics_html = " ".join(f'<span class="topic-pill">{t} <b>{c}</b></span>' for t, c in sorted(topics.items(), key=lambda x: -x[1]))

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>PIR Review — {html.escape(record["brand"])} {html.escape(record["sku"])}</title>
<style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
        background: #0a0a0a;
        color: #e0e0e0;
        line-height: 1.5;
    }}
    header {{
        max-width: 1600px;
        margin: 0 auto;
        padding: 2rem 2rem 1.5rem;
        border-bottom: 1px solid #222;
    }}
    header h1 {{
        font-size: 1.5rem;
        color: #fff;
        margin-bottom: 0.25rem;
    }}
    header .subtitle {{
        color: #666;
        font-size: 0.85rem;
        margin-bottom: 1rem;
    }}
    .stats {{
        display: flex;
        gap: 2rem;
        font-family: 'SF Mono', 'Fira Code', monospace;
        font-size: 0.8rem;
        margin-bottom: 0.75rem;
    }}
    .stat .label {{ color: #555; }}
    .stat .value {{ color: #4ade80; font-weight: 600; }}
    .stat .value.warn {{ color: #f59e0b; }}
    .topics {{
        display: flex;
        flex-wrap: wrap;
        gap: 0.5rem;
        margin-top: 0.75rem;
    }}
    .topic-pill {{
        background: #1e293b;
        color: #93c5fd;
        padding: 3px 10px;
        border-radius: 4px;
        font-size: 0.75rem;
        font-family: 'SF Mono', 'Fira Code', monospace;
    }}
    .topic-pill b {{ color: #4ade80; }}

    .page-section {{
        max-width: 1600px;
        margin: 0 auto;
        padding: 2rem;
        border-bottom: 1px solid #1a1a1a;
    }}
    .page-header {{
        display: flex;
        align-items: center;
        gap: 1rem;
        margin-bottom: 1rem;
    }}
    .page-header h2 {{
        font-size: 1.1rem;
        color: #fff;
        padding: 0.4rem 1rem;
        background: #1a1a1a;
        border-left: 3px solid #3b82f6;
    }}
    .note-count {{
        font-size: 0.8rem;
        color: #666;
    }}
    .page-row {{
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 2rem;
        align-items: start;
    }}
    .pdf-column {{
        position: sticky;
        top: 1rem;
    }}
    .pdf-column img {{
        width: 100%;
        border: 1px solid #222;
        border-radius: 6px;
        background: #fff;
    }}

    .note-card {{
        background: #111;
        border: 1px solid #222;
        border-radius: 6px;
        padding: 1rem;
        margin-bottom: 0.75rem;
    }}
    .note-card.grounded {{
        border-left: 3px solid #4ade80;
    }}
    .note-card.ungrounded {{
        border-left: 3px solid #ef4444;
        background: #1a0a0a;
    }}
    .note-header {{
        display: flex;
        align-items: center;
        gap: 0.5rem;
        margin-bottom: 0.5rem;
    }}
    .note-header .topic {{
        background: #1e293b;
        color: #93c5fd;
        padding: 2px 8px;
        border-radius: 4px;
        font-family: 'SF Mono', 'Fira Code', monospace;
        font-size: 0.75rem;
    }}
    .note-text {{
        color: #e0e0e0;
        font-size: 0.9rem;
        margin-bottom: 0.5rem;
        font-weight: 500;
    }}
    .note-quote {{
        font-size: 0.8rem;
        color: #888;
        font-style: italic;
        border-top: 1px solid #1a1a1a;
        padding-top: 0.5rem;
    }}
    .note-quote .label {{
        font-style: normal;
        color: #555;
        font-size: 0.7rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        display: block;
        margin-bottom: 2px;
    }}
    .note-verdict {{
        font-size: 0.75rem;
        color: #555;
        margin-top: 0.5rem;
    }}
    .empty {{
        color: #333;
        font-style: italic;
        padding: 1rem;
    }}
    .extracted-text {{
        margin-top: 1rem;
    }}
    .extracted-text summary {{
        font-size: 0.75rem;
        color: #555;
        cursor: pointer;
        padding: 0.5rem;
        background: #0d0d0d;
        border-radius: 4px;
    }}
    .extracted-text pre {{
        font-size: 0.7rem;
        color: #666;
        background: #0d0d0d;
        padding: 1rem;
        border-radius: 0 0 4px 4px;
        white-space: pre-wrap;
        word-wrap: break-word;
        max-height: 400px;
        overflow-y: auto;
        line-height: 1.6;
    }}

    @media (max-width: 1000px) {{
        .page-row {{
            grid-template-columns: 1fr;
        }}
        .pdf-column {{
            position: static;
        }}
    }}
</style>
</head>
<body>
<header>
    <h1>{html.escape(record["brand"])} {html.escape(record["sku"])} — {html.escape(record["name"])}</h1>
    <div class="subtitle">GTIN: {html.escape(gtin)} | Manual Ingestion Review | {total_pages} pages</div>
    <div class="stats">
        <div class="stat">
            <span class="label">Notes:</span>
            <span class="value">{total}</span>
        </div>
        <div class="stat">
            <span class="label">Grounded:</span>
            <span class="value">{grounded}</span>
        </div>
        <div class="stat">
            <span class="label">Ungrounded:</span>
            <span class="value{"" if ungrounded == 0 else " warn"}">{ungrounded}</span>
        </div>
    </div>
    <div class="topics">{topics_html}</div>
</header>

{"".join(pages_html)}

</body>
</html>'''


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/build_review.py <GTIN>")
        sys.exit(1)

    gtin = sys.argv[1]
    output_path = os.path.join(RECORDS_DIR, f"{gtin}.review.html")

    page_html = build_review_html(gtin)

    with open(output_path, "w") as f:
        f.write(page_html)

    print(f"Review page written to: {output_path}")
    print(f"Open: file://{output_path}")


if __name__ == "__main__":
    main()
