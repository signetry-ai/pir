#!/usr/bin/env python3
"""Process an intake text file into PIR records.

Usage: python3 scripts/process_intake.py intake/rhino.txt

Reads product data from the intake format, fetches GTINs from Shopify,
and generates PIR-compliant JSON records in records/.
"""

import json
import os
import re
import sys
import urllib.request
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RECORDS_DIR = os.path.join(ROOT, "records")

# ---------------------------------------------------------------------------
# Shopify GTIN lookup
# ---------------------------------------------------------------------------

def fetch_gtin_and_sku(product_url: str) -> tuple[str, str]:
    """Fetch GTIN (barcode) and SKU from Shopify product JSON API."""
    # Extract handle from URL
    handle = product_url.rstrip("/").split("/products/")[-1].split("?")[0]
    base = product_url.split("/products/")[0]
    json_url = f"{base}/products/{handle}.json"
    try:
        req = urllib.request.Request(json_url, headers={"User-Agent": "PIR-Intake/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        variant = data["product"]["variants"][0]
        return variant.get("barcode", ""), variant.get("sku", "")
    except Exception as e:
        print(f"  WARN: Could not fetch GTIN for {handle}: {e}")
        return "", ""


# ---------------------------------------------------------------------------
# Intake parser
# ---------------------------------------------------------------------------

def parse_intake_file(filepath: str) -> list[dict]:
    """Parse an intake file into a list of raw product dicts."""
    with open(filepath) as f:
        content = f.read()

    # Split on --- separator
    sections = re.split(r"\n---\n", content)
    products = []

    for section in sections:
        section = section.strip()
        if not section:
            continue
        # Skip already-done sections
        if "(ALREADY DONE" in section:
            continue
        if "PASTE NEXT PRODUCT URL HERE" in section:
            continue

        # Find the product URL
        url_match = re.search(r"(https://bar-fridges-australia\.com\.au/products/[^\s?]+)", section)
        if not url_match:
            continue

        product_url = url_match.group(1)

        # Extract key-value specs using the tab-separated format
        raw = {}
        raw["_url"] = product_url
        raw["_raw"] = section

        # Extract spec fields
        # Single-line patterns (no DOTALL — match stops at newline)
        single_line = {
            "model_code": r"MODEL CODE:\s*(.+)",
            "body_color": r"BODY COLO[U]?R:\s*\n?(.+)",
            "grill_finish": r"GRILL FINISH:\s*\n?(.+)",
            "interior_finish": r"INTERIOR FINISH:\s*\n?(.+)",
            "door_hinged": r"DOOR HINGED:\s*\n?(.+)",
            "shelving": r"SHELVING:\s*\n?(.+)",
            "glass_door_info": r"GLASS DOOR INFORMATION:\s*\n?(.+)",
            "lockable": r"LOCKABLE:\s*\n?(.+)",
            "adjustable_feet": r"ADJUSTABLE FEET:\s*\n?(.+)",
            "cooling": r"COOLING:\s*\n?(.+)",
            "location": r"LOCATION & SUITABILITY:\s*(.+)",
            "ip_rating": r"ALFRESCO IP RATING:\s*(.+)",
            "energy_star": r"ENERGY STAR RATING:\s*(.+)",
            "running_cost": r"Approximately \$?([\d.]+) per year",
            "running_cost_basis": r"Based on ([\d.]+) cents",
            "noise_db": r"NOISE LEVEL:\s*\n?(\d+)\s*dB",
            "weight": r"WEIGHT:\s*\n?(\d+)\s*kg",
            "exterior_dims": r"Exterior \(WxDxH\):\s*(.+?)mm",
            "internal_dims": r"INTERNAL \(WxDxH\):\s*(.+?)mm",
            "ventilation_top": r"Top:\s*(\d+)\s*mm",
            "ventilation_side": r"Each Side:\s*(\d+)\s*mm",
            "ventilation_rear": r"Rear:\s*(\d+)\s*mm",
            "corona_bottles": r"Corona Bottles:\s*(\d+)",
            "cans_375": r"Standard 375ml Cans:\s*(\d+)",
            "wine_bottles": r"Standard Wine Bottles:\s*(\d+)",
            "litres": r"Litres:\s*(\d+)",
        }
        for key, pattern in single_line.items():
            match = re.search(pattern, section, re.IGNORECASE)
            if match:
                raw[key] = match.group(1).strip()

        # Multi-line patterns (need DOTALL for cross-line matching)
        multi_line = {
            "energy_saving": r"ENERGY SAVING FEATURES:\s*\n(.+?)(?:\n\n|\nADJUSTABLE)",
            "power_consumption": r"(?:POWER CONSUMPTION|kW/24hrs).*?(\d+\.?\d*)\s*kW/24hrs",
            "brand_parts": r"BRAND PARTS USED:\s*\n(.+?)(?:\n\n|\nWEIGHT)",
            "approvals": r"APPROVALS:\s*\n(.+?)(?:\n\n|\nCapacity|\nDimensions)",
            "other_size": r"OTHER SIZE INFORMATION:\s*\n(.+?)(?:\n\n|\nVentilation)",
        }
        for key, pattern in multi_line.items():
            match = re.search(pattern, section, re.DOTALL | re.IGNORECASE)
            if match:
                raw[key] = match.group(1).strip()

        # Extract document URLs
        raw["_doc_urls"] = re.findall(
            r"(https://(?:bar-fridges-australia\.com\.au/cdn/shop/files|brochures\.barfridgesaustralia\.au)/[^\s]+)",
            section,
        )

        if raw.get("model_code"):
            products.append(raw)

    return products


# ---------------------------------------------------------------------------
# Record builder
# ---------------------------------------------------------------------------

def parse_dims(dim_str: str) -> tuple[int, int, int]:
    """Parse '600 x 500 x 840' into (w, d, h)."""
    parts = re.findall(r"\d+", dim_str)
    if len(parts) >= 3:
        return int(parts[0]), int(parts[1]), int(parts[2])
    return 0, 0, 0


def determine_category(raw: dict) -> str:
    """Determine product category from raw data."""
    model = raw.get("model_code", "").upper()
    url = raw.get("_url", "").lower()
    raw_text = raw.get("_raw", "").lower()

    if "TK-" in model or "open front" in url or "open face" in raw_text:
        return "open_display_cooler"
    if "SGT" in model or "upright" in url:
        return "upright_display_fridge"
    if "combo" in model.lower() or "combo" in url:
        return "bar_fridge"
    return "bar_fridge"


def determine_name(raw: dict) -> str:
    """Generate a clean product name."""
    model = raw.get("model_code", "")
    url = raw.get("_url", "")

    # Door count
    doors = 1
    if re.search(r"(2[- ]door|twin|double|2H|2S)", url + model, re.IGNORECASE):
        doors = 2
    elif re.search(r"(3[- ]door|triple|3H|3S)", url + model, re.IGNORECASE):
        doors = 3

    # Door type
    glass_info = raw.get("glass_door_info", "").lower()
    is_heated = "heated" in glass_info
    is_sliding = "sliding" in glass_info or "sliding" in url.lower()
    is_solid = "solid" in glass_info or "-SD" in model
    is_low_e = "low e" in glass_info or "low-e" in glass_info

    # Location
    location = raw.get("location", "").lower()
    is_outdoor = "outdoor" in location or "alfresco" in url.lower()

    # Category
    category = determine_category(raw)

    # Body
    body = raw.get("body_color", "").lower()
    is_stainless = "stainless" in body or "316" in body
    is_black = "black" in body

    # Special types
    if category == "open_display_cooler":
        name = f"Open Display Commercial Cooler"
    elif category == "upright_display_fridge":
        name = f"{doors}-Door Upright Display Fridge"
    else:
        name = f"{doors}-Door"
        if is_outdoor:
            name += " Outdoor"
        name += " Bar Fridge"

    # Qualifiers
    qualifiers = []
    if is_solid:
        qualifiers.append("Solid Door")
    elif is_heated:
        qualifiers.append("Heated Glass")
    elif is_sliding:
        qualifiers.append("Sliding Glass")
    elif is_low_e:
        qualifiers.append("Low-E Glass")

    if qualifiers:
        name += f" ({', '.join(qualifiers)})"

    return name


def build_facts(raw: dict) -> dict:
    """Build the facts{} object from raw data."""
    facts = {}

    # Capacity
    if raw.get("litres"):
        facts["capacity_litres"] = int(raw["litres"])
    if raw.get("cans_375"):
        facts["capacity_375ml_cans"] = int(raw["cans_375"])
    if raw.get("corona_bottles"):
        facts["capacity_330ml_bottles"] = int(raw["corona_bottles"])
    if raw.get("wine_bottles"):
        facts["capacity_wine_bottles_750ml"] = int(raw["wine_bottles"])

    # Dimensions
    if raw.get("exterior_dims"):
        w, d, h = parse_dims(raw["exterior_dims"])
        if w:
            facts["dimensions_exterior_w_mm"] = w
            facts["dimensions_exterior_d_mm"] = d
            facts["dimensions_exterior_h_mm"] = h
    if raw.get("internal_dims"):
        w, d, h = parse_dims(raw["internal_dims"])
        if w:
            facts["dimensions_interior_w_mm"] = w
            facts["dimensions_interior_d_mm"] = d
            facts["dimensions_interior_h_mm"] = h
    if raw.get("other_size"):
        facts["dimensions_note"] = raw["other_size"].strip()

    # Weight
    if raw.get("weight"):
        facts["weight_kg"] = int(raw["weight"])

    # Noise
    if raw.get("noise_db"):
        facts["noise_db"] = int(raw["noise_db"])

    # Energy
    if raw.get("energy_star"):
        try:
            facts["energy_star_rating_au"] = int(raw["energy_star"])
            facts["energy_star_rating_au_note"] = "Australian 1-10 star scale"
        except ValueError:
            pass

    # Power
    if raw.get("power_consumption"):
        try:
            facts["power_consumption_kwh_per_24h"] = float(raw["power_consumption"].strip())
        except ValueError:
            pass
    if raw.get("running_cost"):
        try:
            facts["running_cost_aud_annual"] = float(raw["running_cost"])
        except ValueError:
            pass
    if raw.get("running_cost_basis"):
        try:
            facts["running_cost_basis_cents_per_kwh"] = float(raw["running_cost_basis"])
        except ValueError:
            pass

    # IP Rating
    if raw.get("ip_rating"):
        ip = raw["ip_rating"].strip()
        facts["ip_rating"] = f"IP{ip}" if not ip.startswith("IP") else ip

    # Ambient temp
    cooling = raw.get("cooling", "")
    temp_match = re.search(r"(\d{2})\s*°?C", cooling)
    if temp_match:
        facts["ambient_temperature_max_c"] = int(temp_match.group(1))

    # Internal temp
    if re.search(r"zero|0\s*°?C", cooling, re.IGNORECASE):
        facts["internal_temperature_min_c"] = 0
    temp_min_match = re.search(r"(\d+)-(\d+)\s*°?C", cooling)
    if temp_min_match:
        facts["internal_temperature_min_c"] = int(temp_min_match.group(1))

    # Location
    loc = raw.get("location", "").lower()
    if "outdoor" in loc and "indoor" in loc:
        facts["location"] = ["indoor", "outdoor"]
    elif "outdoor" in loc or "alfresco" in loc:
        facts["location"] = ["indoor", "outdoor"]
    elif "indoor" in loc:
        facts["location"] = ["indoor"]

    # Lockable
    if raw.get("lockable", "").upper().startswith("YES"):
        facts["lockable"] = True

    # Adjustable feet
    feet = raw.get("adjustable_feet", "")
    if "yes" in feet.lower():
        facts["adjustable_feet"] = True
        feet_count = re.search(r"(\d+)", feet)
        if feet_count:
            facts["adjustable_feet_count"] = int(feet_count.group(1))

    # Shelving
    shelving = raw.get("shelving", "")
    shelf_count_match = re.search(r"(\d+)\s*x", shelving)
    if shelf_count_match:
        facts["shelf_count"] = int(shelf_count_match.group(1))
    shelf_w_match = re.search(r"(\d+)mm\s*W", shelving)
    shelf_d_match = re.search(r"(\d+)mm\s*D", shelving)
    if shelf_w_match:
        facts["shelf_w_mm"] = int(shelf_w_match.group(1))
    if shelf_d_match:
        facts["shelf_d_mm"] = int(shelf_d_match.group(1))
    if shelving:
        facts["shelf_type"] = shelving

    # Door hinge
    hinge = raw.get("door_hinged", "")
    if "right" in hinge.lower() and "left" in hinge.lower():
        # Multi-door
        left_count = len(re.findall(r"left", hinge, re.IGNORECASE))
        right_count = len(re.findall(r"right", hinge, re.IGNORECASE))
        facts["door_hinge"] = f"{left_count} x left, {right_count} x right"
    elif "right" in hinge.lower():
        facts["door_hinge"] = "right"
        facts["handle_side"] = "left"
    elif "left" in hinge.lower():
        facts["door_hinge"] = "left"
        facts["handle_side"] = "right"
    elif "sliding" in hinge.lower():
        facts["door_hinge"] = "sliding"

    # Glass door
    glass = raw.get("glass_door_info", "")
    if glass:
        if "solid" in glass.lower():
            facts["glass_door"] = False
            facts["door_type"] = glass.strip()
        else:
            facts["glass_door"] = True
            facts["glass_door_type"] = glass.strip().split("\n")[0]
            if "heated" in glass.lower():
                facts["glass_door_heated_switchable"] = True

    # LED
    raw_text = raw.get("_raw", "").lower()
    if "led" in raw_text:
        facts["led_lighting"] = True
    if "blue" in raw_text and "white" in raw_text:
        facts["led_colour_switchable"] = True
        facts["led_colours"] = ["blue", "white"]
    # Multi-colour nightclub
    if "multi" in raw_text and ("colour" in raw_text or "color" in raw_text or "light" in raw_text):
        if "rgb" in raw_text or "colour" in raw_text or "color" in raw_text:
            facts["led_colour_switchable"] = True

    # Refrigerant
    energy_features = raw.get("energy_saving", "")
    if "R600" in energy_features:
        facts["refrigerant"] = "R600"
        facts["refrigerant_odp"] = 0
        facts["refrigerant_gwp"] = 3
    elif "R290" in energy_features:
        facts["refrigerant"] = "R290"
        facts["refrigerant_odp"] = 0
        facts["refrigerant_gwp"] = 3

    # Body material
    body = raw.get("body_color", "")
    if body:
        facts["body_material"] = body.strip()
    interior = raw.get("interior_finish", "")
    if interior:
        facts["interior_finish"] = interior.strip()
    grill = raw.get("grill_finish", "")
    if grill:
        facts["grill_material"] = grill.strip()

    # Ventilation
    if raw.get("ventilation_top"):
        facts["ventilation_top_mm"] = int(raw["ventilation_top"])
    if raw.get("ventilation_side"):
        facts["ventilation_each_side_mm"] = int(raw["ventilation_side"])
    if raw.get("ventilation_rear"):
        facts["ventilation_rear_mm"] = int(raw["ventilation_rear"])

    # Approvals
    if raw.get("approvals"):
        approvals = [a.strip() for a in raw["approvals"].split(",") if a.strip()]
        if approvals:
            facts["approvals"] = approvals

    # Components from brand parts
    parts = raw.get("brand_parts", "")
    if parts:
        if "GMCC" in parts:
            facts["component_compressor"] = "GMCC"
        elif "Secop" in parts:
            facts["component_compressor"] = "Secop Variable Speed (Japan)"
        elif "LG" in parts:
            facts["component_compressor"] = "LG"

        if "EBM" in parts:
            facts["component_fan_primary"] = "EBM EC Fan (Germany)"
        if "Noctua" in parts:
            facts["component_fan_secondary"] = "Noctua (Norway)"
        elif "Taiwan" in parts and "EC" in parts.upper():
            facts["component_fan_secondary"] = "EC Fan (Taiwan)"

        if "Danfoss" in parts:
            facts["component_controller"] = "Danfoss ECO (Germany)"
        elif "controller" in parts.lower():
            ctrl_match = re.search(r"([\w\s]+)(?:developed\s+)?controller", parts, re.IGNORECASE)
            if ctrl_match:
                facts["component_controller"] = ctrl_match.group(0).strip()

        if "Meanwell" in parts:
            facts["component_transformer"] = "Meanwell (Taiwan)"
        if "Cherry" in parts:
            facts["component_switches"] = "Cherry (USA)"
        if "Philips" in parts:
            facts["component_lighting"] = "Philips LED"

    return facts


def build_qa(facts: dict, raw: dict) -> list[dict]:
    """Generate Q&A pairs based on available facts."""
    qa = []

    # Outdoor suitability
    if facts.get("ip_rating"):
        qa.append({
            "q": "Can it be used outdoors?",
            "a": f"Yes. {facts['ip_rating']} rated for outdoor use."
            + (f" Performs in ambient temperatures up to {facts['ambient_temperature_max_c']}°C+." if facts.get("ambient_temperature_max_c") else ""),
            "facts": [k for k in ["ip_rating", "ambient_temperature_max_c", "location"] if k in facts],
        })
    elif facts.get("location") == ["indoor"]:
        qa.append({
            "q": "Can it be used outdoors?",
            "a": "This unit is designed for indoor or enclosed outdoor use only. It does not have an outdoor IP rating.",
            "facts": ["location"],
        })

    # Lockable
    if facts.get("lockable"):
        qa.append({
            "q": "Is it lockable?",
            "a": "Yes. Includes a key lock.",
            "facts": ["lockable"],
        })

    # Capacity
    if facts.get("capacity_375ml_cans"):
        qa.append({
            "q": "How many cans does it hold?",
            "a": f"{facts['capacity_375ml_cans']} standard 375ml cans.",
            "facts": ["capacity_375ml_cans"],
        })
    if facts.get("capacity_wine_bottles_750ml"):
        qa.append({
            "q": "How many wine bottles does it hold?",
            "a": f"{facts['capacity_wine_bottles_750ml']} standard 750ml wine bottles.",
            "facts": ["capacity_wine_bottles_750ml"],
        })

    # Dimensions
    if facts.get("dimensions_exterior_h_mm"):
        h = facts["dimensions_exterior_h_mm"]
        a = f"The exterior height is {h}mm."
        if h <= 900:
            a += " Standard bench height in Australia is 900mm."
        cite = ["dimensions_exterior_h_mm"]
        if facts.get("ventilation_top_mm"):
            a += f" Ventilation requires {facts['ventilation_top_mm']}mm top, {facts.get('ventilation_each_side_mm', 'N/A')}mm each side, {facts.get('ventilation_rear_mm', 'N/A')}mm rear."
            cite.extend([k for k in ["ventilation_top_mm", "ventilation_each_side_mm", "ventilation_rear_mm"] if k in facts])
        qa.append({
            "q": "Will it fit under a standard bench?",
            "a": a,
            "facts": cite,
        })
    if facts.get("dimensions_exterior_w_mm"):
        qa.append({
            "q": "How wide is it?",
            "a": f"{facts['dimensions_exterior_w_mm']}mm exterior width.",
            "facts": ["dimensions_exterior_w_mm"],
        })

    # Running costs
    if facts.get("running_cost_aud_annual"):
        a = f"Approximately ${facts['running_cost_aud_annual']:.2f} AUD per year"
        if facts.get("running_cost_basis_cents_per_kwh"):
            a += f" based on {facts['running_cost_basis_cents_per_kwh']} cents per kWh"
        a += "."
        qa.append({
            "q": "What are the running costs?",
            "a": a,
            "facts": [k for k in ["running_cost_aud_annual", "running_cost_basis_cents_per_kwh", "power_consumption_kwh_per_24h"] if k in facts],
        })

    # Noise
    if facts.get("noise_db"):
        qa.append({
            "q": "How noisy is it?",
            "a": f"{facts['noise_db']} dB.",
            "facts": ["noise_db"],
        })

    # Energy star
    if facts.get("energy_star_rating_au"):
        qa.append({
            "q": "What is the energy star rating?",
            "a": f"{facts['energy_star_rating_au']} stars on the Australian 1-10 star scale.",
            "facts": ["energy_star_rating_au", "energy_star_rating_au_note"],
        })

    # Condensation (glass door with heated)
    if facts.get("glass_door_heated_switchable"):
        qa.append({
            "q": "Does it get condensation on the glass?",
            "a": "No. It has switchable heated tempered glass. When enabled, it prevents condensation in high humidity environments.",
            "facts": ["glass_door_heated_switchable", "glass_door_type"],
        })

    # Refrigerant
    if facts.get("refrigerant"):
        qa.append({
            "q": "What refrigerant does it use?",
            "a": f"{facts['refrigerant']}. Ozone Depletion Potential: {facts.get('refrigerant_odp', 'N/A')}. Global Warming Potential: {facts.get('refrigerant_gwp', 'N/A')}.",
            "facts": [k for k in ["refrigerant", "refrigerant_odp", "refrigerant_gwp"] if k in facts],
        })

    # Door hinge
    if facts.get("door_hinge"):
        hinge = facts["door_hinge"]
        a = f"{hinge.capitalize()} hinge"
        if facts.get("handle_side"):
            a += f", handle on the {facts['handle_side']}"
        a += "."
        qa.append({
            "q": "Which side is the door hinged?",
            "a": a,
            "facts": [k for k in ["door_hinge", "handle_side"] if k in facts],
        })

    # Approvals
    if facts.get("approvals"):
        qa.append({
            "q": "What approvals does it have?",
            "a": ", ".join(facts["approvals"]) + ".",
            "facts": ["approvals"],
        })

    return qa


def build_record(raw: dict, gtin: str, sku: str) -> dict:
    """Build a complete PIR record from raw intake data."""
    facts = build_facts(raw)
    qa = build_qa(facts, raw)
    category = determine_category(raw)
    name = determine_name(raw)

    # Determine range
    sku_upper = sku.upper()
    if sku_upper.startswith("ENV"):
        product_range = "Envy"
    elif sku_upper.startswith("GSP"):
        product_range = "GSP"
    elif sku_upper.startswith("SGT"):
        product_range = "SGT"
    elif sku_upper.startswith("SG"):
        product_range = "SG"
    elif sku_upper.startswith("TK"):
        product_range = "TK"
    else:
        product_range = None

    record = {
        "schema": "pir/1.0",
        "gtin": gtin,
        "sku": sku,
        "brand": "Rhino",
    }
    if product_range:
        record["range"] = product_range
    record["name"] = name
    record["category"] = category
    record["status"] = {
        "brand_certified": False,
        "brand_domain": None,
        "certified_date": None,
        "submitted_by": "bar-fridges-australia.com.au",
        "submitted_date": str(date.today()),
    }
    record["facts"] = facts
    record["qa"] = qa

    # Documents
    docs = []
    for url in raw.get("_doc_urls", []):
        if "brochure" in url:
            docs.append({"type": "brochure", "url": url, "source": "bar-fridges-australia.com.au", "brand_certified": False})
        elif "manual" in url or "instruction" in url.lower():
            docs.append({"type": "manual", "url": url, "source": "bar-fridges-australia.com.au", "brand_certified": False})
        else:
            docs.append({"type": "spec_sheet", "url": url, "source": "bar-fridges-australia.com.au", "brand_certified": False})
    record["documents"] = docs

    # Sellers
    record["sellers"] = [
        {
            "name": "Bar Fridges Australia",
            "domain": "bar-fridges-australia.com.au",
            "url": raw["_url"],
            "authorized": False,
            "regions": ["AU"],
        }
    ]

    return record


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/process_intake.py intake/rhino.txt")
        sys.exit(1)

    filepath = sys.argv[1]
    if not os.path.isabs(filepath):
        filepath = os.path.join(ROOT, filepath)

    print(f"Parsing {filepath}...")
    products = parse_intake_file(filepath)
    print(f"Found {len(products)} new products to process.\n")

    # Load existing records to skip
    existing = set()
    for f in os.listdir(RECORDS_DIR):
        if f.endswith(".json"):
            existing.add(f.replace(".json", ""))

    created = 0
    skipped = 0
    errors = []

    for raw in products:
        model = raw.get("model_code", "?")
        url = raw["_url"]

        # Fetch GTIN from Shopify
        gtin, sku = fetch_gtin_and_sku(url)
        if not gtin:
            errors.append(f"{model}: Could not fetch GTIN")
            continue
        if not sku:
            sku = model

        # Skip if record exists
        if gtin in existing:
            print(f"  SKIP {sku} ({gtin}) — record exists")
            skipped += 1
            continue

        # Build and write record
        try:
            record = build_record(raw, gtin, sku)
            out_path = os.path.join(RECORDS_DIR, f"{gtin}.json")
            with open(out_path, "w") as f:
                json.dump(record, f, indent=2, ensure_ascii=False)
                f.write("\n")
            print(f"  OK   {sku} ({gtin})")
            created += 1
        except Exception as e:
            errors.append(f"{model} ({gtin}): {e}")
            print(f"  ERR  {model}: {e}")

    print(f"\nDone: {created} created, {skipped} skipped, {len(errors)} errors")
    if errors:
        print("\nErrors:")
        for e in errors:
            print(f"  - {e}")


if __name__ == "__main__":
    main()
