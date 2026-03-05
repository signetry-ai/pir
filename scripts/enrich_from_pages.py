#!/usr/bin/env python3
"""
Enrich PIR skeleton records by scraping product pages from BFA.
Fetches HTML, extracts spec tabs, updates JSON records with missing data.

Usage:
    python scripts/enrich_from_pages.py                    # Enrich all Schmick skeletons
    python scripts/enrich_from_pages.py --gtin 9351886003236  # Enrich one record
    python scripts/enrich_from_pages.py --dry-run          # Show what would change
"""

import re, json, sys, os, time
import urllib.request

def extract_tab(html, tab_id):
    idx = html.find(f'id="{tab_id}"')
    if idx < 0:
        return ''
    chunk = html[idx:idx+5000]
    next_tab = chunk.find('id="v-pills-', 20)
    if next_tab > 0:
        chunk = chunk[:next_tab]
    text = re.sub(r'<[^>]+>', '\n', chunk)
    for ent, repl in [('&amp;','&'),('&nbsp;',' '),('&#39;',"'"),('&deg;','°'),('&ndash;','–'),('&quot;','"')]:
        text = text.replace(ent, repl)
    lines = [l.strip() for l in text.split('\n')
             if l.strip() and len(l.strip()) > 1
             and not l.strip().startswith('d=')
             and not l.strip().startswith('fill')
             and not l.strip().startswith('clip')
             and not l.strip().startswith('stroke')
             and not l.strip().startswith('viewBox')
             and not l.strip().startswith('xmlns')]
    return '\n'.join(lines)


def parse_label_value(text, label):
    """Extract value after a LABEL:\\n pattern, stopping at next label or noise."""
    m = re.search(re.escape(label) + r':\s*\n\s*(.+)', text, re.IGNORECASE)
    if m:
        val = m.group(1).strip()
        # Clean HTML fragments
        if val.startswith('<'):
            return None
        return val
    return None


