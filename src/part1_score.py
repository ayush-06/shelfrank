"""Part 1 scoring, step 2: match extracted recommendations to our catalogue and compute the metrics.

No API calls (free). Inputs: logs/part1/full_*.jsonl (answers + pages seen), logs/part1/extracted.jsonl,
data/part1/questions.csv, data/clean/products.csv.
Outputs (results/part1/):
  recommendations.csv   one row per recommended brand/product, with match + fact-check columns
  answers.csv           one row per answer (brands named, Pilgrim, etc.)
  brand_visibility.csv  % of answers naming each brand, by mode
  pilgrim_*.csv         Pilgrim breakdowns
  accuracy.csv          fact-check rates by model
  stability.csv         how similar repeated answers are
  web_found_vs_picked.csv
  summary.md            plain-language headline numbers
"""

import difflib
import json
import re
from collections import Counter
from pathlib import Path

import sys

import pandas as pd
from rapidfuzz import fuzz

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from clean import classify  # noqa: E402  (same category rules as the catalogue)
OUT = ROOT / "results" / "part1"

# canonical brand names; keys are regexes on the lower-cased brand string
ALIASES = [
    (r"derma\s*co", "The Derma Co"), (r"dot\s*(&|and)\s*key", "Dot & Key"), (r"l['’]?\s?or[eé]al", "L'Oreal Paris"),
    (r"pond", "Pond's"), (r"head\s*(&|and)\s*shoulders", "Head & Shoulders"), (r"mama\s*earth", "Mamaearth"),
    (r"bodywise", "Be Bodywise"), (r"man\s*matters", "Man Matters"), (r"\bwow\b", "WOW Skin Science"),
    (r"re['’]?\s?equil", "Re'equil"), (r"dr\.?\s*sheth", "Dr. Sheth's"), (r"kay\s*beauty", "Kay Beauty"),
    (r"^sugar\b|sugar cosmetics|sugar pop", "SUGAR"), (r"lakm[eē]", "Lakme"), (r"tresemm", "TRESemme"),
    (r"bajaj", "Bajaj Almond Drops"), (r"navratna|zandu", "Zandu Care (Navratna)"), (r"lotus", "Lotus Herbals"),
    (r"the ordinary", "The Ordinary"), (r"la roche", "La Roche-Posay"), (r"cerave", "CeraVe"), (r"cetaphil", "Cetaphil"),
    (r"neutrogena", "Neutrogena"), (r"chemist at play", "Chemist at Play"), (r"conscious chemist", "Conscious Chemist"),
    (r"juicy chemistry", "Juicy Chemistry"), (r"bare anatomy", "Bare Anatomy"), (r"earth rhythm", "Earth Rhythm"),
    (r"faces canada", "Faces Canada"), (r"swiss beauty", "Swiss Beauty"), (r"m\s?caffeine", "mCaffeine"),
    (r"thrive\s*co", "ThriveCo"), (r"pilgrim", "Pilgrim"), (r"minimalist", "Minimalist"), (r"maybelline", "Maybelline"),
    (r"nivea", "Nivea"), (r"garnier", "Garnier"), (r"himalaya", "Himalaya"), (r"biotique", "Biotique"), (r"plum\b", "Plum"),
    (r"foxtale", "Foxtale"), (r"deconstruct", "Deconstruct"), (r"aqualogica", "Aqualogica"), (r"hyphen", "Hyphen"),
    (r"traya", "Traya"), (r"arata", "Arata"), (r"plix", "Plix"), (r"bblunt", "Bblunt"), (r"indulekha", "Indulekha"),
    (r"parachute", "Parachute"), (r"dabur", "Dabur"), (r"kesh king", "Kesh King"), (r"clinic plus", "Clinic Plus"),
    (r"sunsilk", "Sunsilk"), (r"\bdove\b", "Dove"), (r"pantene", "Pantene"), (r"renee", "Renee"), (r"insight", "Insight"),
    (r"^mars\b|mars cosmetics", "Mars"), (r"colorbar", "Colorbar"), (r"sotrue", "Sotrue"), (r"fixderma", "Fixderma"),
]


def canon(b):
    s = (b or "").strip()
    low = s.lower()
    for rx, name in ALIASES:
        if re.search(rx, low):
            return name
    return s


def norm(s):
    s = re.sub(r"[^a-z0-9% ]", " ", (s or "").lower())
    return re.sub(r"\s+", " ", s).strip()


PCTS = re.compile(r"(\d+(?:\.\d+)?)\s?%")


