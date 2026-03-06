#!/usr/bin/env python3
"""
Normalize door_type, body_material -> body_colour, and add door_heated + led_light_colour.

Run: python3 pir/scripts/normalize_fields_v2.py [--dry-run]
"""

import json
import sys
from pathlib import Path
from collections import Counter

RECORDS_DIR = Path(__file__).resolve().parent.parent / "records"

# ── door_type: normalize to "glass" or "solid" ──
DOOR_TYPE_MAP = {
    "triple_glazed_low_e": "glass",
    "heated_tempered": "glass",
    "dual_glazed_low_e": "glass",
    "solid_foamed": "solid",
    "stainless_steel_solid": "solid",
    "triple_layer_low_e": "glass",
    "double_pane": "glass",
    "double_layer_tempered": "glass",
    "dual_glazed_low_e_heated": "glass",
    "316 grade solid stainless": "solid",
    "triple_glazed_low_e_heated": "glass",
    "side_panel_low_e": "glass",
    "low_e": "glass",
    "304 Stainless Solid Door": "solid",
    "Solid Foamed Door": "solid",
    "tempered_lid": "glass",
    "triple_glazed_tempered": "glass",
}

# ── door_heated: extract from door_type before overwriting ──
HEATED_TYPES = {
    "heated_tempered",
    "dual_glazed_low_e_heated",
    "triple_glazed_low_e_heated",
}

# ── body_material -> body_colour ──
BODY_COLOUR_MAP = {
    "Black": "black",
    "Matte Black Finish": "black",
    "White": "white",
    "White - Ask us about branding in a custom design": "white",
    "Branded Custom Sticker": "branded",
    "Branded": "branded",
    "VB Branded": "branded",
    "Vodka Cruiser Branded": "branded",
    "Carlton Draught Branded": "branded",
    "Cartlon Draught Branded": "branded",  # typo in data
    "Melbourne Bitter Branded Custom Sticker": "branded",
    "Hard Rated Branded ": "branded",
    "Brookvale Union Branded": "branded",
    "Coca-Cola branded": "branded",
    "304 Stainless Steel": "stainless steel",
    "Brushed 304 Grade Stainless Steel": "stainless steel",
    "316 Marine Grade Stainless Steel": "stainless steel",
    "Silver": "stainless steel",
    "Light Grey": "stainless steel",
    "Body": None,  # garbage value, skip
}

# ── body_material: derive actual material from old body_material ──
BODY_MATERIAL_MAP = {
    "304 Stainless Steel": "304 stainless steel",
    "Brushed 304 Grade Stainless Steel": "304 stainless steel",
    "316 Marine Grade Stainless Steel": "316 marine grade stainless steel",
}

VALID_BODY_COLOURS = {"black", "white", "stainless steel", "branded"}


