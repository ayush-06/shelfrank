"""Probe sitemap structure for non-Shopify / blocked brands (a few polite requests each)."""
import re, sys, time, urllib.request, urllib.error, gzip
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36 ShelfRank-research"
def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read()
        if url.endswith(".gz") or data[:2] == b"\x1f\x8b":
            data = gzip.decompress(data)
        return data.decode("utf-8", "ignore"), r.status
for dom in sys.argv[1:]:
    print(f"== {dom}")
    try:
        robots, _ = get(f"https://{dom}/robots.txt")
        sms = re.findall(r"(?im)^sitemap:\s*(\S+)", robots)
        print("  robots sitemaps:", sms[:5])
    except Exception as e:
        sms = []; print("  robots:", type(e).__name__, str(e)[:60])
    time.sleep(2)
    root = sms[0] if sms else f"https://{dom}/sitemap.xml"
    try:
        xml, st = get(root)
        locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", xml)
        kind = "index" if "<sitemapindex" in xml else "urlset"
        print(f"  {root} -> {kind}, {len(locs)} locs")
        children = [l for l in locs if re.search(r"product|pdp|catalog", l, re.I)] if kind == "index" else []
        for l in (children or locs)[:6]:
            print("   ", l)
        if kind == "index" and children:
            time.sleep(2)
            cx, _ = get(children[0])
            cl = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", cx)
            print(f"  first product sitemap: {len(cl)} urls, e.g. {cl[:2]}")
        elif kind == "urlset":
            prod = [l for l in locs if re.search(r"/products?/|/p/|\.html", l)]
            print(f"  product-like urls in urlset: {len(prod)}, e.g. {prod[:2]}")
    except Exception as e:
        print("  sitemap:", type(e).__name__, str(e)[:80])
    time.sleep(2)