def parse_specs_from_html(html):
    specs = {}

    feat = extract_tab(html, 'v-pills-main-features')
    tech = extract_tab(html, 'v-pills-technical')
    peace = extract_tab(html, 'v-pills-peace-of-mind')
    dims = extract_tab(html, 'v-pills-dimensions')
    vent = extract_tab(html, 'v-pills-ventilation')

    # === MAIN FEATURES ===
    v = parse_label_value(feat, 'LOCKABLE')
    if v:
        specs['lockable'] = v.upper() in ('YES', 'Y')

    v = parse_label_value(feat, 'GLASS DOOR INFORMATION')
    if v:
        specs['glass_door_type'] = v

    v = parse_label_value(feat, 'DOOR HINGED')
    if v:
        specs['door_hinge'] = v

    v = parse_label_value(feat, 'SHELVING')
    if v:
        specs['shelf_type'] = v

    v = parse_label_value(feat, 'ADJUSTABLE FEET')
    if v:
        specs['adjustable_feet_raw'] = v
        m = re.search(r'(\d+)', v)
        if m:
            specs['adjustable_feet_count'] = int(m.group(1))

    v = parse_label_value(feat, 'ENERGY SAVING FEATURES')
    if v:
        specs['energy_saving'] = v
        m = re.search(r'R\d{3}[a-z]?', v)
        if m:
            specs['refrigerant'] = m.group(0)

    v = parse_label_value(feat, 'BODY COLO')
    if v:
        specs['body_material'] = v

    v = parse_label_value(feat, 'GRILL FINISH')
    if v:
        specs['grill_material'] = v

    v = parse_label_value(feat, 'INTERIOR FINISH')
    if v:
        specs['interior_finish'] = v

    v = parse_label_value(feat, 'MODEL CODE')
    if v:
        specs['model_code'] = v

    # === TECHNICAL ===
    m = re.search(r'ENERGY STAR RATING:\s*\n\s*(\d+)', tech)
    if m:
        specs['energy_star_rating_au'] = int(m.group(1))

    m = re.search(r'(\d+\.?\d*)\s*kW/24hrs', tech)
    if m:
        specs['power_consumption_kwh_per_24h'] = float(m.group(1))

    m = re.search(r'Approximately\s*\$?([\d,.]+)\s*\n\s*per year', tech)
    if m:
        specs['running_cost_aud_annual'] = float(m.group(1).replace(',', ''))

    m = re.search(r'Based on\s*([\d.]+)\s*cents', tech)
    if m:
        specs['running_cost_basis_cents_per_kwh'] = float(m.group(1))

    m = re.search(r'NOISE LEVEL:\s*\n\s*(\d+)\s*\n\s*dB', tech)
    if m:
        specs['noise_db'] = int(m.group(1))

    m = re.search(r'Cools to.*?(\d+)\s*°?\s*C.*?(\d+)\s*°?\s*C', tech)
    if m:
        specs['internal_temperature_min_c'] = int(m.group(1))
        specs['ambient_temperature_max_c'] = int(m.group(2))

    v = parse_label_value(tech, 'LOCATION')
    if v:
        loc = []
        vl = v.lower()
        if 'indoor' in vl:
            loc.append('indoor')
        if 'outdoor' in vl or 'alfresco' in vl:
            loc.append('outdoor')
        if loc:
            specs['location'] = loc

    v = parse_label_value(tech, 'BRAND PARTS USED')
    if v:
        specs['brand_parts'] = v

    m = re.search(r'WEIGHT:\s*\n\s*(\d+\.?\d*)\s*kg', tech)
    if m:
        wt = float(m.group(1))
        specs['weight_kg'] = int(wt) if wt == int(wt) else wt

    # === PEACE OF MIND ===
    v = parse_label_value(peace, 'APPROVALS')
    if v:
        specs['approvals'] = [a.strip() for a in v.split(',') if a.strip()]

    # === DIMENSIONS ===
    m = re.search(r'Exterior\s*\n\s*\(WxDxH\)\s*\n\s*(\d+)\s*x\s*\n\s*(\d+)\s*x\s*\n\s*(\d+)\s*mm', dims)
    if m:
        specs['dimensions_exterior_w_mm'] = int(m.group(1))
        specs['dimensions_exterior_d_mm'] = int(m.group(2))
        specs['dimensions_exterior_h_mm'] = int(m.group(3))

    m = re.search(r'INTERNAL\s*\n\s*\(WxDxH\)\s*\n\s*(\d+)\s*x\s*\n\s*(\d+)\s*x\s*\n\s*(\d+)\s*mm', dims)
    if m:
        specs['dimensions_interior_w_mm'] = int(m.group(1))
        specs['dimensions_interior_d_mm'] = int(m.group(2))
        specs['dimensions_interior_h_mm'] = int(m.group(3))

    # === VENTILATION ===
    m = re.search(r'Top:\s*\n\s*(\d+)\s*\n\s*mm', vent)
    if m:
        specs['ventilation_top_mm'] = int(m.group(1))

    m = re.search(r'Each Side:\s*\n\s*(\d+)\s*\n\s*mm', vent)
    if m:
        specs['ventilation_each_side_mm'] = int(m.group(1))

    m = re.search(r'Rear:\s*\n\s*(\d+)\s*\n\s*mm', vent)
    if m:
        specs['ventilation_rear_mm'] = int(m.group(1))

    return specs


def parse_components(brand_parts_str):
    """Parse brand parts string into component facts."""
    components = {}
    parts = brand_parts_str.lower()

    if 'jiaxipera' in parts:
        components['component_compressor'] = 'Jiaxipera'
    elif 'gmcc' in parts:
        components['component_compressor'] = 'GMCC'

    if 'meanwell' in parts:
        components['component_transformer'] = 'Meanwell (Taiwan)'

    if 'noctua' in parts:
        components['component_fan_secondary'] = 'Noctua (Silent)'
    if 'ebm' in parts:
        components['component_fan_primary'] = 'EBM (Germany)'
    if 'schmick' in parts and 'fan' in parts:
        if 'component_fan_primary' not in components:
            components['component_fan_primary'] = 'Schmick quiet running fans'

    if 'schmick eco' in parts:
        components['component_controller'] = 'Schmick ECO Controller'

    return components


