"""Export human-review spreadsheets of the cleaned data (with a plain-English status per row)."""

import os
import shutil
import sys

import pandas as pd

OUT_DIR = sys.argv[1] if len(sys.argv) > 1 else "C:/Users/as09a/Desktop/ShelfRank - cleaned data"
VIEW = ["status", "brand", "title", "variant", "segment", "category", "gender", "size_value", "size_unit", "price", "mrp",
        "discount_pct", "price_per_100", "in_stock", "all_listings_hidden", "actives", "strengths", "concerns", "claims",
        "rating", "review_count", "description_chars", "url"]


def why(r):
    if r.is_freebie:
        return "freebie / gift / Rs 0-1"
    if r.is_hidden:
        return "hidden copy (a visible listing exists)"
    if r.is_combo:
        return "combo / kit / multipack"
    if r.is_duplicate:
        return "duplicate listing"
    if not r.in_v1_scope:
        return f"category not in v1 ({r.category})"
    if not r.in_stock_effective:
        return "out of stock"
    if not r.has_price:
        return "no price on site"
    if not r.shelf_ok_confidence:
        return "hand-entered, low confidence"
    return "ELIGIBLE"


def main():
    df = pd.read_csv("data/clean/products.csv", low_memory=False)
    df["status"] = df.apply(why, axis=1)
    os.makedirs(OUT_DIR, exist_ok=True)
    df[VIEW].to_csv(f"{OUT_DIR}/1_all_rows_with_status.csv", index=False, encoding="utf-8-sig")
    el = df[df.eligible_for_shelf].drop_duplicates("product_key")
    el[VIEW].to_csv(f"{OUT_DIR}/2_eligible_products_one_row_each.csv", index=False, encoding="utf-8-sig")
    p = df[df.brand == "Pilgrim"].drop_duplicates(["product_key", "variant"])
    p[VIEW].sort_values(["status", "category"]).to_csv(f"{OUT_DIR}/3_PILGRIM_spot_check.csv", index=False, encoding="utf-8-sig")
    el.sample(20, random_state=7)[VIEW].to_csv(f"{OUT_DIR}/4_random_20_spot_check.csv", index=False, encoding="utf-8-sig")
    shutil.copy("data/clean/cleaning_report.csv", f"{OUT_DIR}/5_cleaning_funnel_by_brand.csv")
    pv = el.pivot_table(index="brand", columns="category", values="product_key", aggfunc="count", fill_value=0)
    pv["TOTAL"] = pv.sum(axis=1)
    pv.sort_values("TOTAL", ascending=False).to_csv(f"{OUT_DIR}/6_eligible_by_brand_and_category.csv", encoding="utf-8-sig")
    with open(f"{OUT_DIR}/README.txt", "w", encoding="utf-8") as f:
        f.write(
            "ShelfRank - cleaned data (Phase 2). Nothing deleted: every row has a STATUS saying why it is in or out.\n"
            "1_all_rows_with_status.csv            every product size/shade + status (ELIGIBLE or the reason it's excluded)\n"
            "2_eligible_products_one_row_each.csv  shelf candidates, one row per product\n"
            "3_PILGRIM_spot_check.csv              ALL Pilgrim rows with status -> check categories, sizes, prices, exclusions\n"
            "4_random_20_spot_check.csv            20 random eligible products -> quick accuracy check\n"
            "5_cleaning_funnel_by_brand.csv        how many rows survive each cleaning step, per brand\n"
            "6_eligible_by_brand_and_category.csv  shelf candidates per brand per category\n"
            "Column all_listings_hidden = every listing of this product carries a 'hidden' tag on the brand's store, but it is in stock "
            "and priced, so it is kept.\n"
            "Originals: C:\\Users\\as09a\\personal\\shelfrank\\data\\clean\\products.csv\n")
    print(f"exported to {OUT_DIR}: {len(df)} rows, {len(el)} eligible products, Pilgrim rows {len(p)}")


if __name__ == "__main__":
    main()
