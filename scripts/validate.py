#!/usr/bin/env python3
"""Validate all records in /records/ against /schema/pir.v1.json"""

import json
import os
import sys

try:
    from jsonschema import validate, ValidationError
except ImportError:
    print("Install jsonschema: pip install jsonschema")
    sys.exit(1)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA_PATH = os.path.join(ROOT, "schema", "pir.v1.json")
RECORDS_DIR = os.path.join(ROOT, "records")

with open(SCHEMA_PATH) as f:
    schema = json.load(f)

errors = []
records = sorted(f for f in os.listdir(RECORDS_DIR) if f.endswith(".json"))

if not records:
    print("No records found.")
    sys.exit(0)

print(f"Validating {len(records)} record(s)...\n")

for filename in records:
    path = os.path.join(RECORDS_DIR, filename)
    with open(path) as f:
        try:
            record = json.load(f)
        except json.JSONDecodeError as e:
            errors.append(f"{filename}: invalid JSON — {e}")
            continue

    # GTIN must match filename
    expected_gtin = filename.replace(".json", "")
    if record.get("gtin") != expected_gtin:
        errors.append(
            f"{filename}: gtin field '{record.get('gtin')}' does not match filename '{expected_gtin}'"
        )

    try:
        validate(instance=record, schema=schema)
        print(f"  ✓  {filename}")
    except ValidationError as e:
        path_str = " > ".join(str(p) for p in e.absolute_path) or "root"
        errors.append(f"{filename}: {e.message} (at {path_str})")
        print(f"  ✗  {filename}")

if errors:
    print(f"\n{len(errors)} error(s):\n")
    for e in errors:
        print(f"  ✗  {e}")
    sys.exit(1)

print(f"\n{len(records)} record(s) valid.")
