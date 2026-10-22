"""Part 2: show each model a shelf (shopper question + 8 product cards) and record which product it picks.

Logs every call to logs/part2/<run>.jsonl with the pick, reason, the exact order shown, usage and cost.
Hard budget cap per run file; resumable on (trial_id, model). The API key is read from .env, never printed.

  .venv/Scripts/python src/part2_run.py --run pilot --trials pilot --budget 0.30
  .venv/Scripts/python src/part2_run.py --run main --trials full --models <ids> --budget 4.5
  .venv/Scripts/python src/part2_run.py --show N01        # print one rendered prompt, no API call
"""

import argparse
import asyncio
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from openai import AsyncOpenAI

from part1_run import IST, MODELS

ROOT = Path(__file__).resolve().parent.parent
CHEAP = ["openai/gpt-6-luna", "google/gemini-3.1-flash-lite", "anthropic/claude-haiku-5.5",
         "amazon/nova-2-lite-v1", "meta-llama/llama-4-maverick", "deepseek/deepseek-v4-flash"]
PREMIUM = ["openai/gpt-6-sol", "anthropic/claude-sonnet-5.5", "google/gemini-3.6-flash"]

SYSTEM = ("You are the AI shopping assistant of an online beauty store in India. A shopper asks for a recommendation. "
          "Only the products listed are available. Recommend exactly ONE of them.\n"
          'Reply with JSON only: {"pick": <product number 1-8>, "reason": "<one sentence, max 25 words>"}')


def load_cards():
    c = pd.read_csv(ROOT / "data" / "part2" / "cards.csv").fillna("")
    return {r.product_key: r for r in c.drop_duplicates("product_key").itertuples()}


def render(trial, cards):
    m = trial["mods"]
    swap = m.get("brand_swap")
    lines = []
    for i, k in enumerate(trial["order"], 1):
        c = cards[k]
        if k in (m.get("card_override") or {}):  # Pilgrim card test: hypothetical copy changes
            c = c._replace(**m["card_override"][k])
        brand = c.brand
        if swap and k in swap:
            brand = cards[swap[1] if k == swap[0] else swap[0]].brand
        price = c.price
        if k in (m.get("price_change") or {}):
            price = round(price * (1 + m["price_change"][k]))
        head = f"{i}. {c.name}" if m.get("hide_brands") else f"{i}. {brand} - {c.name}"
        sub = " | ".join(x for x in [c.size, f"₹{price}"] if x)
        block = [head, f"   {sub}"]
        if c.key_ingredients:
            block.append(f"   Key ingredients: {c.key_ingredients.replace(';', ',')}")
        if c.good_for:
            block.append(f"   Good for: {c.good_for.replace(';', ',')}")
        if c.claims:
            block.append(f"   Brand says: {c.claims.replace(' | ', '; ')}")
        if c.texture:
            block.append(f"   Texture/finish: {c.texture}")
        if k in (m.get("ratings") or {}):
            stars, n = m["ratings"][k]
            block.append(f"   Rating: {stars:.1f}★ ({n:,} reviews)")
        if k in (m.get("badge") or {}):
            block.append(f"   [{m['badge'][k]}]")
        lines.append("\n".join(block))
    return f"Shopper: {trial['question']}\n\nAvailable products:\n\n" + "\n\n".join(lines)


def parse_pick(text, n):
    if not text:
        return None, None
    m = re.search(r"\{.*\}", text, re.S)
    if m:
        try:
            d = json.loads(m.group(0))
            p = int(str(d.get("pick")).strip().split()[0].strip("#."))
            return (p if 1 <= p <= n else None), d.get("reason")
        except (ValueError, TypeError, json.JSONDecodeError):
            pass
    m = re.search(r'"?pick"?\s*[:=]\s*"?(\d+)', text)
    if m and 1 <= int(m.group(1)) <= n:
        return int(m.group(1)), None
    return None, None


class Pacer:
    """New OpenRouter accounts get 20 requests/minute per model: keep each model under that."""
    def __init__(self, per_minute):
        self.gap, self.next, self.lock = 60.0 / per_minute, 0.0, asyncio.Lock()

    async def wait(self):
        async with self.lock:
            now = time.monotonic()
            delay = max(0.0, self.next - now)
            self.next = max(now, self.next) + self.gap
        await asyncio.sleep(delay)


def done_keys(path, retry_unparsed=False):
    keys, spent = set(), 0.0
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            spent += r.get("cost_usd") or 0
            if r.get("raw") is not None and not (retry_unparsed and r.get("pick_slot") is None):
                keys.add((r["trial_id"], r["model"]))
    return keys, spent


