"""Flatten Phase 1b product-page records (sitemap brands) into one review spreadsheet."""

import argparse
import csv
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def clean(s, limit=400):
    s = re.sub(r"<[^>]+>", " ", s or "")
    return re.sub(r"\s+", " ", html.unescape(s)).strip()[:limit]


def first_offer(offers):
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    if isinstance(offers, dict) and offers.get("@type") == "AggregateOffer":
        return offers.get("lowPrice"), offers.get("highPrice"), offers.get("availability")
    if isinstance(offers, dict):
        return offers.get("price"), None, offers.get("availability")
    return None, None, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="2026-10-17")
    args = ap.parse_args()
    raw_dir = ROOT / "data" / "raw" / args.date
    rows = []
    for f in sorted((raw_dir / "pages").glob("*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            if not r.get("is_product"):
                continue
            base = {"brand": r["brand"], "url": r["url"]}
            if r.get("plix_product"):
                p = r["plix_product"]
                pr = ((p.get("pricing") or {}).get("priceRange") or {}).get("start", {}) or {}
                mrp = ((p.get("pricing") or {}).get("priceRangeUndiscounted") or {}).get("start", {}) or {}
                rows.append({**base, "name": p.get("name"), "price": (pr.get("gross") or {}).get("amount"),
                             "mrp": (mrp.get("gross") or {}).get("amount"), "in_stock": p.get("is_available"),
                             "rating": None, "review_count": p.get("review_count"),
                             "n_variants": len(p.get("variants") or []), "description_start": clean(p.get("description") or p.get("seo_description"))})
            elif r.get("shopify_product"):
                p = r["shopify_product"]
                v = (p.get("variants") or [{}])[0]
                rows.append({**base, "name": p.get("title"), "price": v.get("price"), "mrp": v.get("compare_at_price"),
                             "in_stock": None, "rating": None, "review_count": None,
                             "n_variants": len(p.get("variants") or []), "description_start": clean(p.get("body_html"))})
            else:
                p = r["jsonld_products"][0]
                price, high, avail = first_offer(p.get("offers"))
                ar = p.get("aggregateRating") or {}
                rows.append({**base, "name": clean(p.get("name"), 150), "price": price or r.get("og_price"), "mrp": high,
                             "in_stock": (str(avail).endswith("InStock") if avail else None),
                             "rating": ar.get("ratingValue"), "review_count": ar.get("reviewCount") or ar.get("ratingCount"),
                             "n_variants": None, "description_start": clean(p.get("description") or r.get("description"))})
    out = raw_dir / "pages_products_flat.csv"
    with open(out, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"{out}  ({len(rows)} rows)")


if __name__ == "__main__":
    main()
