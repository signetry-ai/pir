#!/usr/bin/env python3
"""
Normalize door_hinge field across all PIR records.

Splits the messy door_hinge string into two clean fields:
  - door_hinge: the physical hinge position (left, right, 1 x left, 1 x right, etc.)
  - door_reversible: boolean, can the hinge be changed

Run: python3 pir/scripts/normalize_hinge.py [--dry-run]
"""

import json
import sys
from pathlib import Path
from typing import Optional

RECORDS_DIR = Path(__file__).resolve().parent.parent / "records"

# Canonical hinge values
VALID_HINGE = {
    "left", "right",
    "1 x left, 1 x right",
    "1 x left, 2 x right",
    "2 x left, 1 x right",
    "sliding",
    "lift-up lid",
}

# Mapping: raw value -> (door_hinge, door_reversible)
HINGE_MAP = {
    # --- right, not reversible ---
    "right": ("right", False),
    "Right": ("right", False),
    "Right Hinge (Handle Left)": ("right", False),
    "Right Hing": ("right", False),
    "Right Hinged,": ("right", False),
    "Comes right-hinged": ("right", False),

    # --- left, not reversible ---
    "left": ("left", False),
    "Left Hinged": ("left", False),
    "Left Hinged (Handle On Right)": ("left", False),
    "Left Hinge (Handle Right)": ("left", False),
    "Left Hing (Handle Right)": ("left", False),

    # --- reversible, default unknown -> right ---
    "reversible": ("right", True),
    "Reversible Door (left or right)": ("right", True),
    "Reversible (Left / Right)": ("right", True),

    # --- right, reversible ---
    "Right Hinged (Reversible Door)": ("right", True),
    "Comes Right Hinged - Reversible Door (left or right)": ("right", True),
    "Can Be Changed To Left Hinged - Please Mention In Comments": ("right", True),
    "Right Hinged, If You Want Left Hinged See Model SK116L-B-HD": ("right", True),
    "Can Be Changed To Right Hinged - Select in option set": ("right", True),

    # --- left, reversible ---
    "Left Hinged (Reversible Door)": ("left", True),
    "Left Hinged (Reversible Door Can Be Changed)": ("left", True),
    "Can Be Changed To Right Hinged - Please Mention In Comments": ("left", True),
    "Comes LEFT Hinged, Can Be Changed To Right Hinged - Please Mention In Comments": ("left", True),
    "Can Be Changed To Right Hinged - Please Mention In Comments Or Search Model SK156R-SS": ("left", True),
    "**Left Hinge Only Available At The Moment": ("left", True),

    # --- multi-door, not reversible ---
    "1 x left, 1 x right": ("1 x left, 1 x right", False),
    "1 x Left & 1 x Right": ("1 x left, 1 x right", False),
    "1 x left, 2 x right": ("1 x left, 2 x right", False),
    "2 x Left & 1 x Right": ("2 x left, 1 x right", False),

    # --- multi-door, reversible ---
    "1 x Right And 1 x Left (Can Be Reversed On each If Needed)": ("1 x left, 1 x right", True),

    # --- non-hinge door types ---
    "sliding": ("sliding", False),
    "Lift Up Lid": ("lift-up lid", False),
    "Glass Lid": ("lift-up lid", False),
}


def normalize_record(filepath: Path, dry_run: bool) -> Optional[dict]:
    """Normalize a single record. Returns change summary or None if no change."""
    with open(filepath) as f:
        record = json.load(f)

    if not isinstance(record, dict):
        return None

    facts = record.get("facts")
    if not facts or "door_hinge" not in facts:
        return None

    raw = facts["door_hinge"]

    if raw not in HINGE_MAP:
        return {"file": filepath.name, "error": f"UNMAPPED VALUE: {raw!r}"}

    new_hinge, reversible = HINGE_MAP[raw]

    # Already clean?
    if facts.get("door_hinge") == new_hinge and facts.get("door_reversible") == reversible:
        return None

    old_value = raw
    facts["door_hinge"] = new_hinge
    facts["door_reversible"] = reversible

    if not dry_run:
        with open(filepath, "w") as f:
            json.dump(record, f, indent=2, ensure_ascii=False)
            f.write("\n")

    return {
        "file": filepath.name,
        "old": old_value,
        "new_hinge": new_hinge,
        "new_reversible": reversible,
    }


def main():
    dry_run = "--dry-run" in sys.argv

    if dry_run:
        print("=== DRY RUN (no files will be modified) ===\n")

    records = sorted(RECORDS_DIR.glob("*.json"))
    changes = []
    errors = []
    skipped = 0

    for filepath in records:
        result = normalize_record(filepath, dry_run)
        if result is None:
            skipped += 1
        elif "error" in result:
            errors.append(result)
        else:
            changes.append(result)

    # Report
    print(f"Records scanned: {len(records)}")
    print(f"Changed: {len(changes)}")
    print(f"Skipped (no change or no field): {skipped}")
    print(f"Errors: {len(errors)}")

    if changes:
        print(f"\n--- Changes ---")
        for c in changes:
            rev = " (reversible)" if c["new_reversible"] else ""
            print(f"  {c['file']}: {c['old']!r} -> {c['new_hinge']!r}{rev}")

    if errors:
        print(f"\n--- ERRORS (unmapped values) ---")
        for e in errors:
            print(f"  {e['file']}: {e['error']}")

    # Validate all output values are canonical
    bad = {c["new_hinge"] for c in changes} - VALID_HINGE
    if bad:
        print(f"\n!!! BUG: non-canonical values in output: {bad}")
        sys.exit(1)

    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
