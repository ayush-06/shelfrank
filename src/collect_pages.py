"""Phase 1b: collect products from brands without an open Shopify catalogue.

For each brand: read its sitemap(s), keep URLs that could be product pages, visit each
page politely and keep the ones that carry schema.org "Product" JSON-LD (the same
structured data search engines read: name, description, price, rating...).
Kay Beauty is Shopify, so its product pages are read via /products/<handle>.json.

Output: data/raw/<date>/pages/<slug>.jsonl, one line per visited URL. Resumable:
URLs already in the file are skipped on re-run.
"""

import argparse
import gzip
import html
import json
import re
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IST = timezone(timedelta(hours=5, minutes=30))
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36 ShelfRank-research"
PER_SITE_DELAY = 1.5
ARTICLE = r"tips|about|ingredient|search|green-beauty|gisele|cruelty|offer|store-locator|faq|contact|privacy|terms|sitemap|blog|article|ambassador|women-of-worth|virtual|news|campaign|career|imprint|quiz|routine-finder|how-to|trend|look|tutorial|collection|category"

BRANDS = {
    # Nivea product pages end in -<id>.html; the other /products/ URLs are category pages
    "Nivea": {"sitemaps": ["https://www.nivea.in/sitemap.xml"], "include": r"/products/[^/]+\.html$", "exclude": r"$^"},
    # Garnier.in has no product pages (articles only) -> hand-entered like Pond's
    "Maybelline": {"sitemaps": ["https://www.maybelline.co.in/sitemap.xml"], "include": r".", "exclude": ARTICLE},
    "L'Oreal Paris": {"sitemaps": ["https://www.lorealparis.co.in/sitemap.xml"], "include": r".", "exclude": ARTICLE},
    # Plix has no Product JSON-LD; product data lives in the Next.js __NEXT_DATA__ block
    "Plix": {"sitemaps": ["https://www.plixlife.com/sitemap-products.xml"], "include": r"/product/", "exclude": r"$^", "extract": "plix_next"},
    "WOW Skin Science": {"sitemaps": ["https://www.buywow.in/sitemap.xml"], "include": r"/products/", "exclude": r"$^"},
    "Be Bodywise": {"sitemaps": ["https://bebodywise.com/sitemap-products.xml"], "include": r"/product/", "exclude": r"$^"},
    "Man Matters": {"sitemaps": ["https://manmatters.com/sitemap-products.xml"], "include": r"/dp/", "exclude": r"$^"},
    "Kay Beauty": {"sitemaps": ["https://www.kaybeauty.com/sitemap.xml"], "include": r"kaybeauty\.com/products/", "exclude": r"/en-[a-z]{2}/", "shopify_json": True},
}

print_lock = threading.Lock()


def log(msg):
    with print_lock:
        print(f"[{datetime.now(IST):%H:%M:%S}] {msg}", flush=True)


