"""Test adversarial verification of extracted notes."""
import os
import sys

# Load API key from backend/.env if not in env
if not os.environ.get("ANTHROPIC_API_KEY"):
    env_path = os.path.join(os.path.dirname(__file__), "..", "..", "backend", ".env")
    if os.path.exists(env_path):
        for line in open(env_path):
            if line.startswith("ANTHROPIC_API_KEY="):
                os.environ["ANTHROPIC_API_KEY"] = line.strip().split("=", 1)[1]

sys.path.insert(0, os.path.dirname(__file__))
from verify_notes import verify_notes


def test_grounded_note_passes():
    """A note whose text matches its source quote should be verified."""
    notes = [
        {
            "topic": "installation",
            "text": "Minimum ventilation clearance: 10mm sides and top, 50mm rear.",
            "source_quote": "the appliance must have a minimum ventilation gap of at least 10mm at sides, top and 50mm at the rear",
            "source_page": 5,
        }
    ]
    results = verify_notes(notes)
    assert len(results) == 1
    assert results[0]["verified"] is True, f"Expected grounded, got: {results[0].get('reason')}"
    print(f"  Grounded: {results[0]['reason']}")


def test_ungrounded_note_fails():
    """A note that adds information not in the source quote should fail."""
    notes = [
        {
            "topic": "installation",
            "text": "Unit requires a dedicated 20-amp circuit for safe operation.",
            "source_quote": "the appliance must always be earthed",
            "source_page": 4,
        }
    ]
    results = verify_notes(notes)
    assert len(results) == 1
    assert results[0]["verified"] is False, f"Expected ungrounded, got: {results[0].get('reason')}"
    print(f"  Ungrounded: {results[0]['reason']}")


if __name__ == "__main__":
    test_grounded_note_passes()
    print("PASS: test_grounded_note_passes")
    test_ungrounded_note_fails()
    print("PASS: test_ungrounded_note_fails")
    print("\nAll tests passed!")