def strip_brand(text, brand):
    """lower-case words of a product name without the brand words (so 'Mamaearth Onion Shampoo' -> 'onion shampoo')."""
    t = norm(text)
    for w in norm(brand).split():
        t = re.sub(rf"\b{re.escape(w)}\b", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def load_jsonl(p):
    return [json.loads(l) for l in Path(p).read_text(encoding="utf-8").splitlines() if l.strip()]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    q = pd.read_csv(ROOT / "data" / "part1" / "questions.csv").set_index("qid")
    ans = {}
    for f in ["full_memory.jsonl", "full_web.jsonl"]:
        for r in load_jsonl(ROOT / "logs" / "part1" / f):
            if r.get("answer"):
                ans[(r["mode"], r["qid"], r["model"], r["repeat"])] = r
    ext = {(r["mode"], r["qid"], r["model"], r["repeat"]): r["extracted"] for r in load_jsonl(ROOT / "logs" / "part1" / "extracted.jsonl")
           if r.get("extracted") is not None}

    cat = pd.read_csv(ROOT / "data" / "clean" / "products.csv", low_memory=False)
    cat = cat[~cat.is_freebie & ~cat.is_combo]
    by_brand = {b: g for b, g in cat.groupby("brand")}
    catalogue_brands = set(by_brand)

    recs, answers = [], []
    for key, a in ans.items():
        mode, qid, model, rep = key
        qq = q.loc[qid]
        e = ext.get(key) or {}
        items = [x for x in (e.get("recommendations") or []) if (x.get("brand") or "").strip()]
        brands_in_order = []
        for x in items:
            b = canon(x["brand"])
            if b not in brands_in_order:
                brands_in_order.append(b)
            row = {"mode": mode, "qid": qid, "need": qq.need, "category": qq.category, "language": qq.language, "style": qq["style"],
                   "budget": qq.budget_inr, "model": model.split("/")[1], "repeat": rep, "rank": brands_in_order.index(b) + 1,
                   "brand": b, "brand_raw": x["brand"], "product_raw": x.get("product"), "specific": bool(x.get("specific")),
                   "claimed_price": x.get("price_inr"), "claimed_strength": x.get("claimed_strength"), "in_catalogue_brand": b in catalogue_brands}
            prod_txt = (row["product_raw"] or "").strip()
            if prod_txt and not strip_brand(prod_txt, b):
                row["specific"] = False  # "product" was just the brand name again
            # match the named product to our catalogue: same product type first, then word-overlap similarity
            if row["in_catalogue_brand"] and row["specific"] and prod_txt:
                g = by_brand[b]
                ai_cat = classify(prod_txt)[1]
                if ai_cat == "unclassified":  # vague name (e.g. "Soft"): assume the type the shopper asked for
                    ai_cat = qq.category
                row["ai_category"] = ai_cat
                cand = g[g.category == ai_cat] if ai_cat != "unclassified" and (g.category == ai_cat).any() else g
                target = strip_brand(prod_txt, b)
                titles = cand.title.dropna().astype(str).drop_duplicates()
                scores = titles.apply(lambda t: fuzz.token_set_ratio(target, strip_brand(t, b)))
                best = scores.idxmax()
                row["match_score"] = int(scores[best])
                if row["match_score"] >= 75:
                    title = titles[best]
                    m = cand[cand.title == title]
                    fam = g[g.product_key == m.product_key.iloc[0]]  # every size/variant of that product
                    row["matched_title"] = title
                    row["matched_category"] = m.category.iloc[0]
                    prices = fam.price.dropna()
                    row["our_price_min"], row["our_price_max"] = (prices.min(), prices.max()) if len(prices) else (None, None)
                    cp = row["claimed_price"]
                    vals = pd.concat([fam.price, fam.mrp]).dropna()
                    if cp and len(vals):  # right if within 20% of ANY size's selling price or MRP
                        row["price_ok"] = bool(((vals - float(cp)).abs() / vals <= 0.20).any())
                    claimed = set(PCTS.findall(row["claimed_strength"] or ""))
                    ours = set(PCTS.findall(title))
                    if claimed and ours:
                        row["strength_ok"] = bool(claimed & ours)
                    if pd.notna(qq.budget_inr) and len(prices):
                        row["within_budget"] = bool(prices.min() <= float(qq.budget_inr))
                    row["category_fit"] = row["matched_category"] == qq.category
            recs.append(row)
        pages = [((c.get("url_citation") or c).get("title") or "") + " " + ((c.get("url_citation") or c).get("url") or "")
                 for c in (a.get("citations") or [])]
        found = sorted({canon(m) for p in pages for m in [p] if canon(p) != p}) if pages else []
        answers.append({"mode": mode, "qid": qid, "need": qq.need, "category": qq.category, "language": qq.language, "style": qq["style"],
                        "model": model.split("/")[1], "repeat": rep, "brands": brands_in_order, "n_brands": len(brands_in_order),
                        "advice_only": bool(e.get("advice_only")) or not brands_in_order, "pilgrim": "Pilgrim" in brands_in_order,
                        "pilgrim_rank": brands_in_order.index("Pilgrim") + 1 if "Pilgrim" in brands_in_order else None,
                        "pages_brands": found, "n_pages": len(pages), "extracted": key in ext})
    R, A = pd.DataFrame(recs), pd.DataFrame(answers)
    R.to_csv(OUT / "recommendations.csv", index=False, encoding="utf-8-sig")
    A.to_csv(OUT / "answers.csv", index=False, encoding="utf-8-sig")

    # visibility: % of answers in each mode that name the brand (any rank), and % where it is named first
    vis = []
    for mode, a in A.groupby("mode"):
        n = len(a)
        c_any = Counter(b for bl in a.brands for b in bl)
        c_first = Counter(bl[0] for bl in a.brands if bl)
        for b, k in c_any.items():
            vis.append({"mode": mode, "brand": b, "answers": n, "share_pct": round(100 * k / n, 1),
                        "first_pct": round(100 * c_first.get(b, 0) / n, 1), "in_our_catalogue": b in catalogue_brands})
    V = pd.DataFrame(vis).sort_values(["mode", "share_pct"], ascending=[True, False])
    V.to_csv(OUT / "brand_visibility.csv", index=False, encoding="utf-8-sig")

    # Pilgrim breakdowns
    for dim in ["need", "model", "language", "style"]:
        t = A.groupby(["mode", dim]).agg(answers=("pilgrim", "size"), pilgrim_pct=("pilgrim", "mean")).reset_index()
        t["pilgrim_pct"] = (100 * t.pilgrim_pct).round(1)
        t.to_csv(OUT / f"pilgrim_by_{dim}.csv", index=False, encoding="utf-8-sig")
    pr = R[R.brand == "Pilgrim"]
    pr.to_csv(OUT / "pilgrim_mentions.csv", index=False, encoding="utf-8-sig")

    # accuracy among catalogue-brand, specific recommendations
    s = R[R.in_catalogue_brand & R.specific & R.product_raw.notna()].copy()
    s["matched"] = s.get("matched_title").notna() if "matched_title" in s else False
    acc = s.groupby("model").agg(specific_recs=("brand", "size"), matched_pct=("matched", "mean"),
                                 price_checked=("price_ok", "count"), price_ok_pct=("price_ok", "mean"),
                                 strength_checked=("strength_ok", "count"), strength_ok_pct=("strength_ok", "mean"),
                                 budget_checked=("within_budget", "count"), within_budget_pct=("within_budget", "mean"))
    for c in ["matched_pct", "price_ok_pct", "strength_ok_pct", "within_budget_pct"]:
        acc[c] = (100 * acc[c]).round(1)
    acc.to_csv(OUT / "accuracy.csv", encoding="utf-8-sig")

    # stability: average overlap of brand sets between repeats (memory, models with 3 repeats)
    st = []
    for (qid, model), g in A[A["mode"] == "memory"].groupby(["qid", "model"]):
        sets = [set(b) for b in g.sort_values("repeat").brands]
        if len(sets) >= 2:
            pairs = [(i, j) for i in range(len(sets)) for j in range(i + 1, len(sets))]
            jac = [len(sets[i] & sets[j]) / len(sets[i] | sets[j]) if (sets[i] | sets[j]) else 1.0 for i, j in pairs]
            st.append({"qid": qid, "model": model, "overlap": sum(jac) / len(jac)})
    S = pd.DataFrame(st)
    S.groupby("model").overlap.mean().round(2).to_csv(OUT / "stability.csv", encoding="utf-8-sig")

    # web: was the brand FOUND in the pages the AI was given, and PICKED when found?
    W = A[A["mode"].str.startswith("web")]
    fv = []
    for b in sorted(catalogue_brands | {"Pilgrim"}):
        f = W[W.pages_brands.apply(lambda x: b in x)]
        p = W[W.brands.apply(lambda x: b in x)]
        if len(f) or len(p):
            picked_when_found = f.brands.apply(lambda x: b in x).mean() if len(f) else None
            fv.append({"brand": b, "web_answers": len(W), "found_pct": round(100 * len(f) / len(W), 1),
                       "picked_pct": round(100 * len(p) / len(W), 1),
                       "picked_when_found_pct": round(100 * picked_when_found, 1) if picked_when_found is not None else None})
    F = pd.DataFrame(fv).sort_values("picked_pct", ascending=False)
    F.to_csv(OUT / "web_found_vs_picked.csv", index=False, encoding="utf-8-sig")

    print(f"answers {len(A)} (extracted {A.extracted.sum()}), recommendations {len(R)}, specific {R.specific.sum()}")
    print("\nTop brands by mode (share % / first %):")
    for mode, v in V.groupby("mode"):
        print(f"  [{mode}] " + ", ".join(f"{r.brand} {r.share_pct}/{r.first_pct}" for r in v.head(12).itertuples()))
    print("\nPilgrim % of answers by mode:", (A.groupby("mode").pilgrim.mean() * 100).round(1).to_dict())
    print("\nAccuracy by model:\n", acc.to_string())
    print("\nStability (brand-set overlap between repeats, 1 = identical):", S.groupby("model").overlap.mean().round(2).to_dict())
    print("\nWeb found vs picked (top):\n", F.head(15).to_string(index=False))


if __name__ == "__main__":
    main()