def normalize_record(filepath, dry_run):
    with open(filepath) as f:
        record = json.load(f)

    if not isinstance(record, dict):
        return None

    facts = record.get("facts")
    if not facts:
        return None

    changes = []

    # ── 1. door_type → glass/solid + door_heated ──
    old_door_type = facts.get("door_type")
    if old_door_type and old_door_type not in ("glass", "solid"):
        if old_door_type not in DOOR_TYPE_MAP:
            return {"file": filepath.name, "error": f"UNMAPPED door_type: {old_door_type!r}"}

        # Set door_heated before overwriting door_type
        is_heated = old_door_type in HEATED_TYPES
        if "door_heated" not in facts or facts["door_heated"] != is_heated:
            facts["door_heated"] = is_heated
            changes.append(f"door_heated: {old_door_type!r} -> {is_heated}")

        new_door_type = DOOR_TYPE_MAP[old_door_type]
        facts["door_type"] = new_door_type
        changes.append(f"door_type: {old_door_type!r} -> {new_door_type!r}")

    # If door_type not set but glass_door is, derive it
    if "door_type" not in facts and "glass_door" in facts:
        dt = "glass" if facts["glass_door"] else "solid"
        facts["door_type"] = dt
        # Also set door_heated false by default for these
        if "door_heated" not in facts:
            facts["door_heated"] = False
        changes.append(f"door_type: (from glass_door={facts['glass_door']}) -> {dt!r}")

    # Ensure door_heated exists for all glass doors
    if facts.get("door_type") == "glass" and "door_heated" not in facts:
        facts["door_heated"] = False
        changes.append("door_heated: (default) -> False")

    # ── 2. body_material -> body_colour + body_material ──
    old_body = facts.get("body_material")
    if old_body and old_body not in VALID_BODY_COLOURS:
        if old_body not in BODY_COLOUR_MAP:
            return {"file": filepath.name, "error": f"UNMAPPED body_material: {old_body!r}"}

        new_colour = BODY_COLOUR_MAP[old_body]
        if new_colour:
            facts["body_colour"] = new_colour
            changes.append(f"body_colour: {old_body!r} -> {new_colour!r}")

        # Set actual material if stainless
        new_material = BODY_MATERIAL_MAP.get(old_body)
        if new_material:
            facts["body_material"] = new_material
            changes.append(f"body_material: {old_body!r} -> {new_material!r}")
        else:
            # Remove the old body_material (it was a colour, not material)
            del facts["body_material"]
            changes.append(f"body_material: removed {old_body!r} (was colour not material)")

    # ── 3. led_light_colour ──
    if "led_lighting" in facts and facts["led_lighting"] and "led_light_colour" not in facts:
        # Check if we have existing colour data
        if "led_colours" in facts:
            # e.g. ['blue', 'white']
            colours = facts["led_colours"]
            facts["led_light_colour"] = colours if isinstance(colours, list) else [str(colours)]
            changes.append(f"led_light_colour: (from led_colours) -> {facts['led_light_colour']}")
        else:
            facts["led_light_colour"] = "white"
            changes.append("led_light_colour: (default) -> 'white'")

    if not changes:
        return None

    if not dry_run:
        with open(filepath, "w") as f:
            json.dump(record, f, indent=2, ensure_ascii=False)
            f.write("\n")

    return {"file": filepath.name, "changes": changes}


def main():
    dry_run = "--dry-run" in sys.argv
    if dry_run:
        print("=== DRY RUN ===\n")

    records = sorted(RECORDS_DIR.glob("*.json"))
    results = []
    errors = []
    skipped = 0

    for filepath in records:
        if "." in filepath.stem:
            continue
        result = normalize_record(filepath, dry_run)
        if result is None:
            skipped += 1
        elif "error" in result:
            errors.append(result)
        else:
            results.append(result)

    print(f"Records scanned: {len(records)}")
    print(f"Changed: {len(results)}")
    print(f"Skipped: {skipped}")
    print(f"Errors: {len(errors)}")

    if results:
        print(f"\n--- Changes ---")
        for r in results:
            for c in r["changes"]:
                print(f"  {r['file']}: {c}")

    if errors:
        print(f"\n--- ERRORS ---")
        for e in errors:
            print(f"  {e['file']}: {e['error']}")
        sys.exit(1)

    # Summary
    if not dry_run:
        # Verify final state
        dt_counts = Counter()
        bc_counts = Counter()
        heated_counts = Counter()
        led_counts = Counter()
        for filepath in records:
            if "." in filepath.stem:
                continue
            with open(filepath) as f:
                rec = json.load(f)
            if not isinstance(rec, dict):
                continue
            facts = rec.get("facts", {})
            dt_counts[facts.get("door_type", "(none)")] += 1
            bc_counts[facts.get("body_colour", "(none)")] += 1
            heated_counts[str(facts.get("door_heated", "(none)"))] += 1
            led_counts[str(facts.get("led_light_colour", "(none)"))] += 1

        print("\n--- Final State ---")
        print("\ndoor_type:")
        for v, c in dt_counts.most_common():
            print(f"  {c:4d}  {v}")
        print("\nbody_colour:")
        for v, c in bc_counts.most_common():
            print(f"  {c:4d}  {v}")
        print("\ndoor_heated:")
        for v, c in heated_counts.most_common():
            print(f"  {c:4d}  {v}")
        print("\nled_light_colour:")
        for v, c in led_counts.most_common():
            print(f"  {c:4d}  {v}")


if __name__ == "__main__":
    main()
