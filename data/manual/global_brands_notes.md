# Global brands: collection notes

Collected 2026-10-22, 08:41 to 09:03 IST (about 22 minutes). There were 69 page requests in total, sent one at a time with 3.5 to 6 seconds between them. No Shopify `*.myshopify.com` or `/products.json` endpoints were requested. I did not log in, add anything to a cart or place an order.

Output: `global_brands.csv` has 32 rows (31 medium confidence, 1 low, 0 high).

## Sites used per brand

| Brand | Product text from | Price from | Rows |
|---|---|---|---|
| Neutrogena | neutrogena.in product pages | amazon.in (Neutrogena brand store); Apollo Pharmacy for the Ultra Sheer 80 g | 5 |
| Cetaphil | cetaphil.in product pages | amazon.in (Cetaphil brand store) | 4 |
| CeraVe | amazon.in CeraVe brand-store listings (no Indian brand site found) | amazon.in | 4 |
| The Ordinary | theordinary.com/en-in product pages | amazon.in | 5 |
| La Roche-Posay | laroche-posay.co.in product pages | laroche-posay.co.in (retailer price list embedded in the page) | 8 |
| Sebamed | sebamed.in product pages | amazon.in (SebaMed brand store) | 6 |

## Why there is no "high" confidence
None of the official Indian brand sites shows a price labelled MRP:
- **neutrogena.in**: no prices, only a "Where to Buy" widget.
- **cetaphil.in**: no prices, only "Buy Now" / "Find in Store".
- **sebamed.in**: the price field is an empty "Rs. 0.00" placeholder.
- **theordinary.com/en-in**: prices are in USD only (international shipping to India), with no INR MRP.
- **laroche-posay.co.in**: this is the only site with INR prices. They appear as "RS.xxx" next to each retailer (Amazon, Apollo, Nykaa) and are not labelled MRP, so they count as medium. In two cases the Nykaa entry for a 15 ml pack repeats the larger pack's price. I used the Amazon/Apollo value and recorded the conflict in `notes`.

Amazon prices come from the brand-store listings. Where a M.R.P. strikethrough was shown, I used it as `mrp_inr` and put the selling price in `notes`. Where no strikethrough was shown, the displayed price is taken as the MRP and this is noted.

## Blocks and problems
- **nykaa.com returned 403 (Access Denied)** on the first request. I stopped using Nykaa and made no retries.
- **cerave.in and cerave.co.in do not resolve (DNS)**, and I found no other official CeraVe India site. CeraVe claims and descriptions therefore come from the CeraVe brand-store listings on Amazon.in (importer L'Oréal India). These should be checked against a brand page if one becomes available.
- **laroche-posay.in does not resolve.** The Indian site is laroche-posay.co.in.
- One Amazon search request timed out with no HTTP response. It was not a 403, 429 or captcha. I raised the delay to 6 seconds and later requests loaded normally.
- **Neutrogena Ultra Sheer MRP conflict**: for the 80 g pack, Apollo Pharmacy (sold by Apollo) shows MRP ₹780, while a third-party Amazon listing shows ₹1,000. I used ₹780. The 30 g pack's ₹500 comes only from a third-party Amazon seller, so it is marked **low**.
- The La Roche-Posay Mela B3 serum page's `<title>` says "Anti-Wrinkle Replumping Serum", but all of its claims are about dark spots. This looks like a labelling error on the site.

## Judgement calls on fit
- **La Roche-Posay Cicaplast Baume B5+** is a multi-purpose repair balm, not a daily facial moisturiser. It is included as the brand's sensitive/dry-skin option and flagged as a borderline fit.
- **Neutrogena Hydro Boost Water Gel** and **The Ordinary NMF + HA** are positioned for all skin types or for dryness, not specifically for sensitive skin.
- **Cetaphil Sun SPF 50+** is positioned for sensitive skin, not specifically for oily skin.
- The Neutrogena Oil-Free Acne Wash page warns "Not suitable for sensitive skin".

## Not collected / not found
- **Nizoral**: skipped on purpose. It is a medicated ketoconazole shampoo, and medicines are excluded from the shelves.
- **Neutrogena**: Bright Boost (dull skin / dark spots serum) is not sold in India, because neutrogena.in/bright-boost redirects to the homepage. As a result there is no Neutrogena serum that fits these needs. The Hydro Boost serum and Visible Repair serum are hydration and anti-ageing products and were not collected.
- **Cetaphil**: no face serum for oily or dull skin on cetaphil.in. The Bright Healthy Radiance range has no serum. Moisturising Cream 85 g and 453 g prices were not collected (no adult 85 g listing found on Amazon.in).
- **CeraVe**: Moisturising Cream 50 g/454 g, Foaming Cleanser 473 ml and SA Smoothing Cleanser were not collected.
- **The Ordinary**: Natural Moisturizing Factors + HA 100 ml is currently unavailable on Amazon.in. The 30 ml price was read from Amazon search results, not from its product page.
- **Sebamed**: the brand has no serum or sunscreen that fits the needs well. The Multi Protect Sunscreen SPF 30 exists on sebamed.in but was not collected.
