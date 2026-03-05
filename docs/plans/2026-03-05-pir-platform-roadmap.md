# PIR Platform Roadmap

**Date:** 2026-03-05
**Status:** Draft — awaiting review

## What PIR Is

PIR is an **open-source registry of structured product facts**, indexed by GTIN. JSON files on GitHub. CC0 licensed. That's it.

PIR has zero dependency on any specific platform, database, or backend. Anyone can read the JSON files directly. Anyone can build on top of them.

## What PIR Is Not

PIR is NOT:
- A Supabase database
- A backend service
- Coupled to any resolver, widget, or storefront
- Dependent on Signetry's infrastructure

Solutions like resolvers, widgets, discovery engines, etc. are **consumers** of PIR. They may choose to read PIR records. That's their business.

---

## Phase 1: Complete the Registry (NOW)

**Goal:** Get the data right. More brands, more products, 100% correct.

- [x] Rhino Envy (7 records)
- [x] Rhino SG/GSP/SGT/TK (36 records)
- [ ] Schmick (in progress)
- [ ] Fill capacity_litres gaps (35 products)
- [ ] Fix TK-6S/TK-9 GTIN collision
- [ ] More brands as contributors join

**Tooling:**
- `scripts/process_intake.py` — Repeatable brand onboarding from intake files
- `scripts/validate.py` — Schema validation
- `intake/` directory — Working files for data entry (gitignored)

---

## Phase 2: Product Pages (signetry.ai/products/{gtin})

**Goal:** Human-readable product pages. Shareable links.

A lightweight page that renders PIR JSON into a clean product fact sheet:
- Specs table from `facts{}`
- Pre-answered questions from `qa[]`
- Documents and seller links
- Trust status (brand-certified or retailer-submitted)
- Link to raw JSON

Implementation: static site or simple SSR that reads JSON files directly from the repo. No database layer.

---

## Phase 3: Contributor Onboarding

**Goal:** A retailer can add products without knowing git.

1. Web form at `signetry.ai/contribute`
2. Paste product URL + specs
3. System validates, generates PIR JSON preview
4. Auto-creates GitHub PR to this repo
5. CI validates schema → maintainer merges

Brand certification remains self-serve via DNS TXT verification.

---

## Phase 4: API Access

**Goal:** Programmatic access for developers building on PIR.

```
GET /v1/pir/{gtin}          → Full PIR record
GET /v1/pir/{gtin}/facts    → Just the facts
GET /v1/pir/{gtin}/qa       → Just Q&A pairs
GET /v1/pir/search?brand=Rhino&category=bar_fridge
```

This is a thin read-only API over the JSON files. Could be a Cloudflare Worker reading from GitHub, or a simple static API. No database required.

---

## Consumers (Separate Projects)

These are NOT part of PIR. They are independent projects that choose to use PIR data:

- **Resolver** — AI-powered Q&A engine. Can read PIR records as input.
- **Widget** — Embeddable product intelligence. Can use resolver + PIR.
- **KingCave storefront** — A retailer site. Can embed widget or call resolver.
- **FridgeFinder** — Discovery engine. Can use PIR for product data.

How these consumers integrate with PIR is their own architectural decision.

---

## Known Data Gaps

- 35 Rhino products missing `capacity_litres`
- TK-6S / TK-9 GTIN collision (Shopify data entry error)
- 2 discontinued products (GSP1HL-840-SS, SG1R-HDQ)
