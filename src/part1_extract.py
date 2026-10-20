"""Part 1 scoring, step 1: turn each free-text answer into a structured list of recommendations.

A cheap model reads each answer and returns JSON:
  {"recommendations": [{"rank", "brand", "product", "price_inr", "claimed_strength", "specific"}],
   "retailers": [...], "advice_only": bool}
"specific" = a named product (e.g. "Minimalist 10% Niacinamide Serum") vs a vague brand mention ("Pilgrim's options").

Output: logs/part1/extracted.jsonl (one line per answer; resumable; budget-capped).
"""

import argparse
import asyncio
import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI

ROOT = Path(__file__).resolve().parent.parent
PROMPT = """You extract product recommendations from a shopping assistant's answer. Return ONLY JSON, no prose.

Schema:
{{"recommendations": [{{"rank": 1, "brand": "brand name as written", "product": "product name as written or null",
   "price_inr": number or null, "claimed_strength": "e.g. 10% niacinamide, SPF 50 - or null", "specific": true/false}}],
 "retailers": ["shops/marketplaces mentioned, e.g. Nykaa, Amazon"],
 "advice_only": true/false}}

Rules:
- One entry per brand/product the answer RECOMMENDS or suggests buying, in the order they first appear (rank 1 = first).
- Include brands mentioned as examples ("brands like X and Y"). Do NOT include ingredients (e.g. "niacinamide") as brands.
- Retailers/marketplaces (Nykaa, Amazon, Flipkart, Purplle, Tira, 1mg, Myntra) go in "retailers", NOT recommendations,
  unless it is their own product line (e.g. "Nykaa Cosmetics lipstick" -> brand "Nykaa Cosmetics").
- "specific": true if a particular product is named; false if only the brand is mentioned (e.g. "Pilgrim's options").
- price_inr: only if the answer states a price for that product (a single number; if a range, the lower end).
- advice_only: true if the answer recommends no brand or product at all (only ingredients/tips).

Answer to extract from:
\"\"\"{answer}\"\"\""""


def parse_json(text):
    m = re.search(r"\{.*\}", text or "", re.S)
    return json.loads(m.group(0)) if m else None


async def extract(client, sem, rec, args, state, out):
    async with sem:
        if state["spent"] >= args.budget:
            state["skipped"] += 1
            return
        res = {k: rec[k] for k in ("mode", "qid", "model", "repeat")}
        for attempt in range(3):
            try:
                r = await client.chat.completions.create(
                    model=args.extractor, max_tokens=1200,
                    messages=[{"role": "user", "content": PROMPT.format(answer=rec["answer"])}],
                    extra_body={"usage": {"include": True}, "reasoning": {"enabled": False}})
                cost = (r.usage.model_dump() if r.usage else {}).get("cost") or 0
                state["spent"] += cost
                data = parse_json(r.choices[0].message.content)
                if data is None:
                    raise ValueError("no JSON in extractor output")
                res.update({"extracted": data, "extract_cost": cost, "error": None})
                break
            except Exception as e:
                res.update({"extracted": None, "error": f"{type(e).__name__}: {str(e)[:200]}"})
                await asyncio.sleep(3 * (attempt + 1))
        state["n"] += 1
        out.write(json.dumps(res, ensure_ascii=False) + "\n")
        out.flush()
        if state["n"] % 100 == 0 or res["error"]:
            print(f"[{state['n']}] {res['mode']} {res['qid']} {res['model']}: {'ok' if not res['error'] else res['error'][:80]} | total ${state['spent']:.4f}", flush=True)


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--out", default="logs/part1/extracted.jsonl")
    ap.add_argument("--extractor", default="anthropic/claude-haiku-5.5")
    ap.add_argument("--budget", type=float, required=True)
    ap.add_argument("--limit", type=int, help="only the first N answers (for a test)")
    ap.add_argument("--concurrency", type=int, default=8)
    args = ap.parse_args()
    load_dotenv(ROOT / ".env")
    client = AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=os.environ["OPENROUTER_API_KEY"])
    out_path = ROOT / args.out
    done, spent = set(), 0.0
    if out_path.exists():
        for line in out_path.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            spent += r.get("extract_cost") or 0
            if r.get("extracted") is not None:
                done.add((r["mode"], r["qid"], r["model"], r["repeat"]))
    recs = []
    for f in args.files:
        for line in Path(f).read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            if r.get("answer") and (r["mode"], r["qid"], r["model"], r["repeat"]) not in done:
                recs.append(r)
    if args.limit:
        recs = recs[: args.limit]
    state = {"spent": spent, "n": 0, "skipped": 0}
    print(f"{len(recs)} answers to extract ({len(done)} done), spent so far ${spent:.4f}, cap ${args.budget}")
    sem = asyncio.Semaphore(args.concurrency)
    with open(out_path, "a", encoding="utf-8") as out:
        await asyncio.gather(*(extract(client, sem, r, args, state, out) for r in recs))
    print(f"finished: {state['n']} extracted, total extraction spend ${state['spent']:.4f}"
          + (f", {state['skipped']} skipped (budget cap)" if state["skipped"] else ""))


if __name__ == "__main__":
    asyncio.run(main())
