# ShelfRank Part 2: "Why do products win?" Results (2026-10-22)

## The short version
1. **Once Pilgrim is on the shelf, it does well.** Out of 8 products, the AIs pick Pilgrim **22%** of the time; a fair share is 12.5%. In Part 1, Pilgrim was *named* in only 2% of answers. So **Pilgrim's problem is being found, not being chosen.**
2. **The words on the card matter most.** When Pilgrim's card repeats the shopper's own words (e.g. "Good for: Oily skin, No white cast"), its pick rate **doubles, from 22% to 46%**:
   - sunscreen: 6% → 75%
   - lipstick: 7% → 85%
   - moisturiser: 9% → 46%

   "Clinically tested" or "Dermatologically tested" claims add nothing.
3. **Ratings are the next biggest lever.** +0.6★ adds **+26 points**. But a perfect 5.0★ works *less* well than 4.8★, so "too good to be true" is real. 5,000 reviews beat 50.
4. **The budget is a hard rule.** Over budget means the product is almost never picked. Within budget, **cutting the price doesn't help at all.**
5. **Global brands win only when the shopper gives no budget.** Without a budget, the over-budget global product gets picked: Sebamed's dandruff shampoo goes from 0% to **46%**. Pilgrim's share falls from 22% to 13.5%.
6. **Slot 1 gets picked 6× more often than slot 8** (25% vs 4%), with identical products.
7. **Brand names barely matter.** Hiding every brand name *raises* Pilgrim slightly (+4 points). The AIs' favourite brands lose about 5 points without their names.

## Setup
- **10 shelves**, one per Part 1 need. Each has 8 products from 8 brands, chosen by a written rule:
  - 1 Pilgrim
  - 3 brands the AIs named most in Part 1
  - 2 D2C peers
  - 1 legacy brand
  - 1 deliberately wrong product: over budget (often a famous global brand) or for a different concern

  See `shelves_review.md`.
- **Standard cards:** name, size, price, key ingredients, "good for", up to 2 brand claims, texture. Cards are written from each brand's own text.
- **The AI sees** the shopper's question plus the 8 cards, picks ONE, and gives a one-line reason, as JSON.
- **One thing changes per trial.** Every one-product change is applied to each of the 8 products in turn, and product order is rotated so each product sits in every slot.

| Run | Models | Answers | Cost |
|---|---|---|---|
| Pilot | all 9 | 768 | $0.37 |
| Main grid | 6 cheap: GPT-6 Luna, Gemini 3.1 Flash-Lite, Claude Haiku 5.5, Nova 2 Lite, Llama 4 Maverick, DeepSeek V4 Flash | 11,040 | $2.18 |
| Premium check | GPT-6 Sol, Claude Sonnet 5.5, Gemini 3.6 Flash (subset) | 1,200 | $3.03 |
| Pilgrim card test | 6 cheap | 1,920 | $0.36 |
| **Total** | | **14,928** | **$5.94** |

Parse failures: 0 in the main grid and card test. The premium run had 5 answers cut off, which were re-asked successfully.

## 1. Where Pilgrim stands on each shelf
"Base" = budget question, real names, no ratings or badges, averaged over all 8 slot positions. Fair share = 12.5%.

| Shelf (budget) | Pilgrim's product | Pilgrim picked | Winner |
|---|---|---|---|
| Hair growth serum (₹800) | 3% Redensyl + 4% Anagain + 5% Capilia, ₹729 | **68%** | **Pilgrim** |
| Hair-fall shampoo (₹500) | Redensyl & Anagain shampoo, ₹299 | **40%** | **Pilgrim** |
| Acne-marks serum (₹600) | 10% Niacinamide + Kojic, ₹403 | 32% | Dot & Key 39% |
| Face wash (₹350) | Korean Aloe Anti-Acne, ₹225 | 24% | Dot & Key 46% |
| Dandruff shampoo (₹400) | Tea Tree Anti-Dandruff, ₹299 | 17% | Mamaearth 33% |
| Glow serum (₹700) | 10% Vitamin C Roll-On, ₹569 | 11% | Plum 58% |
| Moisturiser (₹500) | 5 Ceramides Barrier Repair, ₹297 | 9% | Dot & Key 50% |
| Lipstick (₹600) | Matte Me Up! bullet, ₹298 | 7% | Lakmé 42% |
| Sunscreen (₹500) | Aqua Sunscreen Gel, ₹335 | 6% | Re'equil 41% |
| Hair oil (₹400) | Spanish Rosemary oil, ₹290 | 4% | Bare Anatomy 33% |
| **All shelves** | | **22%** (premium models 20%) | |

