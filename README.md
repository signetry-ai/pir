# Signetry PIR — Product Intelligence Records

An open registry of structured product facts. Every record is a GTIN-indexed JSON file containing verified specs, pre-answered questions, and authorized sellers.

## Look up a product

```bash
curl https://pir.signetry.ai/records/9351886000266.json
```

Or browse: `records/{gtin}.json`

## What's in a record

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

## Add a record

1. Find the GTIN (EAN-13 barcode number — 13 digits)
2. Copy `records/9351886000266.json` as a template
3. Fill in `facts{}`, `qa[]`, `sellers[]`, `documents[]`
4. Set `status.submitted_by` to your domain, `status.brand_certified: false`
5. Submit a PR — CI validates against the schema automatically

Filename must match the GTIN exactly: `{gtin}.json`

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

## Records (43 products)

### Rhino Envy (7)

| GTIN | SKU | Name |
|---|---|---|
| [9351886000266](records/9351886000266.json) | ENV1R-SS | 1-Door Outdoor Bar Fridge |
| [9351886001324](records/9351886001324.json) | ENV1L-SS | 1-Door Outdoor Bar Fridge (Left Hinge) |
| [9351886000259](records/9351886000259.json) | ENV1R-SD | 1-Door Outdoor Bar Fridge (Solid Door) |
| [9351886001263](records/9351886001263.json) | ENV1L-SD | 1-Door Outdoor Bar Fridge (Solid Door, Left Hinge) |
| [9351886000273](records/9351886000273.json) | ENV2H-SS | 2-Door Outdoor Bar Fridge |
| [9351886003205](records/9351886003205.json) | ENV2H-SD | 2-Door Outdoor Bar Fridge (Solid Door) |
| [9351886001331](records/9351886001331.json) | ENV3H-SS | 3-Door Outdoor Bar Fridge |

### Rhino GSP (7)

| GTIN | SKU | Name |
|---|---|---|
| [5060482000320](records/5060482000320.json) | GSP1H-SS | 1-Door Outdoor Bar Fridge (Low-E Glass) |
| [5060482000337](records/5060482000337.json) | GSP1HL-SS | 1-Door Outdoor Bar Fridge (Low-E Glass) |
| [5060482000382](records/5060482000382.json) | GSP1H-840-SS | 1-Door Outdoor Bar Fridge (Low-E Glass) |
| [9351886000280](records/9351886000280.json) | GSP1H-840-BW | 1-Door Outdoor Bar Fridge (Low-E Glass) |
| [5060482000344](records/5060482000344.json) | GSP2H-SS | 2-Door Outdoor Bar Fridge (Low-E Glass) |
| [5060482000405](records/5060482000405.json) | GSP2H-840-SS | 2-Door Outdoor Bar Fridge (Low-E Glass) |
| [5060482000351](records/5060482000351.json) | GSP3H-SS | 3-Door Outdoor Bar Fridge (Low-E Glass) |

### Rhino SG (22)

| GTIN | SKU | Name |
|---|---|---|
| [5060482000429](records/5060482000429.json) | SG1R-B | 1-Door Outdoor Bar Fridge (Low-E Glass) |
| [5060482000436](records/5060482000436.json) | SG1L-B | 1-Door Outdoor Bar Fridge (Low-E Glass) |
| [9351886001300](records/9351886001300.json) | SG1R-NC | 1-Door Outdoor Bar Fridge (Low-E Glass) |
| [9351886001317](records/9351886001317.json) | SG1L-NC | 1-Door Outdoor Bar Fridge (Low-E Glass) |
| [9351886001645](records/9351886001645.json) | SG1R-BQ | 1-Door Outdoor Bar Fridge (Low-E Glass) |
| [9351886004752](records/9351886004752.json) | SG1L-BQ | 1-Door Outdoor Bar Fridge (Low-E Glass) |
| [9351886000945](records/9351886000945.json) | SG1Q-Combo | 1-Door Outdoor Bar Fridge (Low-E Glass) |
| [5060482000580](records/5060482000580.json) | SG1R-SD | 1-Door Outdoor Bar Fridge (Solid Door) |
| [5060482000597](records/5060482000597.json) | SG1L-SD | 1-Door Outdoor Bar Fridge (Solid Door) |
| [5060482000627](records/5060482000627.json) | SG1R-HD | 1-Door Outdoor Bar Fridge (Heated Glass) |
| [5060482000634](records/5060482000634.json) | SG1L-HD | 1-Door Outdoor Bar Fridge (Heated Glass) |
| [9351886007845](records/9351886007845.json) | SG1R-B-HD | 1-Door Outdoor Bar Fridge (Heated Glass) |
| [9351886007838](records/9351886007838.json) | SG1L-B-HD | 1-Door Outdoor Bar Fridge (Heated Glass) |
| [9351886003465](records/9351886003465.json) | SG1L-HDQ | 1-Door Outdoor Bar Fridge (Heated Glass) |
| [5060482000443](records/5060482000443.json) | SG2H-B | 2-Door Outdoor Bar Fridge (Low-E Glass) |
| [9351886001669](records/9351886001669.json) | SG2H-NC | 2-Door Outdoor Bar Fridge (Low-E Glass) |
| [5060482000450](records/5060482000450.json) | SG2S-B | 2-Door Outdoor Bar Fridge (Sliding Glass) |
| [5060482000641](records/5060482000641.json) | SG2H-HD | 2-Door Outdoor Bar Fridge (Heated Glass) |
| [9351886006350](records/9351886006350.json) | SG2H-B-HD | 2-Door Outdoor Bar Fridge (Heated Low-E Glass) |
| [5060482000467](records/5060482000467.json) | SG3H-B | 3-Door Outdoor Bar Fridge (Low-E Glass) |
| [5060482000474](records/5060482000474.json) | SG3S-B | 3-Door Outdoor Bar Fridge (Sliding Glass) |
| [5060482003611](records/5060482003611.json) | SG3H-HD | 3-Door Outdoor Bar Fridge (Heated Glass) |
| [9351886003366](records/9351886003366.json) | SG3H-B-HD | 3-Door Outdoor Bar Fridge (Heated Glass) |

### Rhino SGT (3)

| GTIN | SKU | Name |
|---|---|---|
| [9351886001393](records/9351886001393.json) | SGT1R-BS | 3-Door Upright Display Fridge (Low-E Glass) |
| [9351886001409](records/9351886001409.json) | SGT1L-BS | 3-Door Upright Display Fridge (Low-E Glass) |
| [9351886001430](records/9351886001430.json) | SGT2-BS | 2-Door Upright Display Fridge (Low-E Glass) |

### Rhino TK (3)

| GTIN | SKU | Name |
|---|---|---|
| [9351886006626](records/9351886006626.json) | TK-6 | Open Display Commercial Cooler (Low-E Glass) |
| [9351886006633](records/9351886006633.json) | TK-6S | Open Display Commercial Cooler (Low-E Glass) |
| [9351886006657](records/9351886006657.json) | TK-12 | Open Display Commercial Cooler (Low-E Glass) |

### Known data gaps

- 35 products missing `capacity_litres` — source product pages don't include volume data
- TK-6S and TK-9 share the same GTIN in Shopify (data entry error, pending correction)
- 2 products couldn't be fetched (GSP1HL-840-SS, SG1R-HDQ) — likely discontinued

---

Maintained by [Signetry](https://signetry.ai). Contributions welcome.
