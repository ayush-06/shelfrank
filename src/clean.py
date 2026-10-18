"""Phase 2: merge all raw sources into one clean, flagged product table.

Nothing is deleted. Every row is one product size/shade (variant) with flags:
  is_freebie, is_hidden, is_combo, is_duplicate, in_stock, segment/category, in_v1_scope
and a final `eligible_for_shelf`. Rules are keyword-based and transparent (decision E);
rows the rules can't place get category "unclassified" and are reported.

Outputs (data/clean/):
  products.csv          all rows + flags + derived fields
  cleaning_report.csv   per-brand counts after each step
"""

import csv
import html
import json
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "2026-10-17"
OUT = ROOT / "data" / "clean"

# ---------- category rules (order matters: first match wins) ----------
R = lambda p: re.compile(p, re.I)
CATEGORY_RULES = [
    # out of scope first
    ("other", "accessory", R(r"\b(jute )?bag\b|pouch|\bcomb\b|brush|sponge|blender|mirror|towel|headband|scrunchie|gift ?card|voucher|tote|organi[sz]er|sharpener|tweezer|curler")),
    ("other", "fragrance", R(r"perfume|eau de|\bedp\b|\bedt\b|body mist|deo(dorant)?\b|fragrance mist|attar|\bcologne")),
    ("other", "body care", R(r"body ?wash|body gel|shower gel|body lotion|body butter|body oil|\bsoap\b|bath |hand cream|hand wash|foot|underarm|body scrub|body serum|body cream|intimate|hair removal|\bwax strips|body polish|talc|sanitizer|massage oil")),
    ("other", "men grooming", R(r"beard|shav|after ?shave|moustache")),
    ("other", "baby", R(r"\bbaby\b|\bkids?\b|diaper")),
    ("other", "wellness", R(r"gumm(y|ies)|capsule|tablet|supplement|protein|effervescent|sachet|\btea\b(?! ?tree)|multivitamin|\bdrink\b|chewable|probiotic|juice|immunity|giloy|chyawan|syrup|\bhoney\b|ketchup|chutney|vinegar|hommade|culinary|pickle|tooth ?paste|meswak|mouth ?wash|churna|mosquito|animal|\bpet\b|\bmints?\b|beverage|food")),
    ("hair", "hair colour", R(r"hair colou?r|henna|hair dye|root touch|colou?r naturals|mehendi|mehndi")),
    ("makeup", "nail", R(r"\bnail")),
    # makeup and lips before skin (lip serum, serum foundation, spf lip balm)
    ("makeup", "other lip makeup", R(r"lip liner|lip ?pencil|lip gloss|\bgloss\b|lip plumper|lip tint|lip stain")),
    ("makeup", "lipstick", R(r"lipstick|lip crayon|lip colou?r|liquid lip|matte lip|clickstick|bullet lip")),
    ("skin", "lip care", R(r"lip balm|lip mask|lip scrub|lip serum|lip butter|lip oil|lip sleeping|lip care|lip treatment")),
    ("makeup", "kajal/eyeliner", R(r"kajal|kohl|eye ?liner")),
    ("makeup", "mascara", R(r"mascara")),
    ("makeup", "foundation/bb", R(r"foundation|\bbb cream|\bcc cream|skin tint|tinted moisturi|serum foundation")),
    ("makeup", "concealer", R(r"concealer")),
    ("makeup", "compact/powder", R(r"compact|loose powder|setting powder|pressed powder|\bpowder\b")),
    ("makeup", "blush/highlighter", R(r"blush|bronzer|highlighter|contour|strobe")),
    ("makeup", "eyeshadow", R(r"eye ?shadow|palette")),
    ("makeup", "other makeup", R(r"primer|setting spray|brow|makeup fixer|\bfixer\b")),
    # hair
    ("hair", "shampoo", R(r"shampoo")),
    ("hair", "conditioner", R(r"conditioner")),
    ("hair", "hair mask", R(r"hair mask|hair spa|hair masque")),
    ("hair", "hair styling", R(r"hair (gel|wax|spray)|styling|curl (defin|cream|gel)")),
    ("hair", "hair oil", R(r"hair oil|scalp oil|oil for hair|coconut oil|almond drops|amla (hair )?oil|onion oil|rosemary oil|bhringraj|hair & scalp oil|hair and scalp oil|navratna|kesh king|indulekha")),
    ("hair", "hair serum", R(r"hair serum|hair growth|scalp serum|hair tonic|rosemary water|redensyl|anagain|minoxidil|regrowth|hair regrowth|hair fall (control )?(spray|solution|serum)")),
    ("hair", "hair styling", R(r"hair (gel|wax|spray|cream)|styling|leave[- ]in|curl")),
    ("hair", "hair serum", R(r"(hair|scalp|root|hair ?fall).{0,40}serum|serum.{0,40}(hair|scalp)")),
    # skin
    ("skin", "face wash", R(r"face ?wash|cleanser|cleansing|micellar|foaming|face foam|makeup remover")),
    ("skin", "scrub/exfoliator", R(r"scrub|exfoliat|peeling|\bpeel\b")),
    ("skin", "toner/mist", R(r"toner|face mist|essence\b|rose ?water|tonique")),
    ("skin", "face mask", R(r"face mask|sheet mask|clay mask|peel[- ]off|sleeping mask|face pack|ubtan mask|\bmask\b|masque")),
    ("skin", "under-eye", R(r"under ?eye|eye cream|eye gel|eye serum|eye patch|dark circle")),
    ("skin", "sunscreen", R(r"sun ?shield|sunscreen|sun ?screen|sunblock|sun stick|sun gel|sun fluid|sun cream|sun protect|uv (shield|defen)")),
    ("skin", "face serum", R(r"serum|ampoule|booster|\bdrops\b|elixir|face oil")),
    ("skin", "moisturiser", R(r"moisturi[sz]|cream|creme|crème|gel[- ]cream|day cream|night cream|emulsion|face lotion|moisture")),
    ("skin", "spot treatment", R(r"spot|acne patch|pimple patch|spot corrector")),
    ("skin", "sunscreen", R(r"\bspf\s?\d")),  # last resort: SPF with nothing else
]
V1_SCOPE = {"face serum", "sunscreen", "face wash", "moisturiser", "hair serum", "shampoo", "hair oil", "lipstick"}
TYPICAL_SIZE = {"face serum": 30, "sunscreen": 50, "face wash": 100, "moisturiser": 50,
                "hair serum": 50, "shampoo": 250, "hair oil": 200, "lipstick": None}

