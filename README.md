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

## Records

| GTIN | Brand | SKU | Name |
|---|---|---|---|
| [9351886000266](records/9351886000266.json) | Rhino | ENV1R-SS | Envy 1-Door Outdoor Bar Fridge |
| [9351886001324](records/9351886001324.json) | Rhino | ENV1L-SS | Envy 1-Door Outdoor Bar Fridge (Left Hinge) |
| [9351886000259](records/9351886000259.json) | Rhino | ENV1R-SD | Envy 1-Door Outdoor Bar Fridge (Solid Door) |
| [9351886001263](records/9351886001263.json) | Rhino | ENV1L-SD | Envy 1-Door Outdoor Bar Fridge (Solid Door, Left Hinge) |
| [9351886000273](records/9351886000273.json) | Rhino | ENV2H-SS | Envy 2-Door Outdoor Bar Fridge |
| [9351886003205](records/9351886003205.json) | Rhino | ENV2H-SD | Envy 2-Door Outdoor Bar Fridge (Solid Door) |
| [9351886001331](records/9351886001331.json) | Rhino | ENV3H-SS | Envy 3-Door Outdoor Bar Fridge |

---

Maintained by [Signetry](https://signetry.ai). Contributions welcome.
