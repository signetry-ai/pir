#!/usr/bin/env python3
"""Validate all records in /records/ against /schema/pir.v1.json

Install: pip install jsonschema==4.23.0
"""

import json
import os
import sys

try:
    from jsonschema import validate, ValidationError
except ImportError:
    print("Install jsonschema: pip install jsonschema==4.23.0")
    sys.exit(1)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA_PATH = os.path.join(ROOT, "schema", "pir.v1.json")
RECORDS_DIR = os.path.join(ROOT, "records")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def gtin_check_digit_valid(gtin: str) -> bool:
    """
    Validate GS1 check digit (Luhn-variant algorithm).
    Note: Some manufacturer-assigned GTINs may not pass this check.
    Failures are warnings, not errors.
    """
    digits = [int(d) for d in gtin]
    total = sum(
        d * (3 if (len(digits) - 1 - i) % 2 == 0 else 1)
        for i, d in enumerate(digits[:-1])
    )
    expected = (10 - (total % 10)) % 10
    return digits[-1] == expected


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if not os.path.isdir(RECORDS_DIR):
    print("No records/ directory found. Nothing to validate.")
    sys.exit(0)

with open(SCHEMA_PATH) as f:
    schema = json.load(f)

errors = []
warnings = []
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
            print(f"  ✗  {filename}")
            continue

    # GTIN must match filename
    expected_gtin = filename.replace(".json", "")
    if record.get("gtin") != expected_gtin:
        errors.append(
            f"{filename}: gtin field '{record.get('gtin')}' does not match filename"
        )

    # brand_certified must not be set to true via PR — certification is maintainer-only
    if record.get("status", {}).get("brand_certified") is True:
        errors.append(
            f"{filename}: brand_certified: true must be set by a maintainer after DNS "
            f"verification, not via PR. Set brand_certified: false and open a "
            f"certification issue instead."
        )

    # Schema validation
    try:
        validate(instance=record, schema=schema)
        print(f"  ✓  {filename}")
    except ValidationError as e:
        field = " > ".join(str(p) for p in e.absolute_path) or "root"
        errors.append(f"{filename}: {e.message} (at {field})")
        print(f"  ✗  {filename}")
        continue

    # Check digit advisory (warning only — some GTINs are manufacturer-assigned)
    gtin = record.get("gtin", "")
    if len(gtin) in (8, 12, 13, 14) and not gtin_check_digit_valid(gtin):
        warnings.append(
            f"{filename}: GTIN {gtin} has an unexpected check digit. "
            f"Verify it matches the physical barcode. "
            f"(Manufacturer-assigned GTINs may not follow GS1 check digit rules.)"
        )

if warnings:
    print(f"\n{len(warnings)} warning(s):\n")
    for w in warnings:
        print(f"  ⚠  {w}")

if errors:
    print(f"\n{len(errors)} error(s):\n")
    for e in errors:
        print(f"  ✗  {e}")
    sys.exit(1)

print(f"\n{len(records)} record(s) valid.")
