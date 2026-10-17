"""Flatten raw Shopify snapshots into spreadsheets for human review (no cleaning yet).

Writes, next to the raw snapshots (local only, gitignored):
  shopify_products_flat.csv  one row per product
  shopify_variants_flat.csv  one row per variant (size / shade)
"""

import argparse
import csv
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def strip_html(s, limit=None):
    text = re.sub(r"<[^>]+>", " ", s or "")
    text = re.sub(r"\s+", " ", html.unescape(text)).strip()
    return text[:limit] if limit else text


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="2026-10-17")
    args = ap.parse_args()
    raw_dir = ROOT / "data" / "raw" / args.date
    prod_rows, var_rows = [], []
    for f in sorted((raw_dir / "shopify").glob("*.json")):
        snap = json.loads(f.read_text(encoding="utf-8"))
        host = snap.get("final_host") or snap["domain"]
        for p in snap["products"]:
            variants = p.get("variants", [])
            prices = [num(v.get("price")) for v in variants if num(v.get("price")) is not None]
            mrps = [num(v.get("compare_at_price")) for v in variants if num(v.get("compare_at_price"))]
            desc = strip_html(p.get("body_html"))
            prod_rows.append({
                "brand": snap["brand"],
                "product_id": p.get("id"),
                "title": p.get("title"),
                "product_type": p.get("product_type"),
                "vendor": p.get("vendor"),
                "tags": ", ".join(p.get("tags", [])) if isinstance(p.get("tags"), list) else p.get("tags"),
                "url": f"https://{host}/products/{p.get('handle')}",
                "n_variants": len(variants),
                "variant_names": " | ".join(v.get("title", "") for v in variants)[:200],
                "price_min": min(prices) if prices else None,
                "price_max": max(prices) if prices else None,
                "mrp_max": max(mrps) if mrps else None,
                "any_in_stock": any(v.get("available") for v in variants),
                "n_images": len(p.get("images", [])),
                "description_chars": len(desc),
                "description_start": desc[:400],
                "created_at": (p.get("created_at") or "")[:10],
                "updated_at": (p.get("updated_at") or "")[:10],
            })
            for v in variants:
                var_rows.append({
                    "brand": snap["brand"],
                    "product_id": p.get("id"),
                    "product_title": p.get("title"),
                    "variant_id": v.get("id"),
                    "variant_title": v.get("title"),
                    "sku": v.get("sku"),
                    "price": v.get("price"),
                    "mrp_compare_at": v.get("compare_at_price"),
                    "available": v.get("available"),
                    "grams": v.get("grams"),
                })
    for name, rows in [("shopify_products_flat.csv", prod_rows), ("shopify_variants_flat.csv", var_rows)]:
        out = raw_dir / name
        with open(out, "w", newline="", encoding="utf-8-sig") as fh:  # utf-8-sig so Excel shows ₹ etc.
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print(f"{out}  ({len(rows)} rows)")


if __name__ == "__main__":
    main()