ACTIVES = {
    "niacinamide": r"niacinamide", "vitamin c": r"vitamin c|ascorbic|vit\.? c\b", "retinol": r"retin(ol|al|oid)",
    "bakuchiol": r"bakuchiol", "salicylic acid": r"salicylic|\bbha\b", "aha": r"glycolic|\baha\b|lactic acid|mandelic",
    "hyaluronic acid": r"hyaluron", "ceramide": r"ceramide", "peptide": r"peptide", "azelaic acid": r"azelaic",
    "alpha arbutin": r"arbutin", "kojic acid": r"kojic", "tranexamic acid": r"tranexamic", "centella/cica": r"centella|\bcica\b",
    "tea tree": r"tea tree", "rice water": r"rice water|\brice\b", "zinc": r"\bzinc", "squalane": r"squalane",
    "redensyl": r"redensyl", "anagain": r"anagain", "procapil/baicapil/capilia": r"procapil|baicapil|capilia",
    "minoxidil": r"minoxidil", "ketoconazole": r"ketoconazole", "rosemary": r"rosemary", "onion": r"onion",
    "keratin": r"keratin", "biotin": r"biotin", "argan": r"argan", "coconut": r"coconut", "almond": r"almond",
    "amla": r"\bamla\b", "bhringraj": r"bhringraj", "caffeine": r"caffeine|coffee", "patua": r"patu[aá]",
    "aloe vera": r"aloe", "vitamin e": r"vitamin e\b", "spf": r"\bspf\s?\d+", "collagen": r"collagen",
}
CONCERNS = {
    "acne": r"acne|pimple|breakout|blemish", "oily skin": r"oily|oil[- ]control|oil[- ]free|sebum|mattif",
    "dry skin": r"dry skin|dryness|dehydrat|parched", "pigmentation": r"pigment|dark spot|\bspots\b|de-?tan|\btan\b|uneven",
    "dullness": r"\bdull|glow|radian|brighten", "sensitive skin": r"sensitive|sooth|calm|redness|irritat",
    "anti-ageing": r"ageing|aging|wrinkle|fine lines|firm|youth", "pores": r"\bpores?\b",
    "dark circles": r"dark circle|puffi", "hairfall": r"hair ?fall|hair loss|thinning|hair growth|regrowth",
    "dandruff": r"dandruff|flak|itchy scalp", "frizz": r"frizz|smooth", "hair damage": r"damage|repair|split end|breakage",
    "grey hair": r"\bgr[ea]y\b", "sun protection": r"\bspf|uva|uvb|sun protect",
}
CLAIMS = {
    "fragrance-free": r"fragrance[- ]free", "paraben-free": r"paraben[- ]free", "sulphate-free": r"sulph?ate[- ]free",
    "silicone-free": r"silicone[- ]free", "vegan": r"\bvegan", "cruelty-free": r"cruelty[- ]free",
    "dermatologist tested": r"dermatologi(st|cally) (tested|approved|recommended)", "non-comedogenic": r"non[- ]comedogenic",
    "clinically tested": r"clinical(ly)? (tested|proven)", "ayurvedic/natural": r"ayurved|natural|herbal|plant[- ]based",
    "alcohol-free": r"alcohol[- ]free", "pregnancy safe": r"pregnan",
}
COMBO = R(r"combo|\bkit\b|(?<!face )\bpack\b|\d\s?(in\s?1\s?)?pack\b|bundle|\bduo\b|\btrio\b|regime|regimen|routine|pack of|set of|value pack|hamper|gift set|\bset\b|starter pack|\bx\s?[2-9]\b|\b[2-9]\s?x\b|bestsellers? box|essentials box|\bbox\b")
# freebie: judged on title + product TYPE only (tags are noisy: "Free Pouch", "FREEBIE COLLECTION" sit on normal products)
FREEBIE_TITLE = R(r"free ?gift|freebie|\bsample\b|tester|complimentary|mystery box|gift box|\bgwp\b")
FREEBIE_TYPE = R(r"gift|freebie|sample|tryplum|gwp")
# exact hidden markers only ("Bestseller Upsell" is a normal merchandising tag on main listings, so plain "upsell" is NOT hidden)
# ("no-index" is an SEO setting - Conscious Chemist puts it on 551/638 products - so it does NOT mean hidden)
HIDDEN = R(r"hidden-product|\bhidden\b|upsell-product|hide__?product|hide-product|app-button-hide")
SALON = R(r"salon[- ]professional")  # Pilgrim's salon-only line (type "Salon professional" / tag "salon-professional")
TITLE_OVERRIDES = [(R(r"peeling solution|peel solution|exfoliating solution"), ("skin", "scrub/exfoliator"))]
SIZE = re.compile(r"(\d+(?:\.\d+)?)\s?(ml|g|gm|gms|grams?|kg|l|ltr|litre|liter)\b", re.I)
PCT = re.compile(r"(\d+(?:\.\d+)?)\s?%\s?([A-Za-z][A-Za-z\-]+(?: [A-Za-z\-]+)?)")
MEN = R(r"\bmen\b|\bmen's|\bmens\b|for him|\bman\b")


