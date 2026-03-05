#!/usr/bin/env python3
"""
Process Lecavist intake file into PIR records.

Parses the RTF-exported text from ~/Documents/lecavist.rtf,
extracts specs from product descriptions + spec tables,
and generates PIR JSON records.

Usage:
    python scripts/process_lecavist.py                # Process all
    python scripts/process_lecavist.py --dry-run      # Preview only
"""

import json, os, re, sys, subprocess


RECORDS_DIR = "records"

# GTIN lookup from Shopify .json endpoints (pre-fetched)
GTIN_MAP = {
    "LEK14PV": "739988380414",
    "LEK21PV": "739988380421",
    "LEK33PV": "739988380438",
    "LJ17VN2ZBU": "739988379296",
    "LJ20VNBU": "739988379289",
    "LJ40VN2Z2DBU": None,        # Missing from Shopify
    "LJ44VN2ZBU": None,          # Missing from Shopify
    "LJ52VNBU": "739988379302",
    "LKS56VN2Z": "0684910432016",
    "LKCV63N": "0633710296762",
    "LCS100VNFS": None,          # Missing from Shopify
    "LEK1052ZPVFS": None,        # Missing from Shopify
    "LEK1052ZPVFS-1": None,      # URL variant
}


def read_intake():
    """Read and convert the RTF intake file to plain text."""
    rtf_path = os.path.expanduser("~/Documents/lecavist.rtf")
    if not os.path.exists(rtf_path):
        print(f"ERROR: {rtf_path} not found")
        sys.exit(1)
    result = subprocess.run(
        ["textutil", "-convert", "txt", "-stdout", rtf_path],
        capture_output=True, text=True
    )
    return result.stdout


def split_products(text):
    """Split intake text into individual product blocks separated by —."""
    blocks = re.split(r'\n—+\n', text)
    products = []
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        # Must start with a URL
        lines = block.split('\n')
        if lines[0].startswith('https://'):
            products.append(block)
    return products


def extract_sku(text):
    """Extract SKU/model code from text."""
    # Look for known SKU patterns in parentheses or after "Model"
    m = re.search(r'\(([A-Z]{2,3}\w+)\)', text)
    if m:
        return m.group(1)
    # Look for SKU patterns in the URL
    m = re.search(r'-(l[a-z]+\d+\w*)\s*$', text.split('\n')[0], re.IGNORECASE)
    if m:
        return m.group(1).upper()
    return None


def parse_dimensions(text):
    """Extract dimensions (W x H x D) in mm from various formats."""
    dims = {}
    # Format: W595 x D575 x H820 mm
    m = re.search(r'W(\d+)\s*x\s*D(\d+)\s*x\s*H(\d+)', text)
    if m:
        dims['w'], dims['d'], dims['h'] = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return dims
    # Format: W595 x H820 x D575 mm
    m = re.search(r'W(\d+)\s*x\s*H(\d+)\s*x\s*D(\d+)', text)
    if m:
        dims['w'], dims['h'], dims['d'] = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return dims
    # Format: 445 (W) x 515 (H) x 457 (D) mm
    m = re.search(r'(\d+)\s*\(W\)\s*x\s*(\d+)\s*\(H\)\s*x\s*(\d+)\s*\(D\)', text)
    if m:
        dims['w'], dims['h'], dims['d'] = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return dims
    # Format: 500(W) x 850 (H) x 600 (D) mm
    m = re.search(r'(\d+)\s*\(W\)\s*x\s*(\d+)\s*\(H\)\s*x\s*(\d+)\s*\(D\)', text)
    if m:
        dims['w'], dims['h'], dims['d'] = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return dims
    # Format: 50cm (W) x 57.5cm (D) x 84.7cm (H) — convert to mm
    m = re.search(r'([\d.]+)\s*cm\s*\(W\)\s*x\s*([\d.]+)\s*cm\s*\(D\)\s*x\s*([\d.]+)\s*cm\s*\(H\)', text)
    if m:
        dims['w'] = int(float(m.group(1)) * 10)
        dims['d'] = int(float(m.group(2)) * 10)
        dims['h'] = int(float(m.group(3)) * 10)
        return dims
    # Format: 44.5cm (W) x 47.0cm (D) x 50.0cm (H)
    m = re.search(r'([\d.]+)\s*cm\s*\(W\)\s*x\s*([\d.]+)\s*cm\s*\(D\)\s*x\s*([\d.]+)\s*cm\s*\(H\)', text)
    if m:
        dims['w'] = int(float(m.group(1)) * 10)
        dims['d'] = int(float(m.group(2)) * 10)
        dims['h'] = int(float(m.group(3)) * 10)
        return dims
    # Format: Outside: 500 (W) x 1250 (H) x 560 (D) mm
    m = re.search(r'Outside:\s*(\d+)\s*\(W\)\s*x\s*(\d+)\s*\(H\)\s*x\s*(\d+)\s*\(D\)', text)
    if m:
        dims['w'], dims['h'], dims['d'] = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return dims
    # Format: 545 (W) x 1244 (H) x 600 (D) mm
    m = re.search(r'(\d+)\s*\(W\)\s*x\s*(\d+)\s*\(H\)\s*x\s*(\d+)\s*\(D\)', text)
    if m:
        dims['w'], dims['h'], dims['d'] = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return dims
    return dims


