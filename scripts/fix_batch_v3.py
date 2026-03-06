#!/usr/bin/env python3
"""
Batch fixes:
1. Remove glass_door field (redundant with door_type)
2. BC46* fridges: ambient_temperature_max_c = 32
3. BC70* fridges: ambient_temperature_max_c = 32
4. Rename SKU HUS-BC46B-RET -> BC46B-RET
"""

import json
from pathlib import Path

RECORDS_DIR = Path(__file__).resolve().parent.parent / "records"

glass_door_removed = 0
bc46_fixed = 0
bc70_fixed = 0
sku_renamed = 0

for f in sorted(RECORDS_DIR.glob("*.json")):
    if "." in f.stem:
        continue
    with open(f) as fh:
        rec = json.load(fh)
    if not isinstance(rec, dict):
        continue
    facts = rec.get("facts", {})
    sku = rec.get("sku", "")
    dirty = False

    # 1. Remove glass_door
    if "glass_door" in facts:
        del facts["glass_door"]
        glass_door_removed += 1
        dirty = True

    # 2. BC46* ambient = 32
    if "bc46" in sku.lower():
        if facts.get("ambient_temperature_max_c") != 32:
            facts["ambient_temperature_max_c"] = 32
            bc46_fixed += 1
            dirty = True

    # 3. BC70* ambient = 32
    if "bc70" in sku.lower():
        if facts.get("ambient_temperature_max_c") != 32:
            facts["ambient_temperature_max_c"] = 32
            bc70_fixed += 1
            dirty = True

    # 4. Rename SKU
    if sku == "HUS-BC46B-RET":
        rec["sku"] = "BC46B-RET"
        sku_renamed += 1
        dirty = True

    if dirty:
        with open(f, "w") as fh:
            json.dump(rec, fh, indent=2, ensure_ascii=False)
            fh.write("\n")

print(f"glass_door removed: {glass_door_removed}")
print(f"BC46* ambient set to 32: {bc46_fixed}")
print(f"BC70* ambient set to 32: {bc70_fixed}")
print(f"SKU renamed HUS-BC46B-RET -> BC46B-RET: {sku_renamed}")

# Verify
errors = 0
for f in sorted(RECORDS_DIR.glob("*.json")):
    if "." in f.stem:
        continue
    with open(f) as fh:
        rec = json.load(fh)
    if not isinstance(rec, dict):
        continue
    facts = rec.get("facts", {})
    sku = rec.get("sku", "")

    if "glass_door" in facts:
        print(f"  BUG: {f.stem} still has glass_door")
        errors += 1
    if "bc46" in sku.lower() and facts.get("ambient_temperature_max_c") != 32:
        print(f"  BUG: {f.stem} BC46 ambient != 32")
        errors += 1
    if "bc70" in sku.lower() and facts.get("ambient_temperature_max_c") != 32:
        print(f"  BUG: {f.stem} BC70 ambient != 32")
        errors += 1

if errors == 0:
    print("\nAll verified clean.")