**Why winners win (from the AIs' reasons):** the winning card says the shopper's need in the shopper's words:
- Dot & Key: "Face Serum **for Oily Skin**"; "**dry, sensitive skin**"
- Re'equil: "**Oil-Free** Aquagel"

Pilgrim wins hair growth because its card names specific actives the AIs trust (Redensyl, Anagain). Pilgrim's sunscreen card, built from Pilgrim's own product text, says it's for **"dryness"**, so it loses the oily-skin shopper.

## 2. The Pilgrim card test: same product, different words
Only Pilgrim's card changes. The 4 versions are **hypothetical copy**, not Pilgrim's real claims. Each version: 10 shelves × 8 slots × 6 models = 480 answers.

| Pilgrim's card | Pilgrim picked | ± (95%) |
|---|---|---|
| As it is today | 21.9% | 2.6 |
| **"Good for" leads with the shopper's own words** | **46.0%** | 4.5 |
| Second claim → "Clinically tested: visible results in 4 weeks" | 20.8% | 3.6 |
| Second claim → "Dermatologically tested" | 17.5% | 3.4 |
| Plain: claims and texture removed | 12.7% | 3.0 |

- **The shopper's-words effect holds for every model**, from +15 points (Llama) to +29 (Claude Haiku).
- **Biggest jumps:**
  - sunscreen 6% → 75% ("Oily skin, No white cast")
  - lipstick 7% → 85% ("Natural everyday shades")
  - moisturiser 9% → 46% ("Dry skin, Sensitive skin")
  - dandruff 17% → 42%
- **Exception: hair growth**, which drops 68% → 56%. The card was already a strong match, and the new "good for" line replaced specific wording with generic words.
- **Claims matter, but only claims that say something specific.** Removing them halves Pilgrim's share. Generic trust claims ("clinically/dermatologically tested") don't help.

Per shelf: `main/pilgrim_card_test_by_shelf.csv`.

## 3. What moves a product (any brand), averaged over all 8 products and 10 shelves
Lift = change in how often that product is picked, in percentage points. 480 answers per row.

| Change on one product | Lift | ± (95%) |
|---|---|---|
| Rating 4.4★ (+0.2; others 4.2★) | +16 | 5 |
| Rating 4.6★ (+0.4) | +23 | 5 |
| **Rating 4.8★ (+0.6)** | **+26** | 5 |
| Rating 5.0★ (+0.8) | +17 (**dips**) | 5 |
| Rating 4.0★ / 3.8★ / 3.4★ | −4 / −8 / −11 (almost never picked) | 4 |
| 5,000 reviews (others 1,200) | +9 | 5 |
| 50 reviews | −8 | 4 |
| "Bestseller" badge | +9 | 4 |
| "Dermatologist recommended" | +4 | 4 |
| "Sponsored" | −3 | 3 |
| Price −10% / −20% | −1 / 0 (**no effect**) | 4 |
| Price +10% / +20% | −3 / −9 (only when it breaks the budget) | 3 |

- **Pilgrim with a rating boost:** 45% at 4.4★, 57% at 4.8★, 42% at 5.0★.
- **The premium models agree:** +0.4★ gives +20 to +30 points.
- **Price, in detail:** a price rise that stays within budget changes nothing (12.1% vs the 12.5% fair rate). One that crosses the budget drops the product to about 0%. So we **can't express a badge as "worth ₹X"**: within budget, price doesn't move the AI at all.

## 4. Budget, and the famous global brands
On 6 shelves, the deliberately over-budget product is a global brand the AIs love in Part 1:
- The Ordinary Alpha Arbutin ₹948
- La Roche-Posay Anthelios ₹599
- Neutrogena Acne Wash ₹681
- The Ordinary NMF ₹700
- Sebamed Anti-Hairloss ₹566
- Sebamed Anti-Dandruff ₹519

| Question | Over-budget product picked | Pilgrim picked |
|---|---|---|
| With budget ("under ₹500") | **0.1%** | 21.9% |
| Same question, **no budget** | **9.6%** | 13.5% |
| Hinglish, with budget | 0% | 23.1% |

- **Without a budget,** the global brand wins on dandruff (**Sebamed 46%**), and takes a share on face wash (Neutrogena 15%) and glow serum (The Ordinary 15%).
- **Pilgrim loses most on hair-fall shampoo,** where The Derma Co rises to 67%.
- **So the budget in the question protects D2C brands like Pilgrim.** Shoppers who don't state a budget get steered towards premium global products.
- **Hinglish:** no gap. Pilgrim gets 23% vs 22% in English, and no model broke the budget.

Global brand prices are medium confidence: their Indian sites show no labelled MRP, so the prices come from Amazon.in. See `data/manual/global_brands_notes.md`.

## 5. Position and brand names
**Slot bias** (identical products, rotated):

| Slot | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|
| Picked | 24.7% | 20.4% | 12.9% | 11.7% | 9.1% | 9.2% | 7.7% | 4.2% |

- **Most top-heavy:** Llama 4 picks slot 1 35% of the time and slots 6–8 almost never; GPT-6 Luna and Nova are next.
- **Least position-biased:** Claude Haiku, which is close to flat.

**Brand names:**

| | Real names | Names hidden | Names swapped (Pilgrim ↔ top favourite) |
|---|---|---|---|
| Pilgrim's product picked | 21.9% | 25.8% | 25.0% |
| AI-favourite brands' products (3 of 8) | 37.6% | 32.1% | 34.2% |

The favourites' names are worth about 5 points to them. Pilgrim's name is worth nothing, slightly negative. **The AIs judge the card, not the logo.** That's good news for a brand that's under-known.

## 6. Model behaviour
| Model | Pilgrim picked (base) | Same answer when asked twice |
|---|---|---|
| Gemini 3.1 Flash-Lite | 28% | 94% |
| GPT-6 Luna | 28% | 90% |
| Claude Haiku 5.5 | 22% | 81% |
| DeepSeek V4 Flash | 22% | **53%** |
| Llama 4 Maverick | 19% | 98% |
| Nova 2 Lite | **11%** | 83% |
| GPT-6 Sol (premium) | 28% | – |
| Claude Sonnet 5.5 (premium) | 19% | – |
| Gemini 3.6 Flash (premium) | 15% | – |

- **Almost no model breaks a stated budget** (0.1% of picks).
- **DeepSeek is the least consistent:** asked the identical question twice, it gives a different answer half the time.

## What this means for Pilgrim
1. **Discovery is the bottleneck, not the product.** When Pilgrim is on the shelf, it wins more than its fair share. Part 1 showed it's rarely *named*. Getting into the AI's candidate list (search results, retailer listings, reviews) is the bigger job.
2. **Write product text in the shopper's words.** Spell out the problem and skin or hair type it solves ("for oily skin", "no white cast", "for dry, sensitive skin"). This was worth **+24 points** in this test, the single biggest effect. The sunscreen's own text ("dryness") actively works against it.
3. **Ratings and review counts matter. A perfect 5.0★ doesn't help.**
4. **Price cuts within budget don't win AI recommendations.** Staying under common budget lines (₹300 / ₹500 / ₹800) does.
5. **"Bestseller" helps a little. "Sponsored" hurts.**

## Caveats
- These are controlled shelves: we decide which 8 products the AI sees. Real assistants also search, personalise and add their own instructions.
- Cards are standardised from each brand's text. Thin brand text means thin cards. One card (WOW hair growth roll-on) stayed thin.
- The card-test wording is hypothetical and repeats the shopper's question closely. In real use, shoppers phrase needs in many ways.
- 95% intervals use a normal approximation. Each answer counts as independent, although answers from the same model on the same shelf are correlated, so the true uncertainty is a bit wider.
- Premium models ran a subset only: base, no budget, brand hidden, rating +0.4★. They had no repeats, so there is no consistency score for them.

## Files
- `main/`: 6 cheap models. CSVs: `pick_share_by_role`, `pick_share_by_shelf_brand`, `pilgrim_by_shelf`, `position_bias`, `lift`, `brand_effect`, `wrong_picks_and_language`, `consistency`, `pilgrim_card_test`, `pilgrim_card_test_by_shelf`.
- `premium/`: the same tables for Sol, Sonnet and Gemini 3.6.
- `pilot/`: pilot scores.
- `shelves_review.md`: the 10 shelves.
- **Raw answers:**
  - `logs/part2/main.jsonl`, `premium.jsonl`, `card.jsonl`, `pilot.jsonl`: one line per API call
  - `results/readable/part2/<run>/<shelf>.md`: the exact prompt and every model's pick and reason, trial by trial