def parse_product(block):
    """Parse a single product block into structured data."""
    lines = block.split('\n')
    url = lines[0].strip()
    text = '\n'.join(lines[1:])

    data = {'url': url, 'text': text}

    # SKU from URL or text
    # Try URL first
    url_m = re.search(r'-(l[a-z]+\d+\w*(?:fs)?(?:-\d+)?)\s*$', url.split('/')[-1], re.IGNORECASE)
    if url_m:
        data['sku'] = url_m.group(1).upper()
    # Try parentheses in text
    sku_m = re.search(r'\(([A-Z]{2,3}[A-Z0-9]+)\)', text)
    if sku_m:
        data['sku'] = sku_m.group(1)

    # GTIN
    sku = data.get('sku', '')
    data['gtin'] = GTIN_MAP.get(sku)

    # Product name/title — first non-empty line after URL
    for line in lines[1:]:
        line = line.strip()
        if line and not line.startswith('http'):
            data['title'] = line
            break

    # Capacity litres
    m = re.search(r'(\d+)\s*L\s+(?:Capacity|Bordeaux|fridge)', text)
    if m:
        data['capacity_litres'] = int(m.group(1))
    else:
        m = re.search(r'(\d+)L\b', text)
        if m:
            data['capacity_litres'] = int(m.group(1))

    # Bottle capacity
    m = re.search(r'(\d+)\s*(?:Bottle|bottle)\s*(?:Capacity|capacity)', text)
    if m:
        data['capacity_bottles'] = int(m.group(1))
    else:
        m = re.search(r'(\d+)\s*Bordeaux\s*bottles\s*capacity', text)
        if m:
            data['capacity_bottles'] = int(m.group(1))

    # Dimensions
    data['dims'] = parse_dimensions(text)

    # Weight
    m = re.search(r'(?:Weight|weight)[:\s]*(\d+(?:\.\d+)?)\s*kg', text, re.IGNORECASE)
    if m:
        w = float(m.group(1))
        data['weight_kg'] = int(w) if w == int(w) else w
    else:
        m = re.search(r'(?:Net weight)[:\s]*(\d+(?:\.\d+)?)\s*kg', text, re.IGNORECASE)
        if m:
            w = float(m.group(1))
            data['weight_kg'] = int(w) if w == int(w) else w

    # Noise
    m = re.search(r'(\d+)\s*dB', text)
    if m:
        data['noise_db'] = int(m.group(1))

    # Energy consumption kWh/annum
    m = re.search(r'(\d+)\s*[kK][wW]h\s*/?\s*(?:annum|annual|per\s*(?:year|annum))', text)
    if not m:
        m = re.search(r'(?:annual\s*)?energy consumption[^.]*?(\d+)\s*[kK][wW]h', text, re.IGNORECASE)
    if m:
        data['energy_kwh_annual'] = int(m.group(1))

    # Temperature range
    m = re.search(r'temperature range[^.]*?(\d+)\s*°?\s*C\s*to\s*(\d+)\s*°?\s*C', text, re.IGNORECASE)
    if m:
        data['temp_min_c'] = int(m.group(1))
        data['temp_max_c'] = int(m.group(2))

    # Ambient/climate range
    m = re.search(r'(?:room temperature|climate)[^.]*?(\d+)\s*°?\s*C\s*to\s*(\d+)\s*°?\s*C', text, re.IGNORECASE)
    if m:
        data['ambient_min_c'] = int(m.group(1))
        data['ambient_max_c'] = int(m.group(2))
    else:
        m = re.search(r'up to\s*(\d+)\s*°?\s*C', text)
        if m:
            data['ambient_max_c'] = int(m.group(1))

    # Zones
    if re.search(r'[Dd]ual [Zz]one|[Dd]ouble [Zz]one|2 [Tt]emperature [Zz]one', text):
        data['zones'] = 2
    else:
        data['zones'] = 1

    # Shelves
    m = re.search(r'(\d+)\s*(?:wooden|beech|wire|elegant\s*wooden)\s*shelv', text, re.IGNORECASE)
    if not m:
        m = re.search(r'(\d+)\s*shelv', text, re.IGNORECASE)
    if m:
        data['shelf_count'] = int(m.group(1))
    # Shelf material
    if re.search(r'beech\s*wood', text, re.IGNORECASE):
        data['shelf_material'] = "Beech wood"
    elif re.search(r'wire\s*shelv', text, re.IGNORECASE):
        data['shelf_material'] = "Wire with wood trim"
    elif re.search(r'wooden\s*shelv', text, re.IGNORECASE):
        data['shelf_material'] = "Wood"

    # Door type
    if re.search(r'triple.layer.*glass', text, re.IGNORECASE):
        data['glass_door_type'] = "Triple layer glass (glass, tempered glass, low-E coating)"
    elif re.search(r'double.layer.*tempered.*glass', text, re.IGNORECASE):
        data['glass_door_type'] = "Double layer tempered glass"
    elif re.search(r'double.*(?:pane|layer).*glass', text, re.IGNORECASE):
        data['glass_door_type'] = "Double pane glass"

    # Door hinge
    if re.search(r'[Rr]eversible [Dd]oor', text):
        data['door_hinge'] = "reversible"
    elif re.search(r'[Rr]ight hinge', text, re.IGNORECASE):
        data['door_hinge'] = "right"

    # Lockable
    data['lockable'] = bool(re.search(r'\block\b', text, re.IGNORECASE))

    # Refrigerant
    m = re.search(r'R600a?\b', text)
    if m:
        data['refrigerant'] = m.group(0)

    # Installation type
    if re.search(r'[Bb]uilt.?[Ii]n', text) and re.search(r'[Ff]reestanding', text):
        data['installation'] = "built-in or freestanding"
    elif re.search(r'[Ff]reestanding [Oo]nly', text):
        data['installation'] = "freestanding"
    elif re.search(r'[Bb]uilt.?[Ii]n', text):
        data['installation'] = "built-in"
    else:
        data['installation'] = "freestanding"

    # Anti-vibration
    data['anti_vibration'] = bool(re.search(r'[Aa]nti.[Vv]ibration', text))

    # Adjustable feet
    m = re.search(r'(\d+)\s*[Aa]djustable\s*(?:front\s*)?feet', text)
    if m:
        data['adjustable_feet'] = int(m.group(1))

    # Cooling system
    if re.search(r'[Cc]ompressor', text):
        data['cooling_system'] = "Compressor"
    elif re.search(r'[Ff]an [Cc]ooling', text):
        data['cooling_system'] = "Fan"

    # Documents (PDFs)
    data['documents'] = []
    for m in re.finditer(r'(https://cdn\.shopify\.com/[^\s]+\.pdf[^\s]*)', text):
        url = m.group(1)
        if 'manual' in url.lower() or '_im_' in url.lower() or 'instruction' in url.lower():
            data['documents'].append({'type': 'manual', 'url': url})
        elif 'spec' in url.lower():
            data['documents'].append({'type': 'spec_sheet', 'url': url})
        else:
            data['documents'].append({'type': 'brochure', 'url': url})

    # Dual zone temp ranges
    if data.get('zones') == 2:
        # Upper zone
        m = re.search(r'(?:upper|top)\s*(?:zone|compartment)[^.]*?(\d+)\s*°?\s*C\s*(?:to|-)\s*(\d+)\s*°?\s*C', text, re.IGNORECASE)
        if m:
            data['zone_upper_min_c'] = int(m.group(1))
            data['zone_upper_max_c'] = int(m.group(2))
        # Lower zone
        m = re.search(r'(?:lower|bottom)\s*(?:zone|compartment)[^.]*?(\d+)\s*°?\s*C\s*(?:to|-)\s*(\d+)\s*°?\s*C', text, re.IGNORECASE)
        if m:
            data['zone_lower_min_c'] = int(m.group(1))
            data['zone_lower_max_c'] = int(m.group(2))

    # Two-door
    data['door_count'] = 2 if re.search(r'[Tt]wo [Dd]oors|[Dd]ouble [Dd]oor\s*design', text) else 1

    return data