def slugify(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def fetch(url, tries=5):
    for attempt in range(tries):
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                data = r.read()
                if data[:2] == b"\x1f\x8b":
                    data = gzip.decompress(data)
                return data.decode("utf-8", "ignore"), r.status
        except urllib.error.HTTPError as e:
            if e.code == 429 or e.code >= 500:
                wait = min(30 * (2 ** attempt), 600)
                log(f"  {e.code} on {url} -> waiting {wait}s")
                time.sleep(wait)
                continue
            return None, e.code
        except Exception as e:
            log(f"  error on {url}: {type(e).__name__} -> retry")
            time.sleep(10 * (attempt + 1))
    return None, "gave-up"


def sitemap_urls(sitemap, depth=0):
    xml, status = fetch(sitemap)
    if not xml:
        log(f"  sitemap {sitemap} failed ({status})")
        return []
    locs = [html.unescape(l) for l in re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", xml)]
    if "<sitemapindex" in xml and depth < 2:
        out = []
        for child in locs:
            if re.search(r"product", child, re.I) or len(locs) <= 3:
                time.sleep(PER_SITE_DELAY)
                out += sitemap_urls(child, depth + 1)
        return out
    return locs


def jsonld_products(page):
    found = []
    for block in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', page, re.S | re.I):
        try:
            data = json.loads(block.strip())
        except Exception:
            continue
        stack = data if isinstance(data, list) else [data]
        while stack:
            node = stack.pop()
            if isinstance(node, dict):
                t = node.get("@type")
                if t == "Product" or (isinstance(t, list) and "Product" in t):
                    found.append(node)
                stack.extend(v for v in node.values() if isinstance(v, (dict, list)))
            elif isinstance(node, list):
                stack.extend(node)
    return found


def plix_product(page):
    """Product fields + review COUNT from Plix's __NEXT_DATA__ (no review text, no image lists)."""
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', page, re.S)
    if not m:
        return None
    try:
        ppd = json.loads(m.group(1))["props"]["pageProps"]["productPageData"]
    except Exception:
        return None
    p = ppd.get("product") or {}
    if not p.get("name"):
        return None
    try:
        desc = " ".join(b.get("text", "") for b in json.loads(p.get("descriptionJson") or "{}").get("blocks", []))
    except Exception:
        desc = None
    return {
        "name": p.get("name"),
        "slug": p.get("slug"),
        "is_available": p.get("isAvailable"),
        "pricing": p.get("pricing"),
        "description": desc,
        "seo_title": p.get("seoTitle"),
        "seo_description": p.get("seoDescription"),
        "category": (p.get("category") or {}).get("name"),
        "collections": [c.get("name") for c in p.get("collections") or [] if isinstance(c, dict)],
        "metadata": p.get("metadata"),
        "variants": [{k: v.get(k) for k in ("name", "sku", "isAvailable", "pricing", "attributes")}
                     for v in p.get("variants") or [] if isinstance(v, dict)],
        "review_count": (ppd.get("productReviews") or {}).get("totalCount"),
    }


def meta(page, prop):
    m = re.search(rf'<meta[^>]+(?:property|name)=["\']{prop}["\'][^>]+content=["\']([^"\']*)', page, re.I)
    return html.unescape(m.group(1)) if m else None


def collect_brand(brand, cfg, out_dir):
    out_file = out_dir / f"{slugify(brand)}.jsonl"
    done = set()
    if out_file.exists():
        done = {json.loads(l)["url"] for l in out_file.read_text(encoding="utf-8").splitlines() if l.strip()}

    urls = []
    for sm in cfg["sitemaps"]:
        urls += sitemap_urls(sm)
    urls = sorted({u.split("?")[0].rstrip("/") for u in urls
                   if re.search(cfg["include"], u) and not re.search(cfg["exclude"], u, re.I)})
    todo = [u for u in urls if u not in done]
    log(f"{brand}: {len(urls)} candidate pages, {len(todo)} to visit")

    kept = 0
    with open(out_file, "a", encoding="utf-8") as f:
        for i, url in enumerate(todo, 1):
            rec = {"brand": brand, "url": url, "fetched_at": datetime.now(IST).isoformat(timespec="seconds")}
            if cfg.get("shopify_json"):
                body, status = fetch(url + ".json")
                rec["status"] = status
                if body:
                    try:
                        rec["shopify_product"] = json.loads(body).get("product")
                    except Exception:
                        pass
                is_product = bool(rec.get("shopify_product"))
            else:
                page, status = fetch(url)
                rec["status"] = status
                if cfg.get("extract") == "plix_next":
                    prod = plix_product(page) if page else None
                    rec["plix_product"] = prod
                    prods = [prod] if prod else []
                else:
                    prods = jsonld_products(page) if page else []
                    rec["jsonld_products"] = prods
                if page:
                    rec["title"] = meta(page, "og:title")
                    rec["description"] = meta(page, "og:description") or meta(page, "description")
                    rec["og_price"] = meta(page, "product:price:amount") or meta(page, "og:price:amount")
                is_product = bool(prods)
            rec["is_product"] = is_product
            kept += is_product
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            if i % 50 == 0:
                log(f"  {brand}: {i}/{len(todo)} visited, {kept} product pages so far")
            time.sleep(PER_SITE_DELAY)
    log(f"done {brand}: {kept} product pages kept this run")
    return brand, len(urls), kept


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="2026-10-17", help="snapshot folder (same as Phase 1)")
    ap.add_argument("--workers", type=int, default=5)
    ap.add_argument("--only", nargs="*")
    args = ap.parse_args()
    out_dir = ROOT / "data" / "raw" / args.date / "pages"
    out_dir.mkdir(parents=True, exist_ok=True)
    brands = {b: c for b, c in BRANDS.items() if not args.only or b in args.only}
    log(f"collecting {len(brands)} brands into {out_dir}")
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = {pool.submit(collect_brand, b, c, out_dir): b for b, c in brands.items()}
        for fut in as_completed(futs):
            try:
                b, n, k = fut.result()
            except Exception as e:
                log(f"FAILED {futs[fut]}: {e}")
    log("all done")


if __name__ == "__main__":
    main()
