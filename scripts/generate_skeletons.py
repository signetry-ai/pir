#!/usr/bin/env python3
"""
Generate PIR skeleton records from BFA product feed.
Skeletons contain feed data (capacity, dimensions, weight, noise, etc.)
and are then enriched by enrich_from_pages.py with product page data.

Usage:
    python scripts/generate_skeletons.py                     # All brands, skip existing
    python scripts/generate_skeletons.py --brand Schmick     # One brand
    python scripts/generate_skeletons.py --dry-run           # Preview only
"""

import json, sys, os, re
import urllib.request


FEED_URL = "https://feed.barfridgesaustralia.au/api/v1/bfa/company/174752036"
RECORDS_DIR = "records"


def fetch_feed():
    req = urllib.request.Request(FEED_URL, headers={"User-Agent": "PIR/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def categorize(sku, name):
    """Classify product by SKU/name into a category."""
    name_l = name.lower()

    # Branded/novelty wraps
    branded_prefixes = ["BC46B", "BC46W", "BC70B", "SC372"]
    branded_suffixes = ["-LWF", "-LWF2", "-NED", "-JOKER", "-CASTROL", "-FLEECE", "-BVU"]
    branded_exact = ["HUS-BC70B-BB", "HUS-SC70-B-X", "SC70-B-LWF", "SC70-B-LWF2",
                     "SC70-SS-NED", "SC88-SS-NED"]
    if any(sku.startswith(p) for p in branded_prefixes):
        return "branded_novelty"
    if any(sku.endswith(s) for s in branded_suffixes):
        return "branded_novelty"
    if sku in branded_exact:
        return "branded_novelty"
    if "SS-P160FA-" in sku:
        return "branded_novelty"

    if sku.startswith(("YF-", "SK-BDC", "PG-", "RF-")):
        return "portable"
    if sku in ("SD36", "BD36"):
        return "freezer"
    if sku.startswith(("MC", "MS")):
        return "integrated"
    if sku.startswith(("HUS-C", "HUS-F")) or "SC700" in sku:
        return "commercial"
    if sku.startswith("JC") or "wine" in name_l:
        return "wine_fridge"
    if sku.startswith(("BD425D", "BD425W", "BD425LW")):
        return "wine_fridge"
    if sku.startswith("BD425"):
        return "upright"
    if sku.startswith(("SK168", "SK220", "SK422", "SK668", "SS-P160FA")):
        return "upright"
    if sku.startswith(("SK190", "SK206", "SK386")):
        return "multi_door"
    if sku.startswith(("SK86", "SK116", "SK126", "SK146", "SK156", "SK198", "SK228", "SK245", "SK246")):
        return "under_bench"
    if sku.startswith(("SK68", "SK118")):
        return "bar_fridge"
    if sku.startswith(("HUS-SC88", "HUS-SC70-SS", "HUS-SC70L", "HUS-EX")):
        return "outdoor_bar_fridge"
    return "bar_fridge"


CATEGORY_TO_PIR = {
    "bar_fridge": "bar_fridge",
    "outdoor_bar_fridge": "bar_fridge",
    "under_bench": "bar_fridge",
    "multi_door": "bar_fridge",
    "upright": "bar_fridge",
    "wine_fridge": "wine_fridge",
    "commercial": "commercial_fridge",
    "integrated": "integrated_fridge",
    "freezer": "freezer",
    "portable": "portable_fridge",
    "branded_novelty": "bar_fridge",
}

TYPE_NAMES = {
    "under_bench": "Under Bench Bar Fridge",
    "bar_fridge": "Bar Fridge",
    "outdoor_bar_fridge": "Outdoor Bar Fridge",
    "multi_door": "Bar Fridge",
    "upright": "Upright Fridge",
    "wine_fridge": "Wine Fridge",
    "commercial": "Commercial Fridge",
    "integrated": "Integrated Fridge",
    "freezer": "Freezer",
    "portable": "Portable Fridge",
    "branded_novelty": "Bar Fridge",
}


def infer_range(sku):
    for prefix in ["SK", "HUS", "EC", "JC", "BD", "BC", "SC", "SS", "MC", "MS", "YF", "PG", "RF", "SD"]:
        if sku.startswith(prefix):
            return prefix
    return "Other"


def parse_hinge(hinge_str):
    if not hinge_str:
        return "right"
    h = hinge_str.lower()
    if "2 x left" in h:
        return "2 x left, 1 x right"
    if "left" in h and "right" in h:
        return "1 x left, 1 x right"
    if "left" in h:
        return "left"
    return "right"


def infer_door_count(sku):
    if any(x in sku for x in ["386", "3H", "3S", "Combo3"]):
        return "3-Door"
    if any(x in sku for x in ["206", "246", "245", "190", "COMBO", "2H", "2S", "198", "228"]):
        return "2-Door"
    return "1-Door"


def infer_variant(sku, name):
    name_l = name.lower()
    if "-SD" in sku:
        return "(Solid Door)"
    if "-HD" in sku or "heated" in name_l:
        return "(Heated Glass)"
    if "triple glazed" in name_l:
        return "(Triple Glazed)"
    return ""


def build_record(item, cat):
    sku = item["product_code"]
    gtin = str(item["gtin"])
    tech = item.get("technical", {}) or {}
    feat = item.get("main_features", {}) or {}
    cap = item.get("capacity", {}) or {}
    handle = item.get("handle", "")

    # Parse numeric fields
    power_kwh = None
    ps = tech.get("power_consumption", "")
    if ps:
        m = re.search(r"([\d.]+)", ps)
        if m:
            power_kwh = float(m.group(1))

    noise_db = None
    ns = tech.get("noise_level", "")
    if ns:
        m = re.search(r"([\d.]+)", ns)
        if m:
            noise_db = float(m.group(1))
            if noise_db == int(noise_db):
                noise_db = int(noise_db)

    # Location
    suit = tech.get("suitability", "")
    location = []
    if suit:
        if "indoor" in suit.lower():
            location.append("indoor")
        if "alfresco" in suit.lower() or "outdoor" in suit.lower():
            location.append("outdoor")
    if not location:
        location = ["indoor"]

    is_solid = "-SD" in sku
    heated = "-HD" in sku or "heated" in item.get("product_name", "").lower()

    # Build facts
    facts = {}
    if cap.get("litres"):
        facts["capacity_litres"] = cap["litres"]
    if cap.get("cans") and cap["cans"] > 0:
        facts["capacity_375ml_cans"] = cap["cans"]
    if item.get("width"):
        facts["dimensions_exterior_w_mm"] = int(float(item["width"]))
    if item.get("depth"):
        facts["dimensions_exterior_d_mm"] = int(float(item["depth"]))
    if item.get("height"):
        facts["dimensions_exterior_h_mm"] = int(float(item["height"]))
    if item.get("weight"):
        w = float(item["weight"])
        facts["weight_kg"] = int(w) if w == int(w) else w
    if noise_db:
        facts["noise_db"] = noise_db
    if power_kwh:
        facts["power_consumption_kwh_per_24h"] = power_kwh
    max_temp = tech.get("max_outside_temperature")
    if max_temp:
        facts["ambient_temperature_max_c"] = int(max_temp)
    facts["location"] = location
    # Feed says lockable=No on most products but product pages confirm YES.
    # Default to True — enrich_from_pages.py will verify from the actual page.
    facts["lockable"] = True

    feet = feat.get("adjustable_feet")
    if feet and feet != "null":
        facts["adjustable_feet"] = True
        try:
            facts["adjustable_feet_count"] = int(feet)
        except ValueError:
            pass

    facts["door_hinge"] = parse_hinge(item.get("hinge", ""))

    if not is_solid:
        facts["glass_door"] = True
        if heated:
            facts["glass_door_heated_switchable"] = True
        facts["led_lighting"] = True
    else:
        facts["glass_door"] = False

    body = feat.get("body_color", "")
    if body:
        facts["body_material"] = body
    interior = feat.get("interior_finish", "")
    if interior:
        facts["interior_finish"] = interior
    grill = feat.get("door_grill_finish", "")
    if grill:
        facts["grill_material"] = grill

    # Name
    doors = infer_door_count(sku)
    base = TYPE_NAMES.get(cat, "Bar Fridge")
    variant = infer_variant(sku, item.get("product_name", ""))
    name = f"{doors} {base} {variant}".strip()

    # Q&A
    qa = []
    if cap.get("litres"):
        cans_text = f", holds {cap['cans']} standard 375ml cans" if cap.get("cans") and cap["cans"] > 0 else ""
        qa.append({
            "q": "What is the capacity?",
            "a": f"{cap['litres']} litres{cans_text}.",
            "facts": ["capacity_litres"] + (["capacity_375ml_cans"] if cap.get("cans") and cap["cans"] > 0 else [])
        })
    qa.append({"q": "Is it lockable?", "a": "Yes. Includes a key lock.", "facts": ["lockable"]})
    if noise_db:
        qa.append({"q": "How noisy is it?", "a": f"{noise_db} dB.", "facts": ["noise_db"]})
    if power_kwh:
        qa.append({"q": "What are the running costs?", "a": f"Power consumption is {power_kwh} kWh per 24 hours.", "facts": ["power_consumption_kwh_per_24h"]})

    return {
        "schema": "pir/1.0",
        "gtin": gtin,
        "sku": sku,
        "brand": item.get("brand", "Schmick"),
        "range": infer_range(sku),
        "name": name,
        "category": CATEGORY_TO_PIR.get(cat, "bar_fridge"),
        "status": {
            "brand_certified": False,
            "brand_domain": None,
            "certified_date": None,
            "submitted_by": "bar-fridges-australia.com.au",
            "submitted_date": "2026-03-05"
        },
        "facts": facts,
        "qa": qa,
        "documents": [{
            "type": "brochure",
            "url": item.get("brochure_url", ""),
            "source": "bar-fridges-australia.com.au",
            "brand_certified": False
        }],
        "sellers": [{
            "name": "Bar Fridges Australia",
            "domain": "bar-fridges-australia.com.au",
            "url": f"https://bar-fridges-australia.com.au/products/{handle}" if handle else "",
            "authorized": False,
            "regions": ["AU"]
        }]
    }


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--brand", help="Filter by brand name")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    feed = fetch_feed()
    created = 0
    skipped = 0
    gtin_seen = set()
    dupes = 0

    for item in sorted(feed, key=lambda x: x.get("product_code", "")):
        if not item.get("active"):
            continue
        if args.brand and item.get("brand", "").lower() != args.brand.lower():
            continue

        gtin = str(item.get("gtin", ""))
        sku = item.get("product_code", "")
        if not gtin or len(gtin) < 10:
            continue

        filepath = os.path.join(RECORDS_DIR, f"{gtin}.json")
        if os.path.exists(filepath):
            skipped += 1
            continue

        if gtin in gtin_seen:
            print(f"DUPE {sku}: GTIN {gtin} already used by another product")
            dupes += 1
            continue
        gtin_seen.add(gtin)

        cat = categorize(sku, item.get("product_name", ""))
        record = build_record(item, cat)

        if args.dry_run:
            print(f"WOULD CREATE {gtin} ({sku:25s}) [{cat}] {record['name']}")
        else:
            with open(filepath, "w") as fh:
                json.dump(record, fh, indent=2, ensure_ascii=False)
                fh.write("\n")
            print(f"CREATED {gtin} ({sku:25s}) [{cat}] {record['name']}")

        created += 1

    print(f"\nCreated: {created}, Skipped (exists): {skipped}, Dupes: {dupes}")


if __name__ == "__main__":
    main()
