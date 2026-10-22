"""Part 2: build the 10 controlled shelves (one per Part 1 need), 8 products from 8 brands each.

Rule (applied by code, nobody hand-picks):
  1 Pilgrim            - Pilgrim's best-matching product
  3 favourites         - brands the AIs named most for this need in Part 1 (only brands in our catalogue)
  2 D2C peers          - Tier-1 peers for the segment, ranked by overall Part 1 visibility
  1 legacy             - big legacy brand, ranked by Part 1 mentions for this need, then overall
  1 wrong fit          - on purpose: 10-100% over budget (odd needs) or a different concern (even needs)

Within a brand: the product the AIs named for this need in Part 1 (if it is on our shelf list), else the
best keyword match. Within a product: the in-budget size closest to the category's typical size.

Writes data/part2/shelves.csv
"""

import re
import unicodedata
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent

# per need: category, budget, concern tags (from clean.py) and title/description keywords
NEEDS = {
    "N01": dict(need="serum for acne marks", cat="face serum", budget=600, concerns=["pigmentation", "acne"],
                kw=["niacinamide", "acne", "mark", "spot", "blemish", "salicylic", "azelaic", "kojic", "arbutin", "clarif"]),
    "N02": dict(need="serum for glowing skin", cat="face serum", budget=700, concerns=["dullness", "pigmentation"],
                kw=["vitamin c", "glow", "bright", "dark spot", "arbutin", "kojic", "radian", "even tone", "mark", "scar", "pigment"]),
    "N03": dict(need="sunscreen", cat="sunscreen", budget=500, concerns=["oily skin"],
                kw=["gel", "matte", "oily", "aqua", "fluid", "light", "invisible", "white cast", "no white", "water"]),
    "N04": dict(need="face wash for oily skin", cat="face wash", budget=350, concerns=["acne", "oily skin"],
                kw=["acne", "oil", "salicylic", "tea tree", "neem", "pimple", "clear", "pore"]),
    "N05": dict(need="moisturiser for dry skin", cat="moisturiser", budget=500, concerns=["dry skin", "sensitive skin"],
                kw=["ceramide", "barrier", "dry", "hydrat", "sensitive", "moistur", "oat", "shea", "repair"]),
    "N06": dict(need="hair growth serum", cat="hair serum", budget=800, concerns=["hairfall"],
                kw=["growth", "hair fall", "hairfall", "hair loss", "redensyl", "anagain", "rosemary", "procapil", "density", "regrow", "thick"]),
    "N07": dict(need="shampoo for hair fall", cat="shampoo", budget=500, concerns=["hairfall"],
                kw=["hair fall", "hairfall", "hair loss", "hairloss", "anti-hairfall", "rosemary", "onion", "strength", "redensyl", "breakage"]),
    "N08": dict(need="shampoo for dandruff", cat="shampoo", budget=400, concerns=["dandruff"],
                kw=["dandruff", "ketoconazole", "zinc", "piroctone", "tea tree", "itch", "scalp", "flake"]),
    "N09": dict(need="hair oil for hair growth", cat="hair oil", budget=400, concerns=["hairfall"],
                kw=["hair fall", "hairfall", "growth", "onion", "rosemary", "bhringraj", "amla", "kesh", "redensyl"]),
    "N10": dict(need="long-lasting lipstick", cat="lipstick", budget=600, concerns=[],
                kw=["matte", "long", "transfer", "smudge", "stay", "bullet", "creme", "velvet"]),
}
DRUG = re.compile(r"minoxidil|finasteride|ketoconazole 2%|prescription", re.I)  # medicines are not shelf products
WRONG_NOT_MATTE = re.compile(r"gloss|shine|glitter|sheer|balm|tint|plump|satin|metallic", re.I)
SEGMENT = {"face serum": "skin", "sunscreen": "skin", "face wash": "skin", "moisturiser": "skin",
           "hair serum": "hair", "shampoo": "hair", "hair oil": "hair", "lipstick": "makeup"}


