#!/usr/bin/env python3
"""Pull primary product images from BFA feed into PIR repo.

Downloads the first image for each product, saves as images/{gtin}.jpg,
and updates each PIR record with an `images` array.

Usage:
    cd pir && python3 scripts/pull-images.py
"""

import json
import os
import sys
import time
import urllib.request
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

FEED_URL = "https://feed.barfridgesaustralia.au/api/v1/bfa/company/174752036"
PIR_ROOT = Path(__file__).parent.parent
IMAGES_DIR = PIR_ROOT / "images"
RECORDS_DIR = PIR_ROOT / "records"


def fetch_feed():
    """Fetch BFA product feed."""
    print(f"Fetching feed from {FEED_URL}...")
    req = urllib.request.Request(FEED_URL, headers={"User-Agent": "signetry-pir/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    print(f"  {len(data)} products in feed")
    return data


def download_image(gtin: str, url: str, dest: Path) -> tuple[str, bool, str]:
    """Download a single image. Returns (gtin, success, message)."""
    if dest.exists() and dest.stat().st_size > 1000:
        return (gtin, True, "already exists")

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "signetry-pir/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read()
            if len(data) < 500:
                return (gtin, False, f"too small ({len(data)} bytes)")
            dest.write_bytes(data)
            return (gtin, True, f"{len(data) // 1024}KB")
    except Exception as e:
        return (gtin, False, str(e)[:80])


def update_record(gtin: str, image_filename: str):
    """Add images array to PIR record."""
    record_path = RECORDS_DIR / f"{gtin}.json"
    if not record_path.exists():
        return False

    with open(record_path) as f:
        record = json.load(f)

    record["images"] = [
        {
            "url": f"images/{image_filename}",
            "alt": f"{record.get('brand', '')} {record.get('name', '')}".strip(),
            "primary": True,
            "source": "barfridgesaustralia.com.au",
        }
    ]

    with open(record_path, "w") as f:
        json.dump(record, f, indent=2, ensure_ascii=False)
        f.write("\n")

    return True


def main():
    IMAGES_DIR.mkdir(exist_ok=True)

    feed = fetch_feed()

    # Build download tasks: gtin -> first image URL
    tasks = {}
    for product in feed:
        gtin = product.get("gtin")
        images = product.get("product_images", [])
        if not gtin or not images:
            continue
        # Check PIR record exists
        if not (RECORDS_DIR / f"{gtin}.json").exists():
            continue
        tasks[gtin] = images[0]

    print(f"  {len(tasks)} products with images matching PIR records")
    print(f"\nDownloading primary images to {IMAGES_DIR}/...")

    # Determine file extension from URL
    def get_ext(url):
        path = url.split("?")[0]
        if path.endswith(".png"):
            return ".png"
        if path.endswith(".webp"):
            return ".webp"
        return ".jpg"

    success = 0
    failed = 0
    skipped = 0

    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = {}
        for gtin, url in tasks.items():
            ext = get_ext(url)
            dest = IMAGES_DIR / f"{gtin}{ext}"
            futures[pool.submit(download_image, gtin, url, dest)] = (gtin, ext)

        for future in as_completed(futures):
            gtin, ext = futures[future]
            gtin_result, ok, msg = future.result()
            if ok:
                if msg == "already exists":
                    skipped += 1
                else:
                    success += 1
                # Update PIR record
                update_record(gtin, f"{gtin}{ext}")
            else:
                failed += 1
                print(f"  FAIL {gtin}: {msg}")

    print(f"\nDone: {success} downloaded, {skipped} skipped (existed), {failed} failed")
    print(f"Total images: {success + skipped}")

    # Update catalog.json with image flag
    catalog_path = PIR_ROOT / "catalog.json"
    if catalog_path.exists():
        with open(catalog_path) as f:
            catalog = json.load(f)
        updated = 0
        for product in catalog.get("products", []):
            gtin = product.get("gtin")
            if gtin and gtin in tasks:
                ext = get_ext(tasks[gtin])
                product["has_image"] = True
                product["image"] = f"images/{gtin}{ext}"
                updated += 1
        with open(catalog_path, "w") as f:
            json.dump(catalog, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print(f"Updated catalog.json: {updated} products with image flag")


if __name__ == "__main__":
    main()
