#!/usr/bin/env python3
"""
Fix branded/wrapped product records to reflect true manufacturer.

These products are Schmick-manufactured fridges with licensed brand wraps.
Updates brand to manufacturer, adds branding metadata and base_model link.
"""

import json, os, re, sys


RECORDS_DIR = "records"

# Base model extraction patterns — SKU prefix → base model
# The wrap identifier is the suffix after the base model
BASE_MODEL_PATTERNS = [
    # BC46B-* and BC46W-* → BC46B or BC46W
    (r'^(BC46[BW]2?)[-_]', None),
    # BC70B-* → BC70B
    (r'^(BC70B)[-_]', None),
    # SC70-* → SC70
    (r'^(SC70)[-_]', None),
    # SC372-* → SC372 (with hinge variants)
    (r'^(SC372[LB]?[BW]?)[-_]', None),
    # SS-P160-* → SS-P160FA or SS-P160
    (r'^(SS-P160(?:FA)?)[-_]', None),
    # SK-BDC60-* → SK-BDC60
    (r'^(SK-BDC60)[-_]', None),
    # HUS-SC50* → HUS-SC50
    (r'^(HUS-SC50)\w*$', None),
    # HUS-SC372* → HUS-SC372
    (r'^(HUS-SC372[LBW]*)$', None),
    # SC88-* → SC88
    (r'^(SC88)[-_]', None),
    # EC68L-* → EC68L
    (r'^(EC68L)[-_]', None),
    # SC50AB-* → SC50AB
    (r'^(SC50AB)[-_]', None),
    # RF-42-* → RF-42
    (r'^(RF-42)[-_]', None),
    # PG65A-* → PG65A
    (r'^(PG65A)[-_]', None),
]

# Known wrap brands by keyword in SKU
WRAP_BRANDS = {
    'CORONA': ('Corona', 'CUB'),
    'DRAUGHT': ('Carlton Draught', 'CUB'),
    'VB': ('Victoria Bitter', 'CUB'),
    'GNBC': ('Great Northern', 'CUB'),
    'DRY': ('Carlton Dry', 'CUB'),
    'CRISP': ('Great Northern Crisp', 'CUB'),
    'GOLD': ('Great Northern Gold', 'CUB'),
    'ORIG': ('Great Northern Original', 'CUB'),
    'GTSR': ('HSV GTSR', 'Holden'),
    'HSV': ('HSV', 'Holden'),
    'SANDMAN': ('Holden Sandman', 'Holden'),
    'NED': ('Ned Kelly', 'Ned Kelly'),
    'CCR': ('Coca-Cola', 'Coca-Cola'),
    'CASTROL': ('Castrol', 'Castrol'),
    'FLEECE': ('Golden Fleece', 'Golden Fleece'),
    'DINO': ('Dino', 'Sinclair Oil'),
    'ESSO': ('Esso', 'Esso'),
    'GILMORE': ('Gilmore', 'Gilmore Oil'),
    'HANCOCK': ('Hancock', 'Hancock Oil'),
    'MOBIL': ('Mobil', 'Mobil'),
    'NEPTUNE': ('Neptune', 'Neptune Oil'),
    'SHELL': ('Shell', 'Shell'),
    'TEXACO': ('Texaco', 'Texaco'),
    'AMPOL': ('Ampol', 'Ampol'),
    'CALTEX': ('Caltex', 'Caltex'),
    'BP': ('BP', 'BP'),
    'PERONI': ('Peroni', 'Asahi'),
    'ASAHI': ('Asahi', 'Asahi'),
    'FOSTERS': ('Fosters', 'CUB'),
    'HR': ('Hahn Racing', 'Lion'),
    'MB': ('Melbourne Bitter', 'CUB'),
    'VC': ('Victoria Cross', 'CUB'),
    'CD': ('Carlton Draught', 'CUB'),
    'TB': ('Tardis Box', 'Novelty'),
    'VB1': ('Victoria Bitter', 'CUB'),
    'VB2': ('Victoria Bitter V2', 'CUB'),
    'FOOTY': ('AFL Football', 'AFL'),
    'RUGBY': ('Rugby', 'NRL'),
    'TENNIS': ('Tennis', 'Tennis Australia'),
    'GOLF': ('Golf', 'Golf Australia'),
    'DICE': ('Dice', 'Novelty'),
    'SAFE': ('Safe', 'Novelty'),
    'BVU': ('Branded Vinyl', 'Novelty'),
    'LWF': ('Branded Wrap', 'Custom'),
    'LWF2': ('Branded Wrap V2', 'Custom'),
    'PB': ('Police Box', 'Novelty'),
    'JOKER': ('Joker', 'DC Comics'),
}