def enrich_record(record, page_specs):
    """Merge page-extracted specs into existing record facts."""
    facts = record.get('facts', {})
    changes = []

    # Direct mappings - only update if missing or page has better data
    direct_maps = {
        'lockable': 'lockable',
        'glass_door_type': 'glass_door_type',
        'noise_db': 'noise_db',
        'weight_kg': 'weight_kg',
        'power_consumption_kwh_per_24h': 'power_consumption_kwh_per_24h',
        'running_cost_aud_annual': 'running_cost_aud_annual',
        'running_cost_basis_cents_per_kwh': 'running_cost_basis_cents_per_kwh',
        'energy_star_rating_au': 'energy_star_rating_au',
        'ambient_temperature_max_c': 'ambient_temperature_max_c',
        'internal_temperature_min_c': 'internal_temperature_min_c',
        'body_material': 'body_material',
        'interior_finish': 'interior_finish',
        'grill_material': 'grill_material',
        'door_hinge': 'door_hinge',
        'dimensions_exterior_w_mm': 'dimensions_exterior_w_mm',
        'dimensions_exterior_d_mm': 'dimensions_exterior_d_mm',
        'dimensions_exterior_h_mm': 'dimensions_exterior_h_mm',
        'dimensions_interior_w_mm': 'dimensions_interior_w_mm',
        'dimensions_interior_d_mm': 'dimensions_interior_d_mm',
        'dimensions_interior_h_mm': 'dimensions_interior_h_mm',
        'ventilation_top_mm': 'ventilation_top_mm',
        'ventilation_each_side_mm': 'ventilation_each_side_mm',
        'ventilation_rear_mm': 'ventilation_rear_mm',
        'location': 'location',
        'approvals': 'approvals',
        'refrigerant': 'refrigerant',
        'shelf_type': 'shelf_type',
    }

    for page_key, fact_key in direct_maps.items():
        if page_key in page_specs:
            old = facts.get(fact_key)
            new = page_specs[page_key]
            if old is None:
                facts[fact_key] = new
                changes.append(f'  + {fact_key}: {new}')
            elif old != new and fact_key not in ('lockable',):
                # Page data overrides feed skeleton for most fields
                facts[fact_key] = new
                changes.append(f'  ~ {fact_key}: {old} -> {new}')

    # Heated glass detection from glass_door_type
    gdt = facts.get('glass_door_type', '').lower()
    if 'heated' in gdt and not facts.get('glass_door_heated_switchable'):
        facts['glass_door_heated_switchable'] = True
        changes.append('  + glass_door_heated_switchable: True')

    # Components from brand parts
    if 'brand_parts' in page_specs:
        components = parse_components(page_specs['brand_parts'])
        for ck, cv in components.items():
            if ck not in facts:
                facts[ck] = cv
                changes.append(f'  + {ck}: {cv}')

    # Energy star note if rating present
    if 'energy_star_rating_au' in facts and 'energy_star_rating_au_note' not in facts:
        facts['energy_star_rating_au_note'] = 'Australian 1-10 star scale'
        changes.append('  + energy_star_rating_au_note')

    # Adjustable feet
    if 'adjustable_feet_count' in page_specs:
        facts['adjustable_feet'] = True
        facts['adjustable_feet_count'] = page_specs['adjustable_feet_count']

    record['facts'] = facts

    # Enrich Q&A if we have new data
    existing_qs = {qa['q'] for qa in record.get('qa', [])}
    qa = record.get('qa', [])

    if 'running_cost_aud_annual' in facts and 'What are the running costs?' in existing_qs:
        # Update existing running cost Q&A with full answer
        for q in qa:
            if q['q'] == 'What are the running costs?':
                cost = facts['running_cost_aud_annual']
                basis = facts.get('running_cost_basis_cents_per_kwh', 25.64)
                q['a'] = f'Approximately ${cost:.2f} AUD per year based on {basis} cents per kWh.'
                q['facts'] = ['running_cost_aud_annual', 'running_cost_basis_cents_per_kwh', 'power_consumption_kwh_per_24h']

    if 'ventilation_top_mm' in facts:
        for q in qa:
            if q['q'] == 'Will it fit under a standard bench?':
                h = facts.get('dimensions_exterior_h_mm', '?')
                q['a'] = f'Exterior height is {h}mm. Standard Australian bench height is 900mm. Ventilation requires {facts.get("ventilation_top_mm", "?")}mm top, {facts.get("ventilation_each_side_mm", "?")}mm each side, {facts.get("ventilation_rear_mm", "?")}mm rear.'
                q['facts'] = ['dimensions_exterior_h_mm', 'ventilation_top_mm', 'ventilation_each_side_mm', 'ventilation_rear_mm']

    if 'refrigerant' in facts and 'What refrigerant does it use?' not in existing_qs:
        qa.append({
            'q': 'What refrigerant does it use?',
            'a': f'{facts["refrigerant"]}.',
            'facts': ['refrigerant']
        })

    if 'energy_star_rating_au' in facts and 'What is the energy star rating?' not in existing_qs:
        qa.append({
            'q': 'What is the energy star rating?',
            'a': f'{facts["energy_star_rating_au"]} stars on the Australian 1-10 star scale.',
            'facts': ['energy_star_rating_au', 'energy_star_rating_au_note']
        })

    if 'approvals' in facts and 'What approvals does it have?' not in existing_qs:
        qa.append({
            'q': 'What approvals does it have?',
            'a': ', '.join(facts['approvals']) + '.',
            'facts': ['approvals']
        })

    record['qa'] = qa
    return record, changes


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--gtin', help='Enrich specific GTIN only')
    parser.add_argument('--dry-run', action='store_true', help='Show changes without writing')
    parser.add_argument('--brand', default='Schmick', help='Brand to filter')
    args = parser.parse_args()

    records_dir = 'records'
    enriched = 0
    errors = 0

    for f in sorted(os.listdir(records_dir)):
        if not f.endswith('.json'):
            continue

        gtin = f.replace('.json', '')
        if args.gtin and gtin != args.gtin:
            continue

        filepath = os.path.join(records_dir, f)
        with open(filepath) as fh:
            record = json.load(fh)

        if record.get('brand') != args.brand:
            continue

        # Get seller URL to fetch
        seller_url = None
        for s in record.get('sellers', []):
            if s.get('url'):
                seller_url = s['url']
                break

        if not seller_url:
            print(f'SKIP {gtin} ({record.get("sku")}): no seller URL')
            continue

        sku = record.get('sku', '')
        print(f'Fetching {sku} ({gtin})...', end=' ', flush=True)

        try:
            req = urllib.request.Request(seller_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode('utf-8', errors='replace')

            page_specs = parse_specs_from_html(html)
            record, changes = enrich_record(record, page_specs)

            if changes:
                print(f'{len(changes)} updates')
                for c in changes:
                    print(c)
                if not args.dry_run:
                    with open(filepath, 'w') as fh:
                        json.dump(record, fh, indent=2, ensure_ascii=False)
                        fh.write('\n')
                enriched += 1
            else:
                print('no changes')

            time.sleep(0.3)  # Be polite

        except Exception as e:
            print(f'ERROR: {e}')
            errors += 1

    print(f'\nEnriched: {enriched}, Errors: {errors}')


if __name__ == '__main__':
    main()
