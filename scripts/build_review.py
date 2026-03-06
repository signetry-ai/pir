#!/usr/bin/env python3
"""Build an HTML review page for manual ingestion quality assessment.

Usage:
    python3 scripts/build_review.py 9351886006350

Generates records/{gtin}.review.html — open in browser to compare
PDF source text against extracted notes with highlighted source quotes.
"""

import html
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RECORDS_DIR = os.path.join(ROOT, "records")

sys.path.insert(0, os.path.join(ROOT, "scripts"))
from extract_pdf import extract_chunks_from_url


def highlight_quote(page_text: str, quote: str) -> str:
    """Highlight source_quote within page text. Case-insensitive fuzzy match."""
    escaped_text = html.escape(page_text)
    escaped_quote = html.escape(quote)

    # Try exact match first
    if escaped_quote in escaped_text:
        return escaped_text.replace(
            escaped_quote,
            f'<mark>{escaped_quote}</mark>',
            1,
        )

    # Try case-insensitive
    lower_text = escaped_text.lower()
    lower_quote = escaped_quote.lower()
    idx = lower_text.find(lower_quote)
    if idx >= 0:
        original = escaped_text[idx:idx + len(escaped_quote)]
        return escaped_text[:idx] + f'<mark>{original}</mark>' + escaped_text[idx + len(escaped_quote):]

    # Try first 60 chars as anchor (handles minor whitespace diffs)
    anchor = lower_quote[:60]
    idx = lower_text.find(anchor)
    if idx >= 0:
        end = min(idx + len(escaped_quote) + 50, len(escaped_text))
        original = escaped_text[idx:end]
        return escaped_text[:idx] + f'<mark>{original}</mark>' + escaped_text[end:]

    # No match — return with a warning marker
    return f'<span class="no-match-warning">⚠ Quote not found in page text</span>\n{escaped_text}'


