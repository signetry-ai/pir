#!/usr/bin/env python3
"""Ingest a product manual into PIR notes.

Usage:
    python3 scripts/ingest_manual.py 9351886006350

Pipeline:
    1. Load PIR record, find manual URL
    2. Extract text chunks from PDF
    3. LLM extraction — structured notes with source quotes
    4. LLM verification — adversarial grounding check
    5. Write candidate notes to records/{gtin}.notes.json for human review
"""

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RECORDS_DIR = os.path.join(ROOT, "records")


def _load_api_key():
    """Load ANTHROPIC_API_KEY from backend/.env if not in environment."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        return
    env_path = os.path.join(ROOT, "..", "backend", ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path) as f:
        for line in f:
            if line.startswith("ANTHROPIC_API_KEY="):
                os.environ["ANTHROPIC_API_KEY"] = line.strip().split("=", 1)[1]
                return


_load_api_key()

sys.path.insert(0, os.path.join(ROOT, "scripts"))
from extract_pdf import extract_chunks_from_url
from extract_notes import extract_notes
from verify_notes import verify_notes


def load_record(gtin: str) -> dict:
    path = os.path.join(RECORDS_DIR, f"{gtin}.json")
    with open(path) as f:
        return json.load(f)


def find_manual_url(record: dict):
    for doc in record.get("documents", []):
        if doc.get("type") == "manual":
            return doc["url"]
    return None


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/ingest_manual.py <GTIN>")
        sys.exit(1)

    gtin = sys.argv[1]
    print(f"Loading record for {gtin}...")
    record = load_record(gtin)
    print(f"  Product: {record['brand']} {record['sku']} — {record['name']}")

    manual_url = find_manual_url(record)
    if not manual_url:
        print("  ERROR: No manual document linked in this record.")
        sys.exit(1)
    print(f"  Manual: {manual_url[:80]}...")

    # Step 1: Extract text from PDF
    print("\n[1/3] Extracting text from PDF...")
    chunks = extract_chunks_from_url(manual_url)
    print(f"  Extracted {len(chunks)} pages with text")

    if not chunks:
        print("  ERROR: No text extracted from PDF. May be image-only.")
        sys.exit(1)

    # Step 2: LLM extraction
    print("\n[2/3] Extracting notes (LLM pass 1)...")
    notes = extract_notes(chunks, record)
    print(f"  Extracted {len(notes)} candidate notes")

    if not notes:
        print("  No notes extracted. Manual may not contain support content.")
        sys.exit(0)

    # Step 3: LLM verification
    print("\n[3/3] Verifying notes (LLM pass 2)...")
    verified_notes = verify_notes(notes)

    grounded = sum(1 for n in verified_notes if n["verified"])
    ungrounded = len(verified_notes) - grounded
    print(f"  Grounded: {grounded}, Ungrounded: {ungrounded}")

    # Add metadata
    for note in verified_notes:
        note["approved"] = False
        note["source_document"] = manual_url.split("/")[-1].split("?")[0]

    # Save chunks for review page
    chunks_path = os.path.join(RECORDS_DIR, f"{gtin}.chunks.json")
    with open(chunks_path, "w") as f:
        json.dump(chunks, f, indent=2, ensure_ascii=False)
        f.write("\n")

    # Write candidate notes for review
    output_path = os.path.join(RECORDS_DIR, f"{gtin}.notes.json")
    output = {
        "gtin": gtin,
        "sku": record["sku"],
        "brand": record["brand"],
        "name": record["name"],
        "source_manual": manual_url,
        "notes": verified_notes,
    }
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"\nCandidate notes written to: {output_path}")
    print(f"Review, edit, then run: python3 scripts/approve_notes.py {gtin}")


if __name__ == "__main__":
    main()
