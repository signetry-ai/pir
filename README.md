# Signetry PIR — Product Intelligence Records

An open registry of structured product facts. Every record is a GTIN-indexed JSON file containing verified specs, pre-answered questions, and authorized sellers.

**368 products** across 7 brands and 10 categories. CC0 licensed.

## Access the data

**Single record (by GTIN):**
```bash
curl https://raw.githubusercontent.com/signetry/pir/main/records/9351886000266.json
```

**Full catalog index:**
```bash
curl https://raw.githubusercontent.com/signetry/pir/main/catalog.json
```

**AI agents:** See [`llms.txt`](llms.txt) for a structured overview of all products, access patterns, and trust model.

**Browse locally:** `records/{gtin}.json`

## What's in a record

```json
{
  "schema": "pir/1.0",
  "gtin": "9351886000266",
  "sku": "ENV1R-SS",
  "brand": "Rhino",
  "name": "1-Door Outdoor Bar Fridge",
  "category": "bar_fridge",
  "status": { "brand_certified": false, "submitted_by": "barfridgesaustralia.com.au" },
  "facts": { "capacity_litres": 129, "weight_kg": 55, "noise_db": 38 },
  "qa": [{ "q": "How noisy is it?", "a": "38 dB.", "facts": ["noise_db"] }],
  "documents": [{ "type": "spec_sheet", "url": "..." }],
  "sellers": [{ "name": "Bar Fridges Australia", "domain": "barfridgesaustralia.com.au" }]
}
```

- **facts{}** — structured specs with unit-in-key naming (`capacity_litres`, `weight_kg`, `noise_db`)
- **qa[]** — pre-answered questions for AI agents, each citing its source facts
- **sellers[]** — who sells it, with brand authorization state
- **documents[]** — links to spec sheets, manuals, brochures

## Trust model

| `status.brand_certified` | Meaning |
|---|---|
| `false` | Submitted by a retailer or contributor. Source is recorded in `submitted_by`. |
| `true` | Brand verified via DNS domain ownership. Facts are brand-approved. |

AI agents: prefer `brand_certified: true` records for high-stakes queries. Uncertified records are honest about their source and useful as a starting point.

## Registry contents

### By brand

| Brand | Products | Notes |
|---|---|---|
| Schmick | 294 | Includes 121 branded/wrapped variants (CUB, Holden, Fuel Pump, etc.) |
| Rhino | 47 | Outdoor commercial bar fridges |
| Lecavist | 20 | Wine cabinets and beverage fridges (9 pending GTINs) |
| Dellcool | 2 | OEM by Schmick |
| Dellware | 2 | OEM by Schmick |
| IC COLD | 2 | OEM by Schmick |
| Bar Fridges Australia | 1 | House brand accessories |

### By category

| Category | Count |
|---|---|
| bar_fridge | 303 |
| wine_fridge | 35 |
| portable_fridge | 7 |
| integrated_fridge | 7 |
| commercial_fridge | 4 |
| beverage_fridge | 3 |
| upright_display_fridge | 3 |
| open_display_cooler | 3 |
| freezer | 2 |
| wine_cellar | 1 |

### Branded/wrapped products

Some Schmick-manufactured fridges are sold with licensed brand wraps (e.g., Carlton Draught, Victoria Bitter, Corona). These records include:

```json
{
  "manufacturer": "Schmick",
  "brand": "Schmick",
  "base_model": "BC46B",
  "branding": {
    "type": "licensed_wrap",
    "wrap_brand": "Carlton Draught",
    "licensor": "CUB"
  }
}
```

Branding types: `licensed_wrap`, `sub_brand`, `oem`, `house_brand`.

## Add a record

1. Find the GTIN (EAN-13 barcode number — 13 digits)
2. Copy any existing record as a template
3. Fill in `facts{}`, `qa[]`, `sellers[]`, `documents[]`
4. Set `status.submitted_by` to your domain, `status.brand_certified: false`
5. Submit a PR — CI validates against the schema automatically

Filename must match the GTIN exactly: `{gtin}.json`

Products without GTINs use `sku-{SKU}.json` with `"gtin": null`.

## Brand certification

Brands can certify their own records:

1. Add a DNS TXT record to your brand domain: `pir-verify=<your-token>`
2. Open an issue with your brand domain and list of GTINs
3. We verify domain ownership and set `brand_certified: true`

Once certified, only you can update your records.

## Schema

Full schema: [`schema/pir.v1.json`](schema/pir.v1.json)

**Naming conventions for `facts{}`:**

| Convention | Example |
|---|---|
| Units in key | `capacity_litres`, `weight_kg`, `noise_db` |
| Classification codes as strings | `ip_rating: "IP24"` |
| Market suffix for regional ratings | `energy_star_rating_au: 8` |
| Currency in key | `running_cost_aud_annual` |
| Prose qualifications | append `_note` — `power_consumption_note` |
| Component suppliers | `component_compressor`, `component_fan_primary` |

Values are `string`, `number`, `boolean`, or `array of strings`.

## Validate locally

```bash
pip install jsonschema
python scripts/validate.py
```

## Known data gaps

- 9 Lecavist products pending GTINs (stored as `sku-{SKU}.json`)
- 3 Lecavist products missing energy/refrigerant data
- 2 Schmick product pages returned 404 (SK116R-SS, SK126L-SD)
- Some products missing `capacity_litres` — source pages don't include volume data

---

Maintained by [Signetry](https://signetry.ai). License: [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/). Contributions welcome.
