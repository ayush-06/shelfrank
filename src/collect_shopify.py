"""Phase 1: polite, resumable collection of public Shopify catalogues.

Reads data/brands.csv and, for every brand with method shopify / shopify_collections_all,
pages through the store's public /products.json (250 per page) and saves a dated raw
snapshot to data/raw/<date>/shopify/<slug>.json.

Politeness rules:
- several *different* sites run in parallel (WORKERS), but each site gets one request
  every PER_SITE_DELAY seconds
- on HTTP 429 we honour Retry-After (or back off exponentially) and pause ALL workers,
  because Shopify appears to throttle by IP across stores
- finished brands are skipped on re-run, so the script can be stopped and resumed
"""

import argparse
import csv
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
PER_SITE_DELAY = 2.5
MAX_PAGES = 40
MAX_RETRIES = 6

pause_until = 0.0
pause_lock = threading.Lock()
print_lock = threading.Lock()


def log(msg):
    with print_lock:
        print(f"[{datetime.now(IST):%H:%M:%S}] {msg}", flush=True)


def slugify(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def wait_for_global_pause():
    while True:
        with pause_lock:
            remaining = pause_until - time.time()
        if remaining <= 0:
            return
        time.sleep(min(remaining, 5))


def set_global_pause(seconds):
    global pause_until
    with pause_lock:
        pause_until = max(pause_until, time.time() + seconds)


def fetch_json(url):
    for attempt in range(MAX_RETRIES):
        wait_for_global_pause()
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8", "ignore")), r.geturl()
        except urllib.error.HTTPError as e:
            if e.code == 429 or e.code >= 500:
                retry_after = e.headers.get("Retry-After")
                backoff = float(retry_after) if retry_after and retry_after.isdigit() else 30 * (2 ** attempt)
                backoff = min(backoff, 600)
                if e.code == 429:
                    set_global_pause(backoff)
                log(f"  {e.code} on {url} -> backing off {backoff:.0f}s (attempt {attempt + 1}/{MAX_RETRIES})")
                time.sleep(backoff)
                continue
            raise
        except (urllib.error.URLError, TimeoutError) as e:
            backoff = 15 * (attempt + 1)
            log(f"  network error on {url}: {e} -> retry in {backoff}s")
            time.sleep(backoff)
    raise RuntimeError(f"gave up after {MAX_RETRIES} attempts: {url}")


def collect_brand(row, out_dir):
    slug = slugify(row["brand"])
    out_file = out_dir / f"{slug}.json"
    if out_file.exists():
        log(f"skip {row['brand']} (already collected)")
        return row["brand"], "skipped", json.loads(out_file.read_text(encoding="utf-8"))["product_count"]

    path = "/collections/all/products.json" if row["method"] == "shopify_collections_all" else "/products.json"
    products, final_host = [], None
    for page in range(1, MAX_PAGES + 1):
        url = f"https://{row['domain']}{path}?limit=250&page={page}"
        data, final_url = fetch_json(url)
        final_host = final_host or final_url.split("/")[2]
        batch = data.get("products", [])
        products.extend(batch)
        if len(batch) < 250:
            break
        time.sleep(PER_SITE_DELAY)

    snapshot = {
        "brand": row["brand"],
        "domain": row["domain"],
        "final_host": final_host,
        "endpoint": path,
        "fetched_at": datetime.now(IST).isoformat(timespec="seconds"),
        "product_count": len(products),
        "products": products,
    }
    tmp = out_file.with_suffix(".tmp")
    tmp.write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")
    tmp.replace(out_file)
    log(f"done {row['brand']}: {len(products)} products")
    return row["brand"], "ok", len(products)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=datetime.now(IST).strftime("%Y-%m-%d"), help="snapshot folder date")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--only", nargs="*", help="limit to these brand names")
    args = ap.parse_args()

    with open(ROOT / "data" / "brands.csv", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["method"].startswith("shopify")]
    if args.only:
        rows = [r for r in rows if r["brand"] in set(args.only)]
    # focus brand and tier-1 peers first
    order = {"focus": 0, "skin-t1": 1, "hair-t1": 1}
    rows.sort(key=lambda r: min(order.get(t, 2) for t in r["tier"].split("|")))

    out_dir = ROOT / "data" / "raw" / args.date / "shopify"
    out_dir.mkdir(parents=True, exist_ok=True)
    log(f"collecting {len(rows)} brands into {out_dir} with {args.workers} parallel workers")

    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(collect_brand, r, out_dir): r for r in rows}
        for fut in as_completed(futures):
            r = futures[fut]
            try:
                results.append(fut.result())
            except Exception as e:  # keep going; report at the end
                log(f"FAILED {r['brand']}: {e}")
                results.append((r["brand"], f"failed: {e}", 0))

    summary_file = out_dir / "_summary.csv"
    with open(summary_file, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["brand", "status", "products"])
        w.writerows(sorted(results))
    ok = sum(1 for _, s, _ in results if s in ("ok", "skipped"))
    log(f"finished: {ok}/{len(results)} brands collected, {sum(n for *_, n in results)} products. Summary: {summary_file}")


if __name__ == "__main__":
    main()