def text(s):
    s = re.sub(r"<[^>]+>", " ", str(s or ""))
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def num(x):
    try:
        v = float(str(x).replace(",", ""))
        return v if v == v else None
    except (TypeError, ValueError):
        return None


def classify(*fields):
    for i, f in enumerate(fields):
        f = f or ""
        for seg, cat, rx in CATEGORY_RULES:
            if rx.search(f):
                return seg, cat, ["type", "title", "tags", "description"][min(i, 3)]
    return "unknown", "unclassified", None


def size_of(*fields):
    for f in fields:
        m = SIZE.search(f or "")
        if m:
            v, u = float(m.group(1)), m.group(2).lower()
            if u in ("kg",):
                return v * 1000, "g"
            if u in ("l", "ltr", "litre", "liter"):
                return v * 1000, "ml"
            return v, ("ml" if u == "ml" else "g")
    return None, None


def tags_from(d, blob):
    return "; ".join(k for k, rx in d.items() if re.search(rx, blob, re.I))


def rows_shopify():
    for f in sorted((RAW / "shopify").glob("*.json")):
        snap = json.loads(f.read_text(encoding="utf-8"))
        host = snap.get("final_host") or snap["domain"]
        for p in snap["products"]:
            tags = p.get("tags") or []
            tags = ", ".join(tags) if isinstance(tags, list) else str(tags)
            for v in p.get("variants", []):
                yield {
                    "brand": snap["brand"], "source": "shopify", "product_id": p.get("id"), "variant_id": v.get("id"),
                    "title": text(p.get("title")), "variant": text(v.get("title")), "type_tags": f"{p.get('product_type') or ''} | {tags}",
                    "description": text(p.get("body_html")), "price": num(v.get("price")), "mrp": num(v.get("compare_at_price")),
                    "in_stock": bool(v.get("available")), "url": f"https://{host}/products/{p.get('handle')}",
                    "rating": None, "review_count": None, "size_hint": "", "confidence": "",
                    "raw_hidden": bool(HIDDEN.search(tags)),
                }


