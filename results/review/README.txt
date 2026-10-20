ShelfRank - cleaned data (Phase 2). Nothing deleted: every row has a STATUS saying why it is in or out.
1_all_rows_with_status.csv            every product size/shade + status (ELIGIBLE or the reason it's excluded)
2_eligible_products_one_row_each.csv  shelf candidates, one row per product
3_PILGRIM_spot_check.csv              ALL Pilgrim rows with status -> check categories, sizes, prices, exclusions
4_random_20_spot_check.csv            20 random eligible products -> quick accuracy check
5_cleaning_funnel_by_brand.csv        how many rows survive each cleaning step, per brand
6_eligible_by_brand_and_category.csv  shelf candidates per brand per category
Column all_listings_hidden = every listing of this product carries a 'hidden' tag on the brand's store, but it is in stock and priced, so it is kept.
Originals: C:\Users\as09a\personal\shelfrank\data\clean\products.csv
