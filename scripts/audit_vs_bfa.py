#!/usr/bin/env python3
"""
Audit PIR records against BFA feed.

Compares: door_count, dimensions (W/D/H), capacity (litres + cans), location suitability.
Ignores: lockable (BFA data unreliable).

Run: python3 pir/scripts/audit_vs_bfa.py [--html]
"""

import json
import re
import sys
import urllib.request
from pathlib import Path
from collections import defaultdict

RECORDS_DIR = Path(__file__).resolve().parent.parent / "records"
FEED_URL = "https://feed.barfridgesaustralia.au/api/v1/bfa/company/174752036"

DOOR_RE = re.compile(r'(\d+)[- ]?door', re.IGNORECASE)


def fetch_feed():
    print("Fetching BFA feed...")
    req = urllib.request.Request(FEED_URL)
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read())
    print(f"  {len(data)} products in feed")
    return {item["gtin"]: item for item in data if item.get("gtin")}


def load_pir():
    records = {}
    for f in sorted(RECORDS_DIR.glob("*.json")):
        if "." in f.stem:
            continue
        with open(f) as fh:
            rec = json.load(fh)
        if not isinstance(rec, dict):
            continue
        gtin = rec.get("gtin") or f.stem
        records[gtin] = rec
    print(f"  {len(records)} PIR records loaded")
    return records


def extract_door_count_from_name(name):
    m = DOOR_RE.search(name)
    return int(m.group(1)) if m else None


def normalize_location(suitability):
    """BFA suitability -> PIR location list."""
    s = (suitability or "").lower().strip()
    if not s:
        return None
    if "outdoor" in s:
        return ["indoor", "outdoor"]
    if "alfresco" in s:
        return ["indoor", "outdoor"]
    if "indoor" in s:
        return ["indoor"]
    return None


def compare_location(pir_loc, bfa_loc):
    """Compare location arrays. Returns True if equivalent."""
    if pir_loc is None or bfa_loc is None:
        return None  # can't compare
    pir_set = set(pir_loc) if isinstance(pir_loc, list) else {pir_loc}
    bfa_set = set(bfa_loc) if isinstance(bfa_loc, list) else {bfa_loc}
    return pir_set == bfa_set


def audit():
    feed = fetch_feed()
    pir = load_pir()

    matched = 0
    not_in_pir = 0
    not_in_feed = 0
    deltas = []

    feed_gtins = set(feed.keys())
    pir_gtins = set(pir.keys())

    for gtin in sorted(feed_gtins & pir_gtins):
        matched += 1
        bfa = feed[gtin]
        rec = pir[gtin]
        facts = rec.get("facts", {})
        issues = []

        sku = rec.get("sku", bfa.get("product_code", "?"))

        # -- Door count --
        pir_doors = facts.get("door_count")
        bfa_doors = extract_door_count_from_name(bfa.get("product_name", ""))
        if pir_doors and bfa_doors and pir_doors != bfa_doors:
            issues.append({
                "field": "door_count",
                "pir": pir_doors,
                "bfa": bfa_doors,
            })

        # -- Dimensions --
        dim_checks = [
            ("dimensions_exterior_w_mm", "width"),
            ("dimensions_exterior_d_mm", "depth"),
            ("dimensions_exterior_h_mm", "height"),
        ]
        for pir_key, bfa_key in dim_checks:
            pir_val = facts.get(pir_key)
            bfa_val = bfa.get(bfa_key)
            if pir_val is not None and bfa_val is not None:
                try:
                    bfa_num = int(float(bfa_val))
                    pir_num = int(float(pir_val))
                    if abs(pir_num - bfa_num) > 5:  # 5mm tolerance
                        issues.append({
                            "field": pir_key.replace("dimensions_exterior_", "").replace("_mm", ""),
                            "pir": pir_num,
                            "bfa": bfa_num,
                            "delta": pir_num - bfa_num,
                        })
                except (ValueError, TypeError):
                    pass

        # -- Capacity --
        bfa_cap = bfa.get("capacity", {})

        pir_litres = facts.get("capacity_litres")
        bfa_litres = bfa_cap.get("litres")
        if pir_litres is not None and bfa_litres is not None:
            try:
                pl = int(float(pir_litres))
                bl = int(float(bfa_litres))
                if abs(pl - bl) > 2:  # 2L tolerance
                    issues.append({
                        "field": "capacity_litres",
                        "pir": pl,
                        "bfa": bl,
                        "delta": pl - bl,
                    })
            except (ValueError, TypeError):
                pass

        pir_cans = facts.get("capacity_375ml_cans")
        bfa_cans = bfa_cap.get("cans")
        if pir_cans is not None and bfa_cans is not None:
            try:
                pc = int(float(pir_cans))
                bc = int(float(bfa_cans))
                if pc != bc:
                    issues.append({
                        "field": "capacity_cans",
                        "pir": pc,
                        "bfa": bc,
                        "delta": pc - bc,
                    })
            except (ValueError, TypeError):
                pass

        # -- Location suitability --
        pir_loc = facts.get("location")
        bfa_suit = bfa.get("technical", {}).get("suitability")
        bfa_loc = normalize_location(bfa_suit)
        loc_match = compare_location(pir_loc, bfa_loc)
        if loc_match is False:
            issues.append({
                "field": "location",
                "pir": pir_loc,
                "bfa": f"{bfa_suit} -> {bfa_loc}",
            })

        if issues:
            deltas.append({
                "gtin": gtin,
                "sku": sku,
                "name": rec.get("name", "?"),
                "issues": issues,
            })

    not_in_pir = len(feed_gtins - pir_gtins)
    not_in_feed = len(pir_gtins - feed_gtins)

    return {
        "matched": matched,
        "not_in_pir": not_in_pir,
        "not_in_feed": not_in_feed,
        "deltas": deltas,
        "feed_only": sorted(feed_gtins - pir_gtins),
        "pir_only": sorted(pir_gtins - feed_gtins),
    }


