"""Part 2: turn each shelf product into a standard card (same fields, same length for every brand).

A cheap model (Claude Haiku) rewrites the brand's OWN title and description into fixed fields under strict
rules: nothing added, % only if the brand states it, no superlatives that the brand did not use.
Size and price come from our catalogue, never from the model.

In:  data/part2/shelves.csv
Out: data/part2/cards.csv  (raw model output in logs/part2/cards_raw.jsonl)
"""

import argparse
import asyncio
import hashlib
import json
import os
import re
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from openai import AsyncOpenAI

ROOT = Path(__file__).resolve().parent.parent
MODEL = "anthropic/claude-haiku-5.5"

PROMPT = """You are standardising product listings for a comparison table. Use ONLY the brand's text below.

Brand: {brand}
Category: {category}
Title: {title}
Description: {description}

Return JSON only, with these keys:
- "name": the product name without the brand name, size, shade name or marketing phrases (max 60 characters)
- "key_ingredients": up to 4 key ingredients, each with its % ONLY if the brand's text states it (e.g. "10% niacinamide")
- "good_for": up to 3 short phrases (2-4 words each) for the concerns or skin/hair types the brand says it is for
- "claims": up to 2 short claims (max 12 words each) that the brand itself makes. Do not add numbers, results or praise that are not in the text
- "finish_or_texture": 1-3 words if stated (e.g. "gel", "matte", "lightweight"), else ""
- "size_if_stated": the pack size if stated in the title (e.g. "50 ml"), else ""
"""


def with_overrides(shelves):
    """Use hand-collected public descriptions (data/manual/card_descriptions.csv) where our catalogue text is thin."""
    path = ROOT / "data" / "manual" / "card_descriptions.csv"
    shelves["src_text"] = shelves.description.fillna("").astype(str)
    if path.exists():
        o = pd.read_csv(path).fillna("")
        for r in o.itertuples():
            hit = (shelves.brand == r.brand) & (shelves.title.str.strip() == str(r.catalogue_title).strip())
            txt = (f"{r.short_description} Key ingredients: {r.key_ingredients}. Brand claims: {r.claims}. "
                   f"For: {r.concerns}. Texture: {r.texture}. Size: {r.size}.")
            shelves.loc[hit, "src_text"] = txt
    shelves["src_hash"] = shelves.src_text.str.slice(0, 2500).map(lambda t: hashlib.md5(t.encode()).hexdigest()[:10])
    return shelves


def clean_json(text):
    m = re.search(r"\{.*\}", text or "", re.S)
    return json.loads(m.group(0)) if m else None


async def make_card(client, sem, row, out, state, budget):
    async with sem:
        if state["spent"] >= budget:
            return
        msg = PROMPT.format(brand=row.brand, category=row.category, title=row.title,
                            description=str(row.src_text)[:2500])
        for attempt in range(3):
            try:
                r = await client.chat.completions.create(
                    model=MODEL, messages=[{"role": "user", "content": msg}], max_tokens=400, temperature=0,
                    extra_body={"usage": {"include": True}, "reasoning": {"enabled": False, "exclude": True}})
                card = clean_json(r.choices[0].message.content)
                cost = (r.usage.model_dump() if r.usage else {}).get("cost") or 0
                state["spent"] += cost
                if card:
                    rec = {"product_key": row.product_key, "src_hash": row.src_hash, "brand": row.brand, "card": card, "cost_usd": cost}
                    out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    out.flush()
                    return
            except Exception as e:
                print("error", row.brand, type(e).__name__, str(e)[:120])
                await asyncio.sleep(3)


def size_text(row, card):
    if pd.notna(row.size_value) and str(row.size_unit) not in ("nan", ""):
        v = float(row.size_value)
        return f"{v:g} {row.size_unit}"
    return card.get("size_if_stated") or ""


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=float, default=0.10)
    args = ap.parse_args()
    load_dotenv(ROOT / ".env")
    client = AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=os.environ["OPENROUTER_API_KEY"])

    shelves = with_overrides(pd.read_csv(ROOT / "data" / "part2" / "shelves.csv"))
    raw_path = ROOT / "logs" / "part2" / "cards_raw.jsonl"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    spent = 0.0
    if raw_path.exists():
        for line in raw_path.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            done.add((r["product_key"], r.get("src_hash")))
            spent += r.get("cost_usd") or 0
    todo = shelves.drop_duplicates("product_key")
    todo = todo[[(k, h) not in done for k, h in zip(todo.product_key, todo.src_hash)]]
    state = {"spent": spent}
    print(f"{len(todo)} cards to make, spent so far ${spent:.4f}")
    sem = asyncio.Semaphore(6)
    with open(raw_path, "a", encoding="utf-8") as out:
        await asyncio.gather(*(make_card(client, sem, r, out, state, args.budget) for r in todo.itertuples()))

    cards = {}
    for line in raw_path.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        cards[(r["product_key"], r.get("src_hash"))] = r["card"]
    rows = []
    for r in shelves.itertuples():
        c = cards.get((r.product_key, r.src_hash))
        if not c:
            print("MISSING card", r.shelf, r.brand)
            continue
        rows.append({"shelf": r.shelf, "role": r.role, "brand": r.brand, "product_key": r.product_key,
                     "name": c.get("name", ""), "size": size_text(r, c), "price": int(r.price),
                     "key_ingredients": "; ".join(c.get("key_ingredients") or []),
                     "good_for": "; ".join(c.get("good_for") or []),
                     "claims": " | ".join(c.get("claims") or []),
                     "texture": c.get("finish_or_texture") or ""})
    pd.DataFrame(rows).to_csv(ROOT / "data" / "part2" / "cards.csv", index=False, encoding="utf-8")
    print(f"done: {len(rows)} cards, total spent ${state['spent']:.4f}")


if __name__ == "__main__":
    asyncio.run(main())
