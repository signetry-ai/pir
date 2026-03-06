#!/usr/bin/env python3
"""One-shot fix for 7 manually reviewed records."""

import json
from pathlib import Path

RECORDS = Path(__file__).resolve().parent.parent / "records"

fixes = {
    "9351886001409": {
        "name": "Rhino SGT1L-BS \u2013 Black Upright Glass Door Drinks Fridge \u2013 293 Litres",
        "facts": {"door_count": 1, "door_hinge": "left", "door_reversible": False},
    },
    "9351886001393": {
        "name": "Rhino SGT1R-BS \u2013 293L Commercial Upright Glass Door Drinks Fridge \u2013 10 Star Rating",
        "facts": {"door_count": 1, "door_hinge": "right", "door_reversible": False},
    },
    "5060482000351": {
        "facts": {"door_hinge": "2 x left, 1 x right"},
    },
    "5060482000467": {
        "facts": {"door_hinge": "2 x left, 1 x right"},
    },
    "5060482003611": {
        "facts": {"door_hinge": "2 x left, 1 x right"},
    },
    "9351886003151": {
        "name": "Upright 2 Door Bar Fridge | Triple Zone | Beer + Wine | Slim Depth | Triple-Glazed Glass | Schmick SK168-Combo3",
        "facts": {"door_count": 2, "door_hinge": "1 x left, 1 x right"},
    },
    "9351886003366": {
        "facts": {"door_hinge": "2 x left, 1 x right"},
    },
}

for gtin, fix in fixes.items():
    fp = RECORDS / f"{gtin}.json"
    with open(fp) as f:
        rec = json.load(f)

    if "name" in fix:
        old_name = rec.get("name", "?")
        rec["name"] = fix["name"]
        print(f"  {gtin}: name: {old_name!r} -> {fix['name']!r}")

    for key, val in fix.get("facts", {}).items():
        old = rec["facts"].get(key)
        rec["facts"][key] = val
        print(f"  {gtin}: {key}: {old!r} -> {val!r}")

    with open(fp, "w") as f:
        json.dump(rec, f, indent=2, ensure_ascii=False)
        f.write("\n")

print("\nDone. 7 records fixed.")
