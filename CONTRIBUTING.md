# Contributing to PIR

Product Intelligence Records are open data. Anyone with a barcode and a spec sheet can contribute.

## Who can contribute

- **Brands** — certify and maintain your own product records
- **Retailers** — submit data for products you sell
- **Anyone** — if you have the physical product or official spec sheet, you can contribute

## Submitting a record

1. Fork this repo
2. Create `records/{gtin}.json` (use any existing record as a template)
3. Fill in the fields you can verify — omit what you can't
4. Set your status:
   ```json
   "status": {
     "brand_certified": false,
     "submitted_by": "yourdomain.com",
     "submitted_date": "2026-03-05"
   }
   ```
5. Open a pull request against `main`

CI validates your record against the schema automatically. Fix any failures before requesting review.

Products without a GTIN use `sku-{SKU}.json` with `"gtin": null`.

## Record quality rules

Every fact must come from a verifiable source:

- Official spec sheet or product page
- Physical product label or packaging
- Manufacturer datasheet

**Do:**
- Use unit-in-key naming: `capacity_litres`, `weight_kg`, `noise_db`
- Keep `name` descriptive and neutral — no marketing language
- Include `documents[]` links to your sources where possible
- Add `qa[]` entries for common questions the data can answer

**Don't:**
- Guess or estimate values — omit what you can't verify
- Copy specs from third-party sites without cross-checking the source
- Include pricing (changes too frequently to maintain)
- Include reviews, opinions, or subjective assessments

## Updating existing records

- Add missing facts, fix errors, add documents or sellers
- Don't remove existing facts unless they are provably wrong
- Note your source in the PR description

## Brand certification

Brands can certify their own records, which marks them as brand-approved:

1. Open an issue titled "Brand certification: yourbrand.com"
2. Add a DNS TXT record to your domain: `pir-verify=<token>` (we'll provide the token)
3. We verify domain ownership and set `brand_certified: true` on your records

Once certified, only you can update your records.

## What we won't merge

- Records with no verifiable source
- Duplicate GTINs (check `catalog.json` first)
- Pricing, stock levels, or other volatile data
- Marketing copy, reviews, or opinions
- `brand_certified: true` set by anyone other than a maintainer

## Schema reference

Full schema: [`schema/pir.v1.json`](schema/pir.v1.json)

Validate locally:
```bash
pip install jsonschema
python scripts/validate.py
```

## Questions

Open an issue. We're happy to help with record formatting or data sourcing.
