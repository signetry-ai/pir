#!/usr/bin/env python3
"""
Fix door_count + door_hinge consistency across all PIR records.

1. Populates door_count from product name (1-Door, 2-Door, 3-Door)
2. Fixes hinge mismatches:
   - 1-door with "1 x left, 1 x right" -> right + reversible
   - 3-door with "1 x left, 1 x right" -> needs manual review (printed)

Run: python3 pir/scripts/fix_door_count_hinge.py [--dry-run]
"""

import json
import re
import sys
from pathlib import Path

RECORDS_DIR = Path(__file__).resolve().parent.parent / "records"

DOOR_RE = re.compile(r'(\d+)[- ]?door', re.IGNORECASE)


def extract_door_count(name):
    m = DOOR_RE.search(name)
    return int(m.group(1)) if m else None


def fix_record(filepath, dry_run):
    with open(filepath) as f:
        record = json.load(f)

    if not isinstance(record, dict):
        return None

    name = record.get("name", "")
    facts = record.get("facts")
    if not facts:
        return None

    changes = []
    door_count = extract_door_count(name)

    # Populate door_count if missing
    if door_count and facts.get("door_count") != door_count:
        old_dc = facts.get("door_count")
        facts["door_count"] = door_count
        changes.append(f"door_count: {old_dc} -> {door_count}")

    hinge = facts.get("door_hinge", "")
    reversible = facts.get("door_reversible", False)

    # Fix: 1-door with multi-hinge = actually reversible
    if door_count == 1 and hinge == "1 x left, 1 x right":
        facts["door_hinge"] = "right"
        facts["door_reversible"] = True
        changes.append(f"hinge: '1 x left, 1 x right' -> 'right' (reversible, 1-door)")

    # Flag: 3-door with "1 x left, 1 x right" (should be 2+1 config)
    if door_count == 3 and hinge == "1 x left, 1 x right":
        changes.append(f"WARNING: 3-door with '1 x left, 1 x right' - needs review")

    # Flag: 3-door with just "left" (incomplete)
    if door_count == 3 and hinge in ("left", "right"):
        changes.append(f"WARNING: 3-door with '{hinge}' - needs review")

    if not changes:
        return None

    if not dry_run:
        with open(filepath, "w") as f:
            json.dump(record, f, indent=2, ensure_ascii=False)
            f.write("\n")

    return {"file": filepath.name, "name": name, "changes": changes}


def main():
    dry_run = "--dry-run" in sys.argv

    if dry_run:
        print("=== DRY RUN (no files will be modified) ===\n")

    records = sorted(RECORDS_DIR.glob("*.json"))
    results = []
    warnings = []
    skipped = 0

    for filepath in records:
        result = fix_record(filepath, dry_run)
        if result is None:
            skipped += 1
        else:
            has_warning = any("WARNING" in c for c in result["changes"])
            if has_warning:
                warnings.append(result)
            results.append(result)

    print(f"Records scanned: {len(records)}")
    print(f"Modified: {len(results)}")
    print(f"Skipped (no change): {skipped}")
    print(f"Warnings (need review): {len(warnings)}")

    if results:
        print(f"\n--- Changes ---")
        for r in results:
            for c in r["changes"]:
                if "WARNING" not in c:
                    print(f"  {r['file']}: {c}")

    if warnings:
        print(f"\n--- WARNINGS (need manual review) ---")
        for r in warnings:
            for c in r["changes"]:
                if "WARNING" in c:
                    print(f"  {r['file']}: {r['name']} -> {c}")


if __name__ == "__main__":
    main()