async def ask(client, sem, pacer, trial, model, cards, args, state, out):
    cfg = MODELS.get(model, {})
    body = {"usage": {"include": True}}
    if cfg.get("reasoning"):
        body["reasoning"] = {**cfg["reasoning"], "exclude": True}
    async with sem:
        if state["spent"] >= args.budget:
            state["skipped"] += 1
            return
        prompt = render(trial, cards)
        rec = {k: trial[k] for k in ("trial_id", "shelf", "condition", "level", "target", "target_brand",
                                     "target_role", "language", "repeat", "order")}
        rec.update({"model": model, "asked_at": datetime.now(IST).isoformat(timespec="seconds")})
        t0 = time.time()
        for attempt in range(4):
            await pacer.wait()
            try:
                resp = await client.chat.completions.create(
                    model=model, max_tokens=args.max_tokens, extra_body=body,
                    messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}])
                text = resp.choices[0].message.content
                usage = resp.usage.model_dump() if resp.usage else {}
                pick, reason = parse_pick(text, len(trial["order"]))
                rec.update({"raw": text, "pick_slot": pick, "reason": reason,
                            "pick_key": trial["order"][pick - 1] if pick else None,
                            "finish_reason": resp.choices[0].finish_reason, "usage": usage,
                            "cost_usd": usage.get("cost"), "latency_s": round(time.time() - t0, 1), "error": None})
                break
            except Exception as e:
                rec.update({"raw": None, "error": f"{type(e).__name__}: {str(e)[:300]}", "cost_usd": 0})
                await asyncio.sleep(60 if "429" in str(e) else 5 * (attempt + 1))
        state["spent"] += rec.get("cost_usd") or 0
        state["n"] += 1
        state["unparsed"] += int(rec.get("raw") is not None and rec.get("pick_slot") is None)
        out.write(json.dumps(rec, ensure_ascii=False) + "\n")
        out.flush()
        if state["n"] % 50 == 0 or rec.get("error"):
            print(f"[{state['n']}] {model} {trial['shelf']} {trial['condition']}: "
                  f"{'ERROR ' + rec['error'][:80] if rec.get('error') else 'ok'} | total ${state['spent']:.4f}", flush=True)


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run")
    ap.add_argument("--trials", default="full", help="trials file set: full | pilot")
    ap.add_argument("--models", nargs="*", default=CHEAP)
    ap.add_argument("--conditions", nargs="*", help="only these conditions")
    ap.add_argument("--shelves", nargs="*", help="only these shelves")
    ap.add_argument("--targets", nargs="*", help="only one-product changes whose target has these roles")
    ap.add_argument("--levels", nargs="*", help="only these levels (as strings) for one-product changes")
    ap.add_argument("--max-repeat", type=int, default=99)
    ap.add_argument("--budget", type=float)
    ap.add_argument("--max-tokens", type=int, default=300)
    ap.add_argument("--concurrency", type=int, default=60)
    ap.add_argument("--rpm", type=float, default=18, help="max requests per minute per model")
    ap.add_argument("--show", help="print one rendered prompt for this shelf and exit")
    ap.add_argument("--dry", action="store_true", help="count calls only")
    ap.add_argument("--retry-unparsed", action="store_true", help="ask again where the answer could not be parsed (e.g. cut off)")
    args = ap.parse_args()

    cards = load_cards()
    trials = [json.loads(x) for x in (ROOT / "data" / "part2" / f"trials_{args.trials}.jsonl").read_text(encoding="utf-8").splitlines()]
    if args.show:
        t = next(t for t in trials if t["shelf"] == args.show)
        print(SYSTEM + "\n\n" + render(t, cards))
        return
    sel = [t for t in trials
           if (not args.conditions or t["condition"] in args.conditions)
           and (not args.shelves or t["shelf"] in args.shelves)
           and (not args.targets or t["target"] is None or t["target_role"] in args.targets)
           and (not args.levels or t["level"] is None or str(t["level"]) in args.levels)
           and t["repeat"] <= args.max_repeat]
    out_path = ROOT / "logs" / "part2" / f"{args.run}.jsonl"
    done, spent = done_keys(out_path, args.retry_unparsed) if args.run else (set(), 0.0)
    jobs = [(t, m) for t in sel for m in args.models if (t["trial_id"], m) not in done]
    print(f"{len(jobs)} calls to make ({len(done)} already done), spent so far ${spent:.4f}, cap ${args.budget}")
    if args.dry:
        return
    assert args.run and args.budget is not None, "--run and --budget are required"
    load_dotenv(ROOT / ".env")
    client = AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=os.environ["OPENROUTER_API_KEY"])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    state = {"spent": spent, "n": 0, "skipped": 0, "unparsed": 0}
    sem = asyncio.Semaphore(args.concurrency)
    pacers = {m: Pacer(args.rpm) for m in args.models}
    with open(out_path, "a", encoding="utf-8") as out:
        await asyncio.gather(*(ask(client, sem, pacers[m], t, m, cards, args, state, out) for t, m in jobs))
    print(f"finished: {state['n']} calls, {state['unparsed']} unparsed, run total ${state['spent']:.4f}"
          + (f", {state['skipped']} skipped (budget cap)" if state["skipped"] else ""))


if __name__ == "__main__":
    asyncio.run(main())
