"""Test LLM note extraction."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from extract_notes import extract_notes, VALID_TOPICS


def test_extract_notes_returns_valid_structure():
    """Each note must have topic, text, source_quote, source_page."""
    chunks = [
        {"page": 5, "text": "The appliance must have a minimum ventilation gap of at least 10mm at sides, top and 50mm at the rear. The front grille must be completely unobstructed."},
        {"page": 7, "text": "The appliance can be placed into ECO mode to save energy. During ECO mode the inside temperature is allowed to rise a few degrees warmer than the Set Point."},
    ]
    record = {"sku": "SG2H-B-HD", "name": "2-Door Outdoor Bar Fridge", "brand": "Rhino"}

    notes = extract_notes(chunks, record)

    assert len(notes) > 0, "Should extract at least one note"
    for note in notes:
        assert note["topic"] in VALID_TOPICS, f"Invalid topic: {note['topic']}"
        assert len(note["text"]) > 0, "Text must not be empty"
        assert len(note["source_quote"]) > 0, "Source quote must not be empty"
        assert isinstance(note["source_page"], int), "Source page must be int"
    print(f"  Extracted {len(notes)} notes")
    for n in notes:
        print(f"    [{n['topic']}] {n['text'][:60]}...")


if __name__ == "__main__":
    test_extract_notes_returns_valid_structure()
    print("PASS: test_extract_notes_returns_valid_structure")
    print("\nAll tests passed!")