def build_review_html(gtin: str) -> str:
    """Build the review HTML page."""
    record_path = os.path.join(RECORDS_DIR, f"{gtin}.json")
    notes_path = os.path.join(RECORDS_DIR, f"{gtin}.notes.json")

    with open(record_path) as f:
        record = json.load(f)
    with open(notes_path) as f:
        notes_data = json.load(f)

    # Load cached chunks (saved during ingestion) or re-extract
    chunks_path = os.path.join(RECORDS_DIR, f"{gtin}.chunks.json")
    if os.path.exists(chunks_path):
        print(f"Loading cached chunks...")
        with open(chunks_path) as f:
            chunks = json.load(f)
    chunks_by_page = {c["page"]: c["text"] for c in chunks}

    # Group notes by page
    notes_by_page = {}
    for note in notes_data["notes"]:
        page = note["source_page"]
        notes_by_page.setdefault(page, []).append(note)

    # Build HTML
    pages_html = []
    all_pages = sorted(set(list(chunks_by_page.keys()) + list(notes_by_page.keys())))

    for page_num in all_pages:
        page_text = chunks_by_page.get(page_num, "")
        page_notes = notes_by_page.get(page_num, [])

        # Build highlighted page text — highlight all quotes for this page
        highlighted = html.escape(page_text)
        for note in page_notes:
            quote = note["source_quote"]
            escaped_quote = html.escape(quote)
            lower_hl = highlighted.lower()
            lower_q = escaped_quote.lower()
            idx = lower_hl.find(lower_q)
            if idx >= 0:
                # Check it's not already inside a <mark> tag
                before = highlighted[:idx]
                if '<mark>' not in before[max(0, len(before)-6):]:
                    original = highlighted[idx:idx + len(escaped_quote)]
                    highlighted = highlighted[:idx] + f'<mark class="q-{id(note) % 1000}">{original}</mark>' + highlighted[idx + len(escaped_quote):]

        # Build notes cards
        notes_html = ""
        for note in page_notes:
            verified = note.get("verified", False)
            status_class = "grounded" if verified else "ungrounded"
            status_icon = "✅" if verified else "❌"
            reason = html.escape(note.get("reason", ""))

            notes_html += f'''
            <div class="note-card {status_class}">
                <div class="note-header">
                    <span class="status">{status_icon}</span>
                    <span class="topic">{html.escape(note["topic"])}</span>
                    <span class="verdict">{reason}</span>
                </div>
                <div class="note-text">{html.escape(note["text"])}</div>
                <div class="note-quote">
                    <span class="label">Source quote:</span>
                    "{html.escape(note["source_quote"])}"
                </div>
            </div>'''

        if not page_text and not page_notes:
            continue

        pages_html.append(f'''
        <div class="page-section">
            <h2>Page {page_num}</h2>
            <div class="page-row">
                <div class="pdf-column">
                    <h3>PDF Source Text</h3>
                    <pre class="pdf-text">{highlighted if highlighted.strip() else '<em class="empty">No text extracted (may be image/diagram)</em>'}</pre>
                </div>
                <div class="notes-column">
                    <h3>Extracted Notes ({len(page_notes)})</h3>
                    {notes_html if notes_html else '<p class="empty">No notes extracted from this page</p>'}
                </div>
            </div>
        </div>''')

    # Stats
    total = len(notes_data["notes"])
    grounded = sum(1 for n in notes_data["notes"] if n.get("verified"))
    ungrounded = total - grounded
    pages_with_text = len(chunks_by_page)
    pages_with_notes = len(notes_by_page)

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
        padding: 2rem;
        line-height: 1.5;
    }}
    header {{
        max-width: 1400px;
        margin: 0 auto 2rem;
        padding-bottom: 1.5rem;
        border-bottom: 1px solid #333;
    }}
    header h1 {{
        font-size: 1.5rem;
        color: #fff;
        margin-bottom: 0.5rem;
    }}
    header .subtitle {{
        color: #888;
        font-size: 0.9rem;
    }}
    .stats {{
        display: flex;
        gap: 2rem;
        margin-top: 1rem;
        font-family: 'SF Mono', 'Fira Code', monospace;
        font-size: 0.85rem;
    }}
    .stat {{
        display: flex;
        gap: 0.5rem;
    }}
    .stat .label {{ color: #666; }}
    .stat .value {{ color: #4ade80; }}
    .stat .value.warn {{ color: #f59e0b; }}

    .page-section {{
        max-width: 1400px;
        margin: 0 auto 3rem;
    }}
    .page-section h2 {{
        font-size: 1.1rem;
        color: #fff;
        margin-bottom: 1rem;
        padding: 0.5rem 1rem;
        background: #1a1a1a;
        border-left: 3px solid #3b82f6;
    }}
    .page-row {{
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 1.5rem;
    }}
    .pdf-column h3, .notes-column h3 {{
        font-size: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #666;
        margin-bottom: 0.75rem;
    }}
    .pdf-text {{
        background: #111;
        border: 1px solid #222;
        border-radius: 6px;
        padding: 1rem;
        font-family: 'SF Mono', 'Fira Code', monospace;
        font-size: 0.8rem;
        line-height: 1.7;
        white-space: pre-wrap;
        word-wrap: break-word;
        color: #999;
        max-height: 600px;
        overflow-y: auto;
    }}
    .pdf-text mark {{
        background: #3b82f620;
        color: #93c5fd;
        border-bottom: 2px solid #3b82f6;
        padding: 1px 2px;
    }}
    .no-match-warning {{
        color: #f59e0b;
        font-weight: bold;
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
        gap: 0.75rem;
        margin-bottom: 0.5rem;
        font-size: 0.8rem;
    }}
    .note-header .topic {{
        background: #1e293b;
        color: #93c5fd;
        padding: 2px 8px;
        border-radius: 4px;
        font-family: 'SF Mono', 'Fira Code', monospace;
        font-size: 0.75rem;
    }}
    .note-header .verdict {{
        color: #666;
        font-size: 0.75rem;
        margin-left: auto;
    }}
    .note-text {{
        color: #e0e0e0;
        font-size: 0.9rem;
        margin-bottom: 0.75rem;
        font-weight: 500;
    }}
    .note-quote {{
        font-size: 0.8rem;
        color: #666;
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
    }}
    .empty {{
        color: #444;
        font-style: italic;
    }}

    @media (max-width: 900px) {{
        .page-row {{
            grid-template-columns: 1fr;
        }}
    }}
</style>
</head>
<body>
<header>
    <h1>{html.escape(record["brand"])} {html.escape(record["sku"])} — {html.escape(record["name"])}</h1>
    <div class="subtitle">GTIN: {html.escape(gtin)} | Manual Ingestion Review</div>
    <div class="stats">
        <div class="stat">
            <span class="label">Pages extracted:</span>
            <span class="value">{pages_with_text}</span>
        </div>
        <div class="stat">
            <span class="label">Notes extracted:</span>
            <span class="value">{total}</span>
        </div>
        <div class="stat">
            <span class="label">Grounded:</span>
            <span class="value">{grounded}</span>
        </div>
        <div class="stat">
            <span class="label">Ungrounded:</span>
            <span class="value warn">{ungrounded}</span>
        </div>
        <div class="stat">
            <span class="label">Pages with notes:</span>
            <span class="value">{pages_with_notes}</span>
        </div>
    </div>
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