def infer_category(data):
    """Determine PIR category."""
    title = data.get('title', '').lower()
    if 'beverage' in title:
        return 'beverage_fridge'
    if 'cellar' in title:
        return 'wine_cellar'
    if 'wine' in title:
        return 'wine_fridge'
    return 'wine_fridge'


def build_name(data):
    """Build a descriptive product name."""
    bottles = data.get('capacity_bottles', '')
    zones = data.get('zones', 1)
    zone_str = "Dual Zone" if zones == 2 else "Single Zone"

    title = data.get('title', '')
    if 'Beverage' in title:
        litres = data.get('capacity_litres', '')
        return f"Beverage Fridge {litres}L {zone_str}"
    if 'Cellar' in title:
        return f"Wine Cellar {bottles} Bottle {zone_str}"

    install = data.get('installation', '')
    if install == "built-in or freestanding":
        install_str = "Built-In/Freestanding"
    elif install == "built-in":
        install_str = "Built-In"
    else:
        install_str = "Freestanding"
    return f"Wine Cabinet {bottles} Bottle {zone_str} {install_str}"


def build_record(data):
    """Build a PIR record from parsed product data."""
    sku = data.get('sku', 'UNKNOWN')
    gtin = data.get('gtin')

    facts = {}

    if data.get('capacity_litres'):
        facts['capacity_litres'] = data['capacity_litres']
    if data.get('capacity_bottles'):
        facts['capacity_bottles'] = data['capacity_bottles']

    dims = data.get('dims', {})
    if dims.get('w'):
        facts['dimensions_exterior_w_mm'] = dims['w']
    if dims.get('d'):
        facts['dimensions_exterior_d_mm'] = dims['d']
    if dims.get('h'):
        facts['dimensions_exterior_h_mm'] = dims['h']

    if data.get('weight_kg'):
        facts['weight_kg'] = data['weight_kg']
    if data.get('noise_db'):
        facts['noise_db'] = data['noise_db']
    if data.get('energy_kwh_annual'):
        facts['energy_consumption_kwh_annual'] = data['energy_kwh_annual']

    if data.get('temp_min_c') is not None:
        facts['internal_temperature_min_c'] = data['temp_min_c']
    if data.get('temp_max_c') is not None:
        facts['internal_temperature_max_c'] = data['temp_max_c']
    if data.get('ambient_max_c'):
        facts['ambient_temperature_max_c'] = data['ambient_max_c']
    if data.get('ambient_min_c'):
        facts['ambient_temperature_min_c'] = data['ambient_min_c']

    facts['temperature_zones'] = data.get('zones', 1)

    if data.get('zones') == 2:
        if data.get('zone_upper_min_c') is not None:
            facts['zone_upper_temp_min_c'] = data['zone_upper_min_c']
            facts['zone_upper_temp_max_c'] = data['zone_upper_max_c']
        if data.get('zone_lower_min_c') is not None:
            facts['zone_lower_temp_min_c'] = data['zone_lower_min_c']
            facts['zone_lower_temp_max_c'] = data['zone_lower_max_c']

    if data.get('shelf_count'):
        facts['shelf_count'] = data['shelf_count']
    if data.get('shelf_material'):
        facts['shelf_material'] = data['shelf_material']

    facts['glass_door'] = True
    if data.get('glass_door_type'):
        facts['glass_door_type'] = data['glass_door_type']

    if data.get('door_hinge'):
        facts['door_hinge'] = data['door_hinge']
    if data.get('door_count', 1) > 1:
        facts['door_count'] = data['door_count']

    facts['led_lighting'] = True
    facts['anti_vibration'] = data.get('anti_vibration', False)
    facts['lockable'] = data.get('lockable', False)

    if data.get('adjustable_feet'):
        facts['adjustable_feet'] = True
        facts['adjustable_feet_count'] = data['adjustable_feet']

    if data.get('refrigerant'):
        facts['refrigerant'] = data['refrigerant']

    if data.get('cooling_system'):
        facts['cooling_system'] = data['cooling_system']

    facts['installation'] = data.get('installation', 'freestanding')
    facts['location'] = ['indoor']

    # Q&A
    qa = []
    if data.get('capacity_bottles'):
        litres_text = f" ({data['capacity_litres']}L)" if data.get('capacity_litres') else ""
        qa.append({
            "q": "What is the capacity?",
            "a": f"{data['capacity_bottles']} Bordeaux bottles{litres_text}.",
            "facts": ["capacity_bottles"] + (["capacity_litres"] if data.get('capacity_litres') else [])
        })
    elif data.get('capacity_litres'):
        qa.append({
            "q": "What is the capacity?",
            "a": f"{data['capacity_litres']} litres.",
            "facts": ["capacity_litres"]
        })

    if data.get('noise_db'):
        qa.append({
            "q": "How noisy is it?",
            "a": f"{data['noise_db']} dB.",
            "facts": ["noise_db"]
        })

    if data.get('energy_kwh_annual'):
        qa.append({
            "q": "What is the energy consumption?",
            "a": f"{data['energy_kwh_annual']} kWh per year.",
            "facts": ["energy_consumption_kwh_annual"]
        })

    zones = data.get('zones', 1)
    if zones == 2:
        zone_text = ""
        if data.get('zone_upper_min_c') is not None:
            zone_text = f" Upper zone: {data['zone_upper_min_c']}-{data['zone_upper_max_c']}°C, lower zone: {data['zone_lower_min_c']}-{data['zone_lower_max_c']}°C."
        qa.append({
            "q": "How many temperature zones does it have?",
            "a": f"Dual zone.{zone_text}",
            "facts": ["temperature_zones"] + (["zone_upper_temp_min_c", "zone_upper_temp_max_c",
                       "zone_lower_temp_min_c", "zone_lower_temp_max_c"] if data.get('zone_upper_min_c') is not None else [])
        })

    if data.get('installation'):
        qa.append({
            "q": "Can it be built in?",
            "a": f"Installation: {data['installation']}.",
            "facts": ["installation"]
        })

    # Documents
    documents = []
    for doc in data.get('documents', []):
        documents.append({
            "type": doc['type'],
            "url": doc['url'],
            "source": "lecavist.com",
            "brand_certified": True
        })

    handle = data['url'].split('/products/')[-1] if '/products/' in data['url'] else ''

    record = {
        "schema": "pir/1.0",
        "gtin": gtin,
        "sku": sku,
        "brand": "Lecavist",
        "name": build_name(data),
        "category": infer_category(data),
        "status": {
            "brand_certified": False,
            "brand_domain": "lecavist.com",
            "certified_date": None,
            "submitted_by": "lecavist.com",
            "submitted_date": "2026-03-05"
        },
        "facts": facts,
        "qa": qa,
        "documents": documents,
        "sellers": [{
            "name": "Lecavist",
            "domain": "lecavist.com",
            "url": data['url'],
            "authorized": True,
            "regions": ["AU"]
        }]
    }

    return record


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    text = read_intake()
    products = split_products(text)

    print(f"Found {len(products)} products in intake file\n")

    created = 0
    pending_gtin = 0
    skipped_exists = 0

    for block in products:
        data = parse_product(block)
        sku = data.get('sku', 'UNKNOWN')
        gtin = data.get('gtin')

        if not gtin:
            # Use SKU as temporary identifier, pending GTIN
            temp_id = f"sku-{sku}"
            data['gtin'] = None
            filepath = os.path.join(RECORDS_DIR, f"{temp_id}.json")
        else:
            # Normalize GTIN (strip leading zeros, pad to 13)
            gtin = gtin.lstrip('0')
            if len(gtin) < 13:
                gtin = gtin.zfill(13)
            data['gtin'] = gtin
            filepath = os.path.join(RECORDS_DIR, f"{gtin}.json")

        if os.path.exists(filepath):
            print(f"  EXISTS {sku:20s} ({gtin})")
            skipped_exists += 1
            continue

        record = build_record(data)

        display_id = data['gtin'] or f"sku-{sku}"
        if args.dry_run:
            print(f"  WOULD CREATE {sku:20s} ({display_id}) — {record['name']}")
            print(f"    Facts: {len(record['facts'])} fields, Q&A: {len(record['qa'])}, Docs: {len(record['documents'])}")
        else:
            with open(filepath, "w") as fh:
                json.dump(record, fh, indent=2, ensure_ascii=False)
                fh.write("\n")
            print(f"  CREATED {sku:20s} ({display_id}) — {record['name']}")

        if not data['gtin']:
            pending_gtin += 1
        created += 1

    print(f"\nCreated: {created}, Pending GTIN: {pending_gtin}, Exists: {skipped_exists}")


if __name__ == "__main__":
    main()
