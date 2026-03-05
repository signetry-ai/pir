#!/usr/bin/env python3
"""Rename glass_door_type → door_type across all PIR records.

Also fixes glass_door=true on solid/stainless doors.
Updates Q&A fact citations too.
"""

import json
import os
import sys

RECORDS_DIR = os.path.join(os.path.dirname(__file__), "..", "records")

NON_GLASS_TYPES = {"solid_foamed", "stainless_steel_solid"}


def main():
    dry_run = "--dry-run" in sys.argv
    renamed = 0
    glass_fixed = 0

    for filename in sorted(os.listdir(RECORDS_DIR)):
        if not filename.endswith(".json"):
            continue
        filepath = os.path.join(RECORDS_DIR, filename)
        with open(filepath, "r") as f:
            record = json.load(f)

        changed = False
        facts = record.get("facts", {})

        # Rename glass_door_type → door_type
        if "glass_door_type" in facts:
            door_type = facts.pop("glass_door_type")
            facts["door_type"] = door_type
            changed = True
            renamed += 1

            # Fix glass_door for non-glass doors
            if door_type in NON_GLASS_TYPES and facts.get("glass_door") is True:
                facts["glass_door"] = False
                glass_fixed += 1
                print(f"  {filename}: glass_door=true → false (door_type={door_type})")

        # Update Q&A citations
        for qa in record.get("qa", []):
            if "glass_door_type" in qa.get("facts", []):
                qa["facts"] = ["door_type" if f == "glass_door_type" else f for f in qa["facts"]]
                changed = True

        if changed and not dry_run:
            with open(filepath, "w") as f:
                json.dump(record, f, indent=2, ensure_ascii=False)
                f.write("\n")

    prefix = "[DRY RUN] " if dry_run else ""
    print(f"\n{prefix}Renamed glass_door_type → door_type: {renamed}")
    print(f"{prefix}Fixed glass_door=false for solid doors: {glass_fixed}")


if __name__ == "__main__":
    main()