# Fuel pump products
FUEL_PUMP_WRAPS = {
    'SC70-FP-': 'SC70',
    'SS-P160-FP-': 'SS-P160',
}

# Brands that should become Schmick manufacturer
SCHMICK_MANUFACTURED = {'CUB', 'cub', 'Fuel Pump', 'Holden', 'Ned Kelly',
                        'Coca Cola', 'Schmick OWL', 'Bar Fridges Australia',
                        'IC COLD', 'Dellcool', 'Dellware'}


def infer_base_model(sku):
    """Extract the base model from a branded SKU."""
    for pattern, _ in BASE_MODEL_PATTERNS:
        m = re.match(pattern, sku)
        if m:
            return m.group(1)
    return None


def infer_wrap_brand(sku, original_brand):
    """Determine the wrap brand from SKU keywords."""
    sku_upper = sku.upper()

    # Fuel pump special case
    for prefix, base in FUEL_PUMP_WRAPS.items():
        if sku_upper.startswith(prefix.upper()):
            suffix = sku[len(prefix):]
            for key, (brand_name, licensor) in WRAP_BRANDS.items():
                if key in suffix.upper():
                    return brand_name, licensor
            return suffix.replace('-', ' ').strip(), 'Fuel Pump'

    # Check SKU for wrap brand keywords
    # Split on hyphens and check each part
    parts = sku_upper.replace('_', '-').split('-')
    for part in reversed(parts):  # Check from end (wrap is usually suffix)
        # Strip version suffixes like V1, V2
        clean = re.sub(r'V\d+$', '', part)
        if clean in WRAP_BRANDS:
            brand_name, licensor = WRAP_BRANDS[clean]
            return brand_name, licensor

    # Holden special — HUS-SC50WH
    if 'SC50WH' in sku_upper:
        return 'Holden Sandman', 'Holden'

    # Fall back to original brand name
    if original_brand in ('CUB', 'cub'):
        return original_brand, 'CUB'
    return original_brand, original_brand


def determine_branding_type(sku, original_brand):
    """Determine if this is a licensed wrap, sub-brand, or OEM."""
    if original_brand in ('CUB', 'cub', 'Holden', 'Ned Kelly', 'Coca Cola', 'Fuel Pump'):
        return 'licensed_wrap'
    if original_brand == 'Schmick OWL':
        return 'sub_brand'
    if original_brand in ('Dellcool', 'Dellware'):
        return 'oem'  # Schmick-made, sold under Dellcool/Dellware brand
    if original_brand == 'IC COLD':
        return 'oem'
    if original_brand == 'Bar Fridges Australia':
        return 'house_brand'
    return 'licensed_wrap'


def main():
    dry_run = '--dry-run' in sys.argv
    updated = 0

    for f in sorted(os.listdir(RECORDS_DIR)):
        if not f.endswith('.json'):
            continue
        filepath = os.path.join(RECORDS_DIR, f)
        with open(filepath) as fh:
            record = json.load(fh)

        original_brand = record.get('brand', '')
        if original_brand not in SCHMICK_MANUFACTURED:
            continue

        sku = record.get('sku', '')
        base_model = infer_base_model(sku)
        branding_type = determine_branding_type(sku, original_brand)

        if branding_type == 'licensed_wrap':
            wrap_brand, licensor = infer_wrap_brand(sku, original_brand)
            record['manufacturer'] = 'Schmick'
            record['brand'] = 'Schmick'
            record['branding'] = {
                'type': 'licensed_wrap',
                'wrap_brand': wrap_brand,
                'licensor': licensor,
            }
            if base_model:
                record['base_model'] = base_model
        elif branding_type == 'sub_brand':
            record['manufacturer'] = 'Schmick'
            record['brand'] = 'Schmick'
            record['branding'] = {
                'type': 'sub_brand',
                'sub_brand': original_brand,
            }
            if base_model:
                record['base_model'] = base_model
        elif branding_type in ('oem', 'house_brand'):
            record['manufacturer'] = 'Schmick'
            record['brand'] = original_brand  # Keep their brand name
            record['branding'] = {
                'type': branding_type,
                'original_brand': original_brand,
            }

        if dry_run:
            branding_str = json.dumps(record.get('branding', {}))
            base_str = record.get('base_model', '-')
            print(f"  {sku:30s} brand={record['brand']:15s} base={base_str:12s} {branding_str}")
        else:
            with open(filepath, 'w') as fh:
                json.dump(record, fh, indent=2, ensure_ascii=False)
                fh.write('\n')

        updated += 1

    print(f"\n{'Would update' if dry_run else 'Updated'}: {updated} records")


if __name__ == '__main__':
    main()
