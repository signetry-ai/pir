#!/usr/bin/env python3
"""
PIR Data Review Server — local tool for auditing and editing product records.

Run: python3 pir/scripts/review_server.py
Open: http://localhost:8787

Features:
- Browse all products with seller images (scraped from BFA Shopify CDN)
- View all facts for each product
- Inline edit any fact value — saves directly to the JSON file
- Filter by brand, door count, category
- Flag data quality issues visually
"""

import json
import os
import re
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

RECORDS_DIR = Path(__file__).resolve().parent.parent / "records"
PORT = 8787


def load_all_records():
    records = []
    for f in sorted(RECORDS_DIR.glob("*.json")):
        if "." in f.stem:  # skip .notes.json, .chunks.json etc
            continue
        with open(f) as fh:
            try:
                rec = json.load(fh)
            except json.JSONDecodeError:
                continue
        if not isinstance(rec, dict):
            continue
        rec["_file"] = f.name
        rec["_gtin"] = f.stem
        records.append(rec)
    return records


def get_product_image(rec):
    """Try to get a product image URL from seller data."""
    sellers = rec.get("sellers", [])
    for s in sellers:
        url = s.get("url", "")
        # BFA is Shopify — construct CDN image from product handle
        if "bar-fridges-australia.com.au" in url:
            # Use the seller page URL as a link, but we can't get images without scraping
            return url
    return ""


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PIR Data Review</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'SF Mono', monospace; background: #0a0a0a; color: #e4e4e7; font-size: 13px; }

  .toolbar { position: sticky; top: 0; z-index: 100; background: #18181b; border-bottom: 1px solid #27272a; padding: 12px 20px; display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
  .toolbar label { color: #71717a; font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; }
  .toolbar select, .toolbar input { background: #27272a; color: #e4e4e7; border: 1px solid #3f3f46; padding: 6px 10px; border-radius: 4px; font-size: 12px; font-family: inherit; }
  .toolbar .count { color: #a1a1aa; font-size: 12px; margin-left: auto; }

  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(420px, 1fr)); gap: 1px; background: #27272a; padding: 1px; }

  .card { background: #18181b; padding: 16px; display: flex; flex-direction: column; gap: 10px; }
  .card.dirty { outline: 2px solid #f59e0b; outline-offset: -2px; }
  .card.saved { outline: 2px solid #22c55e; outline-offset: -2px; }

  .card-header { display: flex; gap: 12px; align-items: flex-start; }
  .card-header .info { flex: 1; min-width: 0; }
  .card-header .brand { color: #71717a; font-size: 11px; text-transform: uppercase; letter-spacing: 0.08em; }
  .card-header .name { color: #fafafa; font-size: 14px; font-weight: 600; margin-top: 2px; line-height: 1.3; }
  .card-header .gtin { color: #52525b; font-size: 11px; font-family: monospace; margin-top: 4px; }
  .card-header .sku { color: #a1a1aa; font-size: 11px; }
  .card-header .seller-link { display: inline-block; margin-top: 4px; color: #3b82f6; font-size: 11px; text-decoration: none; }
  .card-header .seller-link:hover { text-decoration: underline; }

  .facts-table { width: 100%; border-collapse: collapse; }
  .facts-table tr { border-bottom: 1px solid #1e1e22; }
  .facts-table tr:last-child { border-bottom: none; }
  .facts-table td { padding: 3px 0; vertical-align: top; }
  .facts-table .fk { color: #71717a; width: 45%; font-size: 11px; padding-right: 8px; }
  .facts-table .fv { color: #e4e4e7; font-family: monospace; font-size: 12px; }

  .facts-table .fv-edit { background: transparent; color: #e4e4e7; border: 1px solid transparent; padding: 1px 4px; font-family: monospace; font-size: 12px; width: 100%; border-radius: 2px; }
  .facts-table .fv-edit:hover { border-color: #3f3f46; }
  .facts-table .fv-edit:focus { border-color: #3b82f6; outline: none; background: #27272a; }
  .facts-table .fv-edit.changed { color: #f59e0b; border-color: #f59e0b; }

  .card-actions { display: flex; gap: 8px; margin-top: 4px; }
  .btn-save { background: #22c55e; color: #0a0a0a; border: none; padding: 5px 14px; border-radius: 3px; font-size: 11px; font-weight: 600; cursor: pointer; font-family: inherit; display: none; }
  .btn-save:hover { background: #16a34a; }
  .card.dirty .btn-save { display: inline-block; }

  .badge { display: inline-block; padding: 1px 6px; border-radius: 2px; font-size: 10px; font-weight: 600; }
  .badge-warn { background: #451a03; color: #f59e0b; }
  .badge-ok { background: #052e16; color: #22c55e; }
  .badge-info { background: #172554; color: #60a5fa; }

  .status-bar { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 2px; }

  .toast { position: fixed; bottom: 20px; right: 20px; background: #22c55e; color: #0a0a0a; padding: 10px 20px; border-radius: 6px; font-weight: 600; font-size: 13px; opacity: 0; transition: opacity 0.3s; z-index: 200; }
  .toast.show { opacity: 1; }
  .toast.error { background: #ef4444; color: white; }
</style>
</head>
<body>

<div class="toolbar">
  <div>
    <label>Brand</label><br>
    <select id="filterBrand" onchange="applyFilters()">
      <option value="">All</option>
    </select>
  </div>
  <div>
    <label>Doors</label><br>
    <select id="filterDoors" onchange="applyFilters()">
      <option value="">All</option>
      <option value="1">1-Door</option>
      <option value="2">2-Door</option>
      <option value="3">3-Door</option>
    </select>
  </div>
  <div>
    <label>Category</label><br>
    <select id="filterCategory" onchange="applyFilters()">
      <option value="">All</option>
    </select>
  </div>
  <div>
    <label>Search</label><br>
    <input type="text" id="filterSearch" placeholder="GTIN, SKU, name..." oninput="applyFilters()" style="width:200px">
  </div>
  <div>
    <label>Sort</label><br>
    <select id="sortBy" onchange="applyFilters()">
      <option value="brand">Brand + Name</option>
      <option value="gtin">GTIN</option>
      <option value="category">Category</option>
      <option value="doors">Door Count</option>
    </select>
  </div>
  <div class="count" id="countDisplay">-</div>
</div>

<div class="grid" id="grid"></div>

<div class="toast" id="toast"></div>

<script>
let ALL_RECORDS = [];
let DIRTY = {};  // gtin -> {key: newValue}

async function loadData() {
  const resp = await fetch('/api/records');
  ALL_RECORDS = await resp.json();
  populateFilters();
  applyFilters();
}

function populateFilters() {
  const brands = [...new Set(ALL_RECORDS.map(r => r.brand).filter(Boolean))].sort();
  const cats = [...new Set(ALL_RECORDS.map(r => r.category).filter(Boolean))].sort();

  const brandSel = document.getElementById('filterBrand');
  brands.forEach(b => { const o = document.createElement('option'); o.value = b; o.textContent = b; brandSel.appendChild(o); });

  const catSel = document.getElementById('filterCategory');
  cats.forEach(c => { const o = document.createElement('option'); o.value = c; o.textContent = c.replace(/_/g, ' '); catSel.appendChild(o); });
}

function applyFilters() {
  const brand = document.getElementById('filterBrand').value;
  const doors = document.getElementById('filterDoors').value;
  const cat = document.getElementById('filterCategory').value;
  const search = document.getElementById('filterSearch').value.toLowerCase();
  const sortBy = document.getElementById('sortBy').value;

  let filtered = ALL_RECORDS.filter(r => {
    if (brand && r.brand !== brand) return false;
    if (doors && String(r.facts?.door_count || '') !== doors) return false;
    if (cat && r.category !== cat) return false;
    if (search) {
      const haystack = [r._gtin, r.sku, r.name, r.brand, r.category].join(' ').toLowerCase();
      if (!haystack.includes(search)) return false;
    }
    return true;
  });

  filtered.sort((a, b) => {
    if (sortBy === 'brand') return (a.brand + a.name).localeCompare(b.brand + b.name);
    if (sortBy === 'gtin') return a._gtin.localeCompare(b._gtin);
    if (sortBy === 'category') return (a.category || '').localeCompare(b.category || '');
    if (sortBy === 'doors') return (a.facts?.door_count || 0) - (b.facts?.door_count || 0);
    return 0;
  });

  document.getElementById('countDisplay').textContent = `${filtered.length} / ${ALL_RECORDS.length} products`;
  renderGrid(filtered);
}

function renderGrid(records) {
  const grid = document.getElementById('grid');
  grid.innerHTML = '';

  records.forEach(rec => {
    const card = document.createElement('div');
    card.className = 'card';
    card.id = `card-${rec._gtin}`;

    const sellerUrl = rec.sellers?.[0]?.url || '';
    const sellerLink = sellerUrl ? `<a class="seller-link" href="${sellerUrl}" target="_blank">View on retailer site &rarr;</a>` : '';

    // Status badges
    const badges = [];
    const f = rec.facts || {};
    if (!f.door_count) badges.push('<span class="badge badge-warn">no door_count</span>');
    if (!f.door_hinge) badges.push('<span class="badge badge-warn">no hinge</span>');
    if (f.door_reversible === true) badges.push('<span class="badge badge-info">reversible</span>');
    if (!f.capacity_litres) badges.push('<span class="badge badge-warn">no capacity</span>');
    if (!f.dimensions_exterior_w_mm) badges.push('<span class="badge badge-warn">no dimensions</span>');

    card.innerHTML = `
      <div class="card-header">
        <div class="info">
          <div class="brand">${rec.brand || '?'} &middot; ${rec.range || ''}</div>
          <div class="name">${rec.name || '?'}</div>
          <div class="gtin">${rec._gtin} &middot; <span class="sku">${rec.sku || '?'}</span> &middot; ${(rec.category || '').replace(/_/g, ' ')}</div>
          ${sellerLink}
          <div class="status-bar">${badges.join('')}</div>
        </div>
      </div>
      <table class="facts-table">
        ${renderFacts(rec._gtin, rec.facts || {})}
      </table>
      <div class="card-actions">
        <button class="btn-save" onclick="saveRecord('${rec._gtin}')">Save Changes</button>
      </div>
    `;

    grid.appendChild(card);
  });
}

function renderFacts(gtin, facts) {
  // Define display order - important fields first
  const priority = [
    'door_count', 'door_hinge', 'door_reversible', 'door_type',
    'capacity_litres', 'capacity_375ml_cans',
    'dimensions_exterior_w_mm', 'dimensions_exterior_d_mm', 'dimensions_exterior_h_mm',
    'weight_kg', 'noise_db', 'lockable', 'glass_door', 'led_lighting',
    'location', 'ambient_temperature_max_c',
    'body_material', 'interior_finish',
  ];

  const allKeys = Object.keys(facts);
  const ordered = [...priority.filter(k => k in facts), ...allKeys.filter(k => !priority.includes(k))];

  return ordered.map(key => {
    const val = facts[key];
    const displayVal = Array.isArray(val) ? val.join(', ') : String(val);
    const inputType = typeof val === 'boolean' ? 'checkbox' : 'text';

    if (typeof val === 'boolean') {
      return `<tr>
        <td class="fk">${key.replace(/_/g, ' ')}</td>
        <td class="fv">
          <label style="cursor:pointer">
            <input type="checkbox" ${val ? 'checked' : ''}
              onchange="markChanged('${gtin}', '${key}', this.checked, 'bool')"
              style="accent-color: #3b82f6">
            ${val ? 'Yes' : 'No'}
          </label>
        </td>
      </tr>`;
    }

    return `<tr>
      <td class="fk">${key.replace(/_/g, ' ')}</td>
      <td class="fv">
        <input class="fv-edit" value="${escapeHtml(displayVal)}"
          data-original="${escapeHtml(displayVal)}"
          data-gtin="${gtin}" data-key="${key}"
          onchange="markChanged('${gtin}', '${key}', this.value, '${typeof val === 'number' ? 'number' : Array.isArray(val) ? 'array' : 'string'}')"
          onfocus="this.select()">
      </td>
    </tr>`;
  }).join('');
}

function escapeHtml(str) {
  return str.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function markChanged(gtin, key, value, type) {
  if (!DIRTY[gtin]) DIRTY[gtin] = {};

  // Convert types
  if (type === 'number') {
    const n = Number(value);
    if (!isNaN(n)) value = n;
  } else if (type === 'bool') {
    // already boolean from checkbox
  } else if (type === 'array') {
    value = value.split(',').map(s => s.trim()).filter(Boolean);
  }

  DIRTY[gtin][key] = value;

  const card = document.getElementById(`card-${gtin}`);
  card.classList.add('dirty');
  card.classList.remove('saved');

  // Highlight the input
  const input = card.querySelector(`input[data-key="${key}"]`);
  if (input && input.classList) input.classList.add('changed');
}

async function saveRecord(gtin) {
  const changes = DIRTY[gtin];
  if (!changes) return;

  try {
    const resp = await fetch('/api/save', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({gtin, facts: changes})
    });

    if (!resp.ok) throw new Error(await resp.text());

    const result = await resp.json();

    // Update local data
    const rec = ALL_RECORDS.find(r => r._gtin === gtin);
    if (rec) {
      for (const [k, v] of Object.entries(changes)) {
        rec.facts[k] = v;
      }
    }

    delete DIRTY[gtin];
    const card = document.getElementById(`card-${gtin}`);
    card.classList.remove('dirty');
    card.classList.add('saved');
    card.querySelectorAll('.fv-edit.changed').forEach(el => el.classList.remove('changed'));

    setTimeout(() => card.classList.remove('saved'), 2000);
    showToast(`Saved ${gtin} (${Object.keys(changes).length} fields)`);

  } catch (err) {
    showToast(`Error saving ${gtin}: ${err.message}`, true);
  }
}

function showToast(msg, isError) {
  const toast = document.getElementById('toast');
  toast.textContent = msg;
  toast.className = 'toast show' + (isError ? ' error' : '');
  setTimeout(() => toast.className = 'toast', 2500);
}

// Keyboard shortcut: Ctrl+S saves all dirty records
document.addEventListener('keydown', async (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key === 's') {
    e.preventDefault();
    const gtins = Object.keys(DIRTY);
    if (!gtins.length) return;
    for (const gtin of gtins) {
      await saveRecord(gtin);
    }
    showToast(`Saved ${gtins.length} record(s)`);
  }
});

loadData();
</script>
</body>
</html>"""


class ReviewHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path.startswith("/?"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(HTML_TEMPLATE.encode())

        elif self.path == "/api/records":
            records = load_all_records()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(records, ensure_ascii=False).encode())

        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/api/save":
            content_length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(content_length))

            gtin = body.get("gtin")
            fact_updates = body.get("facts", {})

            if not gtin or not fact_updates:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b'{"error":"missing gtin or facts"}')
                return

            filepath = RECORDS_DIR / f"{gtin}.json"
            if not filepath.exists():
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b'{"error":"record not found"}')
                return

            with open(filepath) as f:
                record = json.load(f)

            facts = record.get("facts", {})
            changed = []
            for key, value in fact_updates.items():
                old = facts.get(key)
                facts[key] = value
                changed.append({"key": key, "old": old, "new": value})

            with open(filepath, "w") as f:
                json.dump(record, f, indent=2, ensure_ascii=False)
                f.write("\n")

            print(f"  SAVED {gtin}: {', '.join(c['key'] for c in changed)}")

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True, "changed": changed}).encode())

        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        if "/api/save" in str(args):
            BaseHTTPRequestHandler.log_message(self, format, *args)


def main():
    server = HTTPServer(("127.0.0.1", PORT), ReviewHandler)
    print(f"\n  PIR Data Review Server")
    print(f"  http://localhost:{PORT}")
    print(f"  Records: {RECORDS_DIR}")
    print(f"  Ctrl+C to stop\n")
    print(f"  Tips:")
    print(f"  - Click any value to edit inline")
    print(f"  - Cmd+S saves all pending changes")
    print(f"  - Changes write directly to JSON files\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_close()


if __name__ == "__main__":
    main()
