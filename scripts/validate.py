#!/usr/bin/env python3
"""Validate all PIR records against the JSON schema."""

import json
import os
import sys

try:
    from jsonschema import Draft202012Validator
except ImportError:
    print("Install jsonschema: pip install jsonschema")
    sys.exit(1)

RECORDS_DIR = "records"
SCHEMA_PATH = "schema/pir.v1.json"


def main():
    with open(SCHEMA_PATH) as f:
        schema = json.load(f)

    validator = Draft202012Validator(schema)
    errors = 0
    checked = 0
    seen_gtins = set()

    for filename in sorted(os.listdir(RECORDS_DIR)):
        if not filename.endswith(".json"):
            continue

        checked += 1
        filepath = os.path.join(RECORDS_DIR, filename)
        with open(filepath) as f:
            try:
                record = json.load(f)
            except json.JSONDecodeError as e:
                print(f"  FAIL  {filename}: invalid JSON — {e}")
                errors += 1
                continue

        file_errors = list(validator.iter_errors(record))

        if file_errors:
            for err in file_errors:
                path = ".".join(str(p) for p in err.absolute_path) or "(root)"
                print(f"  FAIL  {filename}: {path} — {err.message}")
            errors += 1
            continue

        # Cross-check: filename must match gtin or sku- prefix
        gtin = record.get("gtin")
        sku = record.get("sku", "")
        if gtin:
            if filename != f"{gtin}.json":
                print(f"  FAIL  {filename}: filename doesn't match gtin '{gtin}'")
                errors += 1
            if gtin in seen_gtins:
                print(f"  FAIL  {filename}: duplicate gtin '{gtin}'")
                errors += 1
            seen_gtins.add(gtin)
        else:
            expected = f"sku-{sku}.json"
            if filename != expected:
                print(f"  FAIL  {filename}: expected filename '{expected}' for sku '{sku}'")
                errors += 1

    if errors:
        print(f"\n{errors} file(s) failed validation out of {checked} checked.")
        sys.exit(1)
    else:
        print(f"\n  OK  All {checked} records valid.")


if __name__ == "__main__":
    main()