def rows_pages():
    for f in sorted((RAW / "pages").glob("*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            if not r.get("is_product"):
                continue
            base = {"brand": r["brand"], "source": "page", "url": r["url"], "raw_hidden": False, "confidence": ""}
            if r.get("plix_product"):
                p = r["plix_product"]
                v = (p.get("variants") or [{}])[0]  # default variant only; others are multi-unit packs
                vp = (v.get("pricing") or {})
                yield {**base, "product_id": p.get("slug"), "variant_id": v.get("sku"), "title": text(p.get("name")),
                       "variant": text(v.get("name")), "type_tags": f"{p.get('category') or ''} | {', '.join(p.get('collections') or [])}",
                       "description": text(p.get("description") or p.get("seo_description")),
                       "price": num(((vp.get("price") or {}).get("gross") or {}).get("amount")),
                       "mrp": num(((vp.get("priceUndiscounted") or {}).get("gross") or {}).get("amount")),
                       "in_stock": bool(v.get("isAvailable", p.get("is_available"))), "rating": None,
                       "review_count": p.get("review_count"), "size_hint": ""}
                continue
            if r.get("shopify_product"):
                p = r["shopify_product"]
                for v in p.get("variants", []):
                    yield {**base, "product_id": p.get("id"), "variant_id": v.get("id"), "title": text(p.get("title")),
                           "variant": text(v.get("title")), "type_tags": f"{p.get('product_type') or ''} | {p.get('tags') or ''}",
                           "description": text(p.get("body_html")), "price": num(v.get("price")), "mrp": num(v.get("compare_at_price")),
                           "in_stock": None, "rating": None, "review_count": None, "size_hint": ""}
                continue
            p = r["jsonld_products"][0]
            offers = p.get("offers")
            offers = offers[0] if isinstance(offers, list) and offers else offers
            offers = offers if isinstance(offers, dict) else {}
            price = offers.get("price") or offers.get("lowPrice") or r.get("og_price")
            avail = str(offers.get("availability") or "")
            ar = p.get("aggregateRating") or {}
            props = p.get("additionalProperty") or []
            ingredients = " ".join(str(x.get("value")) for x in props if isinstance(x, dict) and "ingredient" in str(x.get("name", "")).lower())
            yield {**base, "product_id": p.get("sku") or r["url"], "variant_id": p.get("sku"), "title": text(p.get("name")),
                   "variant": "", "type_tags": f"{p.get('category') or ''} | {r['url']}",
                   "description": text(p.get("description") or r.get("description")) + (f" Ingredients: {ingredients}" if ingredients else ""),
                   "price": num(price), "mrp": num(offers.get("highPrice")),
                   "in_stock": (None if not avail else avail.endswith("InStock")),
                   "rating": num(ar.get("ratingValue")), "review_count": num(ar.get("reviewCount") or ar.get("ratingCount")),
                   "size_hint": str(p.get("size") or "")}


def rows_manual():
    df = pd.read_csv(ROOT / "data" / "manual" / "legacy_brands.csv")
    for i, m in df.iterrows():
        if m["brand"] == "Pond's":
            continue  # Pond's now comes from its own store (ponds.in)
        yield {"brand": m["brand"], "source": "manual", "product_id": f"manual-{i}", "variant_id": f"manual-{i}",
               "title": text(m["product_name"]), "variant": "", "type_tags": str(m["product_type"]),
               "description": text(f"{m['short_description']} Key ingredients: {m['key_ingredients']}. Claims: {m['claims']}. Concerns: {m['concerns']}."),
               "price": num(m["mrp_inr"]), "mrp": num(m["mrp_inr"]), "in_stock": True, "url": m["source_url"],
               "rating": None, "review_count": None, "size_hint": f"{m['size']} {m['unit']}",
               "confidence": m["confidence"], "raw_hidden": False}


def main():
    df = pd.DataFrame([*rows_shopify(), *rows_pages(), *rows_manual()])
    n0 = len(df)

    # classification: title first, then type/tags, then description start
    # the brand's own product TYPE first when it is specific (e.g. "Lipstick"), then title, then tags, then description
    cls = df.apply(lambda r: classify(r["type_tags"].split("|")[0], r["title"], r["type_tags"], r["description"][:300]),
                   axis=1, result_type="expand")
    df[["segment", "category", "category_from"]] = cls
    # salon-only products are out of scope (decided with the user 2026-10-19)
    salon = df.type_tags.str.contains(SALON)
    df.loc[salon, ["segment", "category", "category_from"]] = ["other", "salon professional", "type/tags"]
    for rx, (seg, cat) in TITLE_OVERRIDES:
        hit = df.title.str.contains(rx)
        df.loc[hit, ["segment", "category", "category_from"]] = [seg, cat, "title override"]
    # out-of-scope words in the TITLE always win (e.g. type says "Cream" but title says "Baby ... Face Cream")
    other_rules = [(seg, cat, rx) for seg, cat, rx in CATEGORY_RULES if seg == "other"]
    for i, t in df.title.items():
        for seg, cat, rx in other_rules:
            if rx.search(t) and df.at[i, "segment"] != "other":
                df.at[i, "segment"], df.at[i, "category"], df.at[i, "category_from"] = seg, cat, "title (out-of-scope override)"
                break
    # manual rows: trust the hand-entered product_type mapping where rules miss
    manual_map = {"face wash": ("skin", "face wash"), "face serum": ("skin", "face serum"), "moisturiser": ("skin", "moisturiser"),
                  "sunscreen": ("skin", "sunscreen"), "shampoo": ("hair", "shampoo"), "conditioner": ("hair", "conditioner"),
                  "hair oil": ("hair", "hair oil"), "hair serum": ("hair", "hair serum"), "hair mask": ("hair", "hair mask"),
                  "body lotion": ("other", "body care"), "hair colour": ("hair", "hair colour"), "micellar water": ("skin", "face wash"),
                  "sheet mask": ("skin", "face mask"), "bb/cc cream": ("makeup", "foundation/bb")}
    for i in df.index[df.source == "manual"]:
        seg_cat = manual_map.get(df.at[i, "type_tags"])
        if seg_cat:
            df.at[i, "segment"], df.at[i, "category"], df.at[i, "category_from"] = (*seg_cat, "manual")

    blob = (df.title + " " + df.variant + " " + df.description.str.slice(0, 600))
    df["gender"] = ["men" if (MEN.search(t) or b == "Man Matters") else "unisex/women" for t, b in zip(df.title, df.brand)]
    sizes = [size_of(r.variant, r.title, r.size_hint, r.description[:400]) for r in df.itertuples()]
    df["size_value"], df["size_unit"] = zip(*sizes)
    df["price_per_100"] = (df.price / df.size_value * 100).round(1)
    df["discount_pct"] = ((1 - df.price / df.mrp) * 100).where(df.mrp > df.price).round(0)
    df["actives"] = [tags_from(ACTIVES, t + " " + v) or tags_from(ACTIVES, b) for t, v, b in zip(df.title, df.variant, blob)]
    df["strengths"] = ["; ".join(f"{m[1].lower()} {m[0]}%" for m in PCT.findall(t)) for t in df.title]
    hair_c, skin_c = {"hairfall", "dandruff", "frizz", "hair damage", "grey hair"}, set(CONCERNS) - {"hairfall", "dandruff", "frizz", "hair damage", "grey hair"}
    df["concerns"] = [tags_from({k: v for k, v in CONCERNS.items() if k in (hair_c if seg == "hair" else skin_c if seg == "skin" else ())}, b)
                      for b, seg in zip(blob, df.segment)]
    df["claims"] = [tags_from(CLAIMS, t + " " + d) for t, d in zip(df.title, df.description)]
    df["description_chars"] = df.description.str.len()

    # flags
    ptype = df.type_tags.str.split("|").str[0].fillna("")
    df["is_freebie"] = ((df.price.notna() & (df.price <= 1)) | df.title.str.contains(FREEBIE_TITLE) | ptype.str.contains(FREEBIE_TYPE))
    # brands whose own store marks EVERY product unavailable (e.g. Pond's, TRESemme) don't sell there:
    # treat their stock as unknown instead of out-of-stock, so they aren't wrongly dropped
    avail_rate = df[df.source == "shopify"].groupby("brand").in_stock.apply(lambda s: (s == True).mean())
    non_selling = set(avail_rate[avail_rate == 0].index)
    df["stock_unknown"] = df.brand.isin(non_selling) | df.in_stock.isna()
    df["in_stock_effective"] = (df.in_stock == True) | df.stock_unknown
    df["is_combo"] = df.apply(lambda r: bool(COMBO.search(f"{r.title} {r.type_tags.split('|')[0]}")), axis=1)
    # punctuation first, then sizes, so "50gm" and "50.gm" (an A/B-test pair of listings) normalise to the same key
    norm = (df.title.str.lower().str.replace(r"[^a-z0-9]+", " ", regex=True).str.replace(SIZE, "", regex=True)
            .str.replace(r"\s+", " ", regex=True).str.strip())
    df["product_key"] = df.brand + "|" + norm
    # hidden: some brands (e.g. Pilgrim) tag real, sold products "hidden-product". A hidden listing is only dropped
    # when a VISIBLE listing of the same product exists; if every listing is hidden we keep one and flag it.
    hidden_tag = df.raw_hidden | ((df.source == "shopify") & df.type_tags.str.contains(HIDDEN))
    has_visible = (~hidden_tag).groupby(df.product_key).transform("any")
    df["is_hidden"] = hidden_tag & has_visible
    df["all_listings_hidden"] = hidden_tag & ~has_visible
    # duplicates: same brand + normalised name + variant + size; keep the visible, in-stock, cheapest-listed one
    df["_rank"] = hidden_tag.astype(int) * 4 + (~df.in_stock.fillna(False)).astype(int) * 2 + df.is_freebie.astype(int)
    order = df.sort_values(["_rank", "price"]).index
    first = df.loc[order].duplicated(["product_key", "variant", "size_value"], keep="first")
    df["is_duplicate"] = first.reindex(df.index)
    excl = pd.read_csv(ROOT / "data" / "manual" / "exclusions.csv")
    df["manual_excluded"] = False
    for e in excl.itertuples():
        df.loc[(df.brand == e.brand) & df.title.str.contains(e.title_contains, regex=False), "manual_excluded"] = True
    df["in_v1_scope"] = df.category.isin(V1_SCOPE)
    df["typical_size"] = df.category.map(TYPICAL_SIZE)
    df["shelf_ok_confidence"] = ~((df.source == "manual") & (~df.confidence.isin(["high", "medium"])))
    df["has_price"] = df.price.fillna(0) > 1
    df["eligible_for_shelf"] = (df.in_v1_scope & ~df.manual_excluded & ~df.is_freebie & ~df.is_hidden & ~df.all_listings_hidden & ~df.is_combo & ~df.is_duplicate
                                & df.in_stock_effective & df.has_price & df.shelf_ok_confidence)

    cols = ["brand", "source", "product_key", "product_id", "variant_id", "title", "variant", "segment", "category", "category_from",
            "gender", "size_value", "size_unit", "typical_size", "price", "mrp", "discount_pct", "price_per_100", "in_stock", "stock_unknown", "in_stock_effective",
            "actives", "strengths", "concerns", "claims", "rating", "review_count", "description_chars",
            "is_freebie", "is_hidden", "all_listings_hidden", "is_combo", "is_duplicate", "manual_excluded", "in_v1_scope", "has_price", "shelf_ok_confidence",
            "eligible_for_shelf", "confidence", "url", "type_tags", "description"]
    OUT.mkdir(parents=True, exist_ok=True)
    df[cols].to_csv(OUT / "products.csv", index=False, encoding="utf-8-sig")

    # step-by-step funnel per brand (counted on variants)
    steps = [("all rows", pd.Series(True, index=df.index))]
    m = pd.Series(True, index=df.index)
    for name, cond in [("not freebie", ~df.is_freebie), ("not hidden", ~df.is_hidden), ("not combo", ~df.is_combo),
                       ("not duplicate", ~df.is_duplicate), ("in v1 categories", df.in_v1_scope), ("in stock (or unknown)", df.in_stock_effective),
                       ("has price", df.has_price), ("eligible for shelf", df.eligible_for_shelf)]:
        m = m & cond
        steps.append((name, m.copy()))
    rep = pd.DataFrame({name: s.groupby(df.brand).sum() for name, s in steps}).astype(int)
    rep.loc["TOTAL"] = rep.sum()
    rep.to_csv(OUT / "cleaning_report.csv", encoding="utf-8-sig")

    print(f"rows in: {n0}")
    print(rep.loc["TOTAL"].to_string())
    print("\ncategory counts (all rows):\n", df.category.value_counts().head(40).to_string())
    print("\nunclassified rows:", int((df.category == "unclassified").sum()))
    print("\neligible products (unique product_key) by category:\n",
          df[df.eligible_for_shelf].groupby("category").product_key.nunique().to_string())


if __name__ == "__main__":
    main()