def print_report(result):
    print(f"\n{'='*70}")
    print(f"BFA FEED vs PIR AUDIT")
    print(f"{'='*70}")
    print(f"Matched GTINs:    {result['matched']}")
    print(f"In feed only:     {result['not_in_pir']}")
    print(f"In PIR only:      {result['not_in_feed']}")
    print(f"Products w/deltas: {len(result['deltas'])}")

    # Summary by field
    field_counts = defaultdict(int)
    for d in result["deltas"]:
        for issue in d["issues"]:
            field_counts[issue["field"]] += 1

    print(f"\n--- Delta Summary ---")
    for field, count in sorted(field_counts.items(), key=lambda x: -x[1]):
        print(f"  {field:25s}: {count} mismatches")

    print(f"\n--- All Deltas ---")
    for d in result["deltas"]:
        print(f"\n  {d['gtin']} | {d['sku']} | {d['name']}")
        for issue in d["issues"]:
            delta_str = f" (delta: {issue['delta']:+d})" if "delta" in issue else ""
            print(f"    {issue['field']:25s}: PIR={issue['pir']}  BFA={issue['bfa']}{delta_str}")

    if result["feed_only"]:
        print(f"\n--- In BFA Feed but NOT in PIR ({len(result['feed_only'])}) ---")
        for gtin in result["feed_only"]:
            print(f"  {gtin}")

    if result["pir_only"]:
        print(f"\n--- In PIR but NOT in BFA Feed ({len(result['pir_only'])}) ---")
        for gtin in result["pir_only"]:
            print(f"  {gtin}")


def write_html(result):
    out = RECORDS_DIR.parent / "scripts" / "audit_report.html"

    rows = []
    for d in result["deltas"]:
        for issue in d["issues"]:
            delta = issue.get("delta", "")
            delta_str = f"{delta:+d}" if isinstance(delta, int) else str(delta)
            severity = "high" if issue["field"] in ("door_count", "location") else "med"
            rows.append(f"""<tr class="{severity}">
                <td class="mono">{d['gtin']}</td>
                <td>{d['sku']}</td>
                <td>{d['name']}</td>
                <td><b>{issue['field']}</b></td>
                <td class="mono">{issue['pir']}</td>
                <td class="mono">{issue['bfa']}</td>
                <td class="mono">{delta_str}</td>
            </tr>""")

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>BFA vs PIR Audit</title>
<style>
    body {{ font-family: -apple-system, monospace; background: #0a0a0a; color: #e4e4e7; margin: 20px; font-size: 13px; }}
    h1 {{ font-size: 18px; color: #fafafa; }}
    .stats {{ display: flex; gap: 24px; margin: 16px 0; }}
    .stat {{ background: #18181b; padding: 12px 20px; border-radius: 6px; }}
    .stat .n {{ font-size: 24px; font-weight: 700; color: #fafafa; }}
    .stat .label {{ color: #71717a; font-size: 11px; text-transform: uppercase; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 16px; }}
    th {{ text-align: left; padding: 8px; border-bottom: 2px solid #27272a; color: #71717a; font-size: 11px; text-transform: uppercase; }}
    td {{ padding: 6px 8px; border-bottom: 1px solid #1e1e22; }}
    .mono {{ font-family: monospace; }}
    tr.high td {{ background: #1c0a0a; }}
    tr.high td:nth-child(4) {{ color: #ef4444; }}
    tr.med td {{ background: #1a1500; }}
    tr.med td:nth-child(4) {{ color: #f59e0b; }}
</style></head><body>
<h1>BFA Feed vs PIR Audit</h1>
<div class="stats">
    <div class="stat"><div class="n">{result['matched']}</div><div class="label">Matched</div></div>
    <div class="stat"><div class="n">{len(result['deltas'])}</div><div class="label">With Deltas</div></div>
    <div class="stat"><div class="n">{result['not_in_pir']}</div><div class="label">Feed Only</div></div>
    <div class="stat"><div class="n">{result['not_in_feed']}</div><div class="label">PIR Only</div></div>
</div>
<table>
<tr><th>GTIN</th><th>SKU</th><th>Name</th><th>Field</th><th>PIR</th><th>BFA</th><th>Delta</th></tr>
{''.join(rows)}
</table>
</body></html>"""

    with open(out, "w") as f:
        f.write(html)
    print(f"\nHTML report: {out}")
    return out


def main():
    result = audit()
    print_report(result)

    if "--html" in sys.argv:
        path = write_html(result)
        import subprocess
        subprocess.run(["open", str(path)])


if __name__ == "__main__":
    main()
