"""Test PDF text extraction."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from extract_pdf import extract_chunks_from_url


def test_chunks_have_page_numbers():
    """Each chunk must have a page number and non-empty text."""
    record_path = os.path.join(os.path.dirname(__file__), "..", "records", "9351886006350.json")
    with open(record_path) as f:
        record = json.load(f)
    manual_url = next(d["url"] for d in record["documents"] if d["type"] == "manual")
    chunks = extract_chunks_from_url(manual_url)

    assert len(chunks) > 0, "Should extract at least one chunk"
    for chunk in chunks:
        assert "page" in chunk, "Each chunk must have a page number"
        assert "text" in chunk, "Each chunk must have text"
        assert isinstance(chunk["page"], int), "Page must be an integer"
        assert len(chunk["text"].strip()) > 0, "Text must not be empty"
    print(f"Extracted {len(chunks)} chunks")


def test_chunks_are_page_ordered():
    """Chunks should be in page order."""
    record_path = os.path.join(os.path.dirname(__file__), "..", "records", "9351886006350.json")
    with open(record_path) as f:
        record = json.load(f)
    manual_url = next(d["url"] for d in record["documents"] if d["type"] == "manual")
    chunks = extract_chunks_from_url(manual_url)
    pages = [c["page"] for c in chunks]
    assert pages == sorted(pages), "Chunks must be in page order"


if __name__ == "__main__":
    test_chunks_have_page_numbers()
    print("PASS: test_chunks_have_page_numbers")
    test_chunks_are_page_ordered()
    print("PASS: test_chunks_are_page_ordered")
    print("\nAll tests passed!")
