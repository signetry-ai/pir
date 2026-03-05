#!/usr/bin/env python3
"""Normalize glass_door_type values across all PIR records.

Replaces marketing prose with structured construction descriptions.
"""

import json
import os
import re
import sys

RECORDS_DIR = os.path.join(os.path.dirname(__file__), "..", "records")

# Mapping from messy values → clean normalized values
# Order matters: checked top-down, first match wins
NORMALIZE_MAP = [
    # Solid doors (no glass)
    (r"304 Stainless Solid Door", "stainless_steel_solid"),
    (r"Solid Foamed Door", "solid_foamed"),
    (r"Tempered glass lid", "tempered_lid"),

    # Heated + dual glazed LOW E
    (r"(?i)dual glazed.*low.?e.*heated|heated.*dual glazed.*low.?e", "dual_glazed_low_e_heated"),
    (r"(?i)switchable.*heated.*dual glazed|dual glazed.*switchable.*heated", "dual_glazed_low_e_heated"),
    (r"(?i)Swtichable.*Stainless Steel heated", "heated_tempered"),  # typo in source, it's a heated glass door
    (r"(?i)dual glazed.*low.?e.*with heating", "dual_glazed_low_e_heated"),

    # Heated + triple glazed
    (r"(?i)triple.*low.?e.*heated|heated.*triple", "triple_glazed_low_e_heated"),
    (r"(?i)switchable.*heated.*triple|triple.*switchable", "triple_glazed_heated"),

    # Triple glazed LOW E (various capitalizations)
    (r"(?i)triple.*glazed.*low.?e|triple.*low.?e.*glass", "triple_glazed_low_e"),
    (r"(?i)tempered.*triple.*glazed.*low.?e", "triple_glazed_low_e"),
    (r"(?i)triple.*glazed.*tempered.*low.?e", "triple_glazed_low_e"),
    (r"(?i)Triple Glazed LOW E", "triple_glazed_low_e"),
    (r"(?i)triple glazed tempered", "triple_glazed_tempered"),

    # Triple layer (Lecavist style)
    (r"(?i)triple layer glass", "triple_layer_low_e"),

    # Dual glazed LOW E
    (r"(?i)dual glazed.*low.?e|both panes low.?e", "dual_glazed_low_e"),

    # Side panel LOW E
    (r"(?i)side glass panels.*low.?e", "side_panel_low_e"),

    # LOW E (generic, with marketing stripped)
    (r"(?i)low.?e glass helps prevent|low.?e glass prevents", "low_e"),

    # Heated glass (various marketing phrasings)
    (r"(?i)heated glass stops condensation", "heated_tempered"),
    (r"(?i)heated glass to prevent condensation", "heated_tempered"),
    (r"(?i)heated glass to stop condensation", "heated_tempered"),
    (r"(?i)heated glass \(stops condensation\)", "heated_tempered"),
    (r"(?i)heated glass", "heated_tempered"),
    (r"(?i)heated.*tempered|tempered.*heated", "heated_tempered"),

    # Double pane / double layer
    (r"(?i)double pane", "double_pane"),
    (r"(?i)double layer tempered", "double_layer_tempered"),
]


def normalize(value: str):
    """Return normalized value, or None if already clean / no match."""
    for pattern, replacement in NORMALIZE_MAP:
        if re.search(pattern, value):
            if value == replacement:
                return None  # already clean
            return replacement
    return None  # no match — leave as-is


def main():
    dry_run = "--dry-run" in sys.argv
    changed = 0
    skipped = 0
    errors = []

    for filename in sorted(os.listdir(RECORDS_DIR)):
        if not filename.endswith(".json"):
            continue
        filepath = os.path.join(RECORDS_DIR, filename)
        with open(filepath, "r") as f:
            record = json.load(f)

        facts = record.get("facts", {})
        old_value = facts.get("glass_door_type")
        if old_value is None:
            continue

        new_value = normalize(old_value)
        if new_value is None:
            skipped += 1
            continue

        print(f"  {filename}: \"{old_value}\" → \"{new_value}\"")
        changed += 1

        if not dry_run:
            facts["glass_door_type"] = new_value
            with open(filepath, "w") as f:
                json.dump(record, f, indent=2, ensure_ascii=False)
                f.write("\n")

    print(f"\n{'[DRY RUN] ' if dry_run else ''}Changed: {changed}, Skipped (already clean or no match): {skipped}")
    if errors:
        print(f"Errors: {len(errors)}")
        for e in errors:
            print(f"  {e}")


if __name__ == "__main__":
    main()
