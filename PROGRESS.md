# ShelfRank: progress log

*Read this first when resuming after a context reset. Last updated: 2026-10-21 (full Part 1 run started).*
The full narrative, decisions and research live in the Obsidian note `C:\Users\as09a\Obsidian\Obsidian Vault\Exploring Evals.md`.

## What this is
A private study of **how the AI models behind shopping assistants recommend Indian beauty products**, and **where Pilgrim stands** against its competitors.
- **Part 1, "Who gets recommended?"** No shelf. We ask shopper questions and record which brands and products each AI names, in two modes:
  - **memory:** no internet
  - **web:** OpenRouter web plugin, Exa search, 5 results
- **Part 2, "Why do products win?"** A controlled 8-product shelf. Vary the position, badge, rating, price and language one at a time.

## Ground rules (do not break)
- **Do NOT update Claude's memory from this project.** Only this file and the Obsidian note are the record.
- **Never read or print API keys.** The OpenRouter key lives in `.env` (gitignored); code reads it, Claude never opens it.
- **The repo is private** (github.com/ayush-06/shelfrank). **Results are not published** unless the user decides to.
- **Git push needs the GitHub CLI account `ayush-06` active.** Check with `gh auth status`. The user also has the work account `ayushsharma-pilgrim` in gh and in Git Credential Manager (for the Pilgrim repos).
- Public data only. Polite, slow requests; never get around a block; never place orders.
- **Shopify is throttling our IP** (429s since 2026-10-18; still 429 on 2026-10-19). Don't hammer it. Kay Beauty and the ratings pass wait.
- Budget: user's OpenRouter credit is **$5** (spent $0.43 before the full run). Every run uses `--budget` caps. **Top-ups take time to show up**, so plan spend ahead and ask for a top-up early (Part 2 will need one).

## Status
| Phase | Status |
|---|---|
| 1. Collect catalogues | ✅ 41 Shopify brands, 10,556 raw products (`data/raw/2026-10-17/shopify/`); 7 brands via product pages, 1,626 (`.../pages/`); 85 hand-entered rows (`data/manual/legacy_brands.csv`); L'Oréal Paris and Nivea MRPs (`data/manual/price_additions.csv`) |
| 1b. Pending data | ⏳ Kay Beauty (Shopify 429); ratings and descriptions for shelf products only (after the throttling lifts) |
| 2. Clean | ✅ `src/clean.py` → `data/clean/products.csv`: **2,120 shelf-eligible products, 56 brands, Pilgrim 60**. Review exports go to `C:\Users\as09a\Desktop\ShelfRank - cleaned data\` via `src/export_review.py` |
| Part 1 questions | ✅ Approved: `data/part1/questions.csv`, 60 questions (10 needs × 3 styles × English/Hinglish), plain language, no brands or ingredients |
| Part 1 pilot | ✅ 2026-10-20: 102 answers, $0.31. Pilgrim named in 3/102. Minimalist dominates. GPT-6 names 0–1 products. Web mode surfaces more D2C brands |
| Part 1 full run | 🔄 **Started 2026-10-21** (user approved). Run files `logs/part1/full_memory.jsonl` and `logs/part1/full_web.jsonl`. Caps: memory $2.30 total, web $1.50 total (spent so far before the run: pilot $0.31 + cost test $0.12) |
| Web-mode bias handling | ✅ Decided 2026-10-21: Exa with **10 pages** (same $0.0075 as 5); log every page; split "was the brand FOUND in the results" vs "was it PICKED when found"; small check with each provider's own search (`--engine native`, $0.017–0.032 per answer = 3–4× Exa) on 10 English need+budget questions × GPT-6 Luna and Gemini 3.6 Flash; state "Exa top-10, date" as a limitation |
| Part 1 scoring | ⏳ To build: extract products from answers → match to catalogue → visibility, rank, fact-check, stability |
| Part 2 | ⏳ Not started (shelf builder, trials, needs a credit top-up) |
| Dashboard and write-up | ⏳ Not started |

## Key decisions (A–J and later)
- Out-of-stock products off shelves. Typical size per category. Combos off shelves. Men's products only for men's requests. Keyword rules first.
- v1 categories: face serum, sunscreen, face wash, moisturiser, hair serum, shampoo, hair oil, lipstick.
- Hand-entered or hand-priced rows: only medium/high confidence go on shelves.
- Shelf cards are a standard format (name, size, price, actives, concerns, 1–2 claims). The baseline shows selling price only.
- Salon-professional products are excluded. Peeling solution is an exfoliator (not v1).
- Hidden: only exact markers (`hidden-product`, `upsell-product`, `hide__product`…). "no-index" is SEO, not hidden. A product hidden on **every** listing is excluded (shoppers can't find it) **unless it's in Pilgrim's public Bestsellers collection** (`data/raw/2026-10-17/pilgrim_bestsellers_collection.json`; 41/54 bestsellers are in the study).
- Brands whose store marks every product unavailable (Pond's, TRESemmé) → stock "unknown", not out of stock.
- Manual exclusions: `data/manual/exclusions.csv`.

## How to run things
```
# Part 1 (resumable; --budget is a hard cap per run file)
.venv/Scripts/python src/part1_run.py --run <name> --mode memory --qids pilot|<ids>|(empty=all) --repeats N --budget X
.venv/Scripts/python src/part1_run.py --run <name> --mode web --qids <ids> --models <ids> --budget X
.venv/Scripts/python src/part1_peek.py logs/part1/<file>.jsonl ...      # quick brand-mention summary → logs/part1/peek.csv

# data
.venv/Scripts/python src/clean.py            # rebuild data/clean/products.csv
.venv/Scripts/python src/export_review.py    # refresh Desktop review files
```
On Windows, set `PYTHONIOENCODING=utf-8` when printing.

## Models (OpenRouter, prices checked 2026-10-19)
GPT-6 Luna, GPT-6 Sol, Gemini 3.1 Flash-Lite, Gemini 3.6 Flash, Claude Haiku 5.5, Claude Sonnet 5.5, Nova 2 Lite, Llama 4 Maverick, DeepSeek V4 Flash (see `MODELS` in `src/part1_run.py`). Web mode uses Exa at $0.007 per search.

## Next steps
1. ~~User go → full Part 1 run.~~ **Running** (see Status). If interrupted, re-run the same commands; the runner resumes.
   - memory: all 60 questions × 3 repeats on 6 cheap models, plus × 1 on Sol, Sonnet and Gemini 3.6 Flash
   - web: 20 "need + budget" questions × 4 models
2. Build Part 1 scoring:
   - LLM extraction to JSON (brand, product, claimed price, claimed %)
   - fuzzy-match to `data/clean/products.csv`
   - metrics: share, rank, Pilgrim visibility, hallucination/price/% errors, fit-to-request, stability, EN vs Hinglish, memory vs web
3. Report the Part 1 findings to the user (tables), and add them to Obsidian.
4. Part 2 design: shelf builder (Pilgrim + top-recommended from Part 1 + peers + legacy + 1–2 "wrong" products), standard cards, trials, pilot. Needs a credit top-up.
5. Later: Kay Beauty and the ratings pass once Shopify stops throttling (test one request first).
6. Undo list at the end (see the Obsidian note): uninstall gh, log out both gh accounts if wanted, repo-local git config, delete the repo if wanted.
