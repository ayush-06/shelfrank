# ShelfRank

*PageRank for the AI shopping era: how AI shopping assistants rank Indian beauty brands.*

A private research project. It tests how the AI models behind shopping assistants (GPT, Gemini, Claude, Nova, Llama, DeepSeek, Sarvam) choose between real Indian beauty products, and what sways those choices.

## What it measures
- **Position bias:** does the first product on the "shelf" win more than its fair share?
- **Badge effect:** how much do labels like "Bestseller", "Dermatologist recommended" or "Sponsored" shift the pick, and what is that worth in ₹ of discount?
- **Price framing:** does a crossed-out MRP sway the model?
- **Accuracy:** does the pick meet the shopper's budget, ingredient and skin-type needs?
- **Hinglish gap:** do Hinglish requests get worse picks than English ones?
- **Consistency:** do you get the same pick when you ask the same question again?
- **Brand pull:** does the brand name alone change the pick?

## Method (short)
1. Take dated snapshots of brands' **public** product catalogues.
2. Build 8-product shelves for realistic shopper requests in English and Hinglish.
3. Rotate every product through every slot, and add controlled variations (badges, MRP, description text).
4. Run every shelf on every model with [Inspect AI](https://inspect.aisi.org.uk) via OpenRouter.
5. Grade with code (no AI judge), and report error bars.

## Layout
```
src/            code
data/raw/       dated catalogue snapshots (local only, not committed)
data/manual/    hand-entered products for brands without an online store
data/clean/     standardised product table
data/shelves/   generated shelves and test cases
logs/           model answers / Inspect logs (local only, not committed)
results/        charts, dashboard, findings
```

## Ground rules
- Public catalogue data only. One slow, polite pass per site, and no block is ever circumvented.
- Catalogues are never republished. No orders are ever placed.
- API keys live in `.env` and are never committed.