def norm(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "", s)


def relevance(row, cfg):
    title, desc = str(row.title).lower(), str(row.description).lower()[:1500]
    concerns = str(row.concerns).lower()
    t = sum(k in title for k in cfg["kw"])
    c = sum(k in concerns for k in cfg["concerns"])
    d = min(2, sum(k in desc for k in cfg["kw"]))
    return 3 * min(t, 3) + 2 * c + d


def pick_variant(g, budget, mode="in"):
    """g = all eligible variants of one product. mode 'in' = within budget, 'over' = 10-100% over budget."""
    g = g[~(g.size_value > 3 * g.typical_size)]  # no bulk packs (also catches size/price data errors)
    if mode == "in":
        g = g[g.price <= budget]
    else:
        g = g[(g.price > budget * 1.1) & (g.price <= budget * 2.0)]
    if g.empty:
        return None
    g = g.assign(_d=(g.size_value - g.typical_size).abs().fillna(0))
    return g.sort_values(["_d", "price"]).iloc[0]


def main():
    p = pd.read_csv(ROOT / "data" / "clean" / "products.csv", low_memory=False)
    e = p[(p.eligible_for_shelf == True) & (p.gender.fillna("") != "men")].copy()
    brands = pd.read_csv(ROOT / "data" / "brands.csv")
    tier = dict(zip(brands.brand, brands.tier.fillna("")))
    key_of = {norm(b): b for b in brands.brand}
    key_of.update({"lakme": "Lakme", "loreal": "L'Oreal Paris", "lorealparis": "L'Oreal Paris", "tresemme": "TRESemme"})

    rec = pd.read_csv(ROOT / "results" / "part1" / "recommendations.csv")
    rec = rec[rec.brand.notna()].copy()
    rec["cbrand"] = rec.brand.map(lambda b: key_of.get(norm(b)))
    vis = pd.read_csv(ROOT / "results" / "part1" / "brand_visibility.csv")
    vis = vis[vis["mode"] == "memory"].copy()
    vis["cbrand"] = vis.brand.map(lambda b: key_of.get(norm(b)))
    overall = vis.groupby("cbrand").share_pct.sum().to_dict()

    rows = []
    for nid, cfg in NEEDS.items():
        pool = e[e.category == cfg["cat"]].copy()
        pool["score"] = pool.apply(relevance, axis=1, cfg=cfg)
        r = rec[rec.need == cfg["need"]]
        need_count = r.groupby("cbrand").qid.count().to_dict()
        # product the AIs named for this need (matched to our catalogue), per brand
        named = (r[(r.match_score >= 75) & (r.matched_category == cfg["cat"])]
                 .groupby(["cbrand", "matched_title"]).qid.count().reset_index()
                 .sort_values("qid", ascending=False))
        used = set()

        def best_product(brand, mode="in", min_score=None, wrong_concern=False):
            g = pool[pool.brand == brand]
            min_score = min_score if min_score is not None else (3 if cfg["cat"] == "lipstick" else 6)
            if g.empty:
                return None
            cands = []
            for pk, pg in g.groupby("product_key"):
                v = pick_variant(pg, cfg["budget"], "over" if mode == "over" else "in")
                if v is None:
                    continue
                if wrong_concern:
                    bad = (v.score == 0 and not set(cfg["concerns"]) & set(str(v.concerns).split("; "))) if cfg["cat"] != "lipstick" else bool(WRONG_NOT_MATTE.search(str(v.title)))
                    if not bad or "matte" in str(v.title).lower():
                        continue
                elif v.score < min_score:
                    continue
                if cfg["cat"] == "hair serum" and re.search(r"\boil\b", str(v.title), re.I) and "serum" not in str(v.title).lower():
                    continue  # hair oils that slipped into "hair serum"
                if cfg["cat"] not in ("hair serum", "shampoo", "hair oil") and re.search(r"scalp|\bhair\b", str(v.title), re.I):
                    continue  # hair products that slipped into a skin category
                types = {t for t in ("serum", "moisturi", "face wash", "cleanser", "sunscreen", "shampoo", "conditioner")
                         if t in str(v.title).lower()}
                if len(types) >= 2 and not ("sunscreen" in types and "serum" in types):
                    continue  # two-product combos
                if DRUG.search(f"{v.title} {str(v.description)[:600]}"):
                    continue
                desc_ok = len(str(v.description)) >= 150  # thin listings make thin cards; prefer a full one
                n_named = named[(named.cbrand == brand) & (named.matched_title == v.title)].qid.sum()
                # a good fit first; among good fits, the product the AIs named; Pilgrim bestsellers break ties
                cands.append((int(v.score >= 7), int(desc_ok), int(n_named), bool(v.is_pilgrim_bestseller), int(v.score), -float(v.price), v))
            if not cands:
                return None
            cands.sort(key=lambda c: c[:6], reverse=True)
            return cands[0][6]

        def add(role, brand, **kw):
            if brand in used or brand is None:
                return False
            v = best_product(brand, **kw)
            if v is None:
                return False
            used.add(brand)
            rows.append({"shelf": nid, "need": cfg["need"], "category": cfg["cat"], "budget_inr": cfg["budget"],
                         "role": role, "brand": brand, "product_key": v.product_key, "title": v.title,
                         "variant": v.variant, "size_value": v.size_value, "size_unit": v.size_unit,
                         "price": round(float(v.price)), "mrp": v.mrp, "relevance": v.score,
                         "named_in_part1": int(named[(named.cbrand == brand) & (named.matched_title == v.title)].qid.sum()),
                         "brand_need_mentions_part1": int(need_count.get(brand, 0)), "url": v.url,
                         "actives": v.actives, "concerns": v.concerns, "desc_chars": len(str(v.description)),
                         "description": v.description})
            return True

        add("pilgrim", "Pilgrim")
        ranked_need = sorted(need_count, key=lambda b: -need_count[b])
        n = 0
        for b in ranked_need:
            if n < 3 and b != "Pilgrim" and add("part1_favourite", b):
                n += 1
        seg = SEGMENT[cfg["cat"]]
        peer_tag = "makeup" if seg == "makeup" else f"{seg}-t1"
        peers = sorted([b for b, t in tier.items() if peer_tag in t.split("|") and "legacy" not in t],
                       key=lambda b: -overall.get(b, 0))
        n = 0
        for b in peers:
            if n < 2 and add("d2c_peer", b):
                n += 1
        legacy = sorted([b for b, t in tier.items() if t == "legacy"],  # true legacy only (Mamaearth is D2C-born)
                        key=lambda b: (-need_count.get(b, 0), -overall.get(b, 0)))
        for b in legacy:
            if add("legacy", b):
                break
        # wrong fit: if a global brand the AIs named for this need has a good-fit product over budget, it takes
        # this slot ("does the famous brand still win when it breaks the budget?"). Otherwise: odd shelves
        # over budget, even shelves a different concern / not matte.
        glob = [b for b in ranked_need if tier.get(b) == "global"]
        if not any(add("wrong_over_budget", b, mode="over") for b in glob):
            odd = int(nid[1:]) % 2 == 1
            rest = ranked_need + peers + legacy + sorted(e.brand.unique())
            for b in rest:
                if (add("wrong_over_budget", b, mode="over") if odd else add("wrong_concern", b, wrong_concern=True)):
                    break
        got = sum(1 for x in rows if x["shelf"] == nid)
        if got != 8:
            print(f"WARNING {nid}: only {got} products")

    out = pd.DataFrame(rows)
    (ROOT / "data" / "part2").mkdir(parents=True, exist_ok=True)
    out.to_csv(ROOT / "data" / "part2" / "shelves.csv", index=False, encoding="utf-8")
    pd.set_option("display.width", 250)
    print(out[["shelf", "role", "brand", "title", "variant", "price", "relevance", "named_in_part1"]].to_string())


if __name__ == "__main__":
    main()
