#!/usr/bin/env python3
"""Merge approved notes from a .notes.json file into the PIR record.

Usage:
    # After reviewing and editing the .notes.json file:
    python3 scripts/approve_notes.py 9351886006350

    # Approve all grounded notes without interactive review:
    python3 scripts/approve_notes.py 9351886006350 --auto-approve-grounded
"""

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RECORDS_DIR = os.path.join(ROOT, "records")


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/approve_notes.py <GTIN> [--auto-approve-grounded]")
        sys.exit(1)

    gtin = sys.argv[1]
    auto_approve = "--auto-approve-grounded" in sys.argv

    notes_path = os.path.join(RECORDS_DIR, f"{gtin}.notes.json")
    record_path = os.path.join(RECORDS_DIR, f"{gtin}.json")

    if not os.path.exists(notes_path):
        print(f"No notes file found: {notes_path}")
        print(f"Run: python3 scripts/ingest_manual.py {gtin}")
        sys.exit(1)

    with open(notes_path) as f:
        notes_data = json.load(f)
    with open(record_path) as f:
        record = json.load(f)

    if auto_approve:
        for note in notes_data["notes"]:
            if note.get("verified"):
                note["approved"] = True

    # Collect approved notes
    approved = [n for n in notes_data["notes"] if n.get("approved")]
    rejected = len(notes_data["notes"]) - len(approved)

    if not approved:
        print("No approved notes found. Edit the .notes.json file and set approved: true.")
        sys.exit(0)

    # Merge into record — deduplicate by (topic, source_quote)
    existing_notes = record.get("notes", [])
    existing_keys = {(n["topic"], n.get("source_quote", "")) for n in existing_notes}
    added = 0
    skipped = 0

    for note in approved:
        key = (note["topic"], note.get("source_quote", ""))
        if key in existing_keys:
            skipped += 1
            continue
        existing_keys.add(key)
        clean_note = {
            "topic": note["topic"],
            "text": note["text"],
            "facts": note.get("facts", []),
            "source_quote": note["source_quote"],
            "source_page": note["source_page"],
            "source_document": note["source_document"],
            "verified": True,
            "approved": True,
        }
        existing_notes.append(clean_note)
        added += 1

    record["notes"] = existing_notes

    with open(record_path, "w") as f:
        json.dump(record, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Merged {added} approved notes into {record_path}")
    if skipped:
        print(f"Skipped {skipped} duplicates (already in record)")
    print(f"Rejected: {rejected}")
    print(f"\nDon't forget to commit:")
    print(f"  git add records/{gtin}.json")
    print(f"  git commit -m 'feat({gtin}): add {added} verified support notes from manual'")


if __name__ == "__main__":
    main()
