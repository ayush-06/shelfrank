"""Part 1: ask shopper questions to many models via OpenRouter and log every answer.

Modes:
  memory  - the model answers from its own knowledge (no internet)
  web     - OpenRouter web plugin (Exa engine, same for every model) searches first

Every call is appended to logs/part1/<run>.jsonl with the answer, token usage and the
exact cost OpenRouter reports. A hard budget cap stops new calls once reached.
Resumable: (mode, qid, model, repeat) already in the file are skipped.

The API key is read from .env by the program; it is never printed.
"""

import argparse
import asyncio
import csv
import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI

ROOT = Path(__file__).resolve().parent.parent
IST = timezone(timedelta(hours=5, minutes=30))

# reasoning: "off" where the model allows it, else the lowest effort it accepts
MODELS = {
    "openai/gpt-6-luna": {"reasoning": {"effort": "none"}},          # ChatGPT free/Go default
    "openai/gpt-6-sol": {"reasoning": {"effort": "low"}},            # ChatGPT paid / Copilot
    "google/gemini-3.1-flash-lite": {"reasoning": {"effort": "none"}},
    "google/gemini-3.6-flash": {"reasoning": {"effort": "low"}},     # Gemini app / AI Mode
    "anthropic/claude-haiku-5.5": {"reasoning": {"enabled": False}},
    "anthropic/claude-sonnet-5.5": {"reasoning": {"effort": "low"}}, # Alexa for Shopping, Shopify Sidekick
    "amazon/nova-2-lite-v1": {"reasoning": {"enabled": False}},      # Amazon's own model
    "meta-llama/llama-4-maverick": {},                               # Meta AI
    "deepseek/deepseek-v4-flash": {"reasoning": {"enabled": False}},
}
PILOT_QIDS = ["N01-a-en", "N02-b-hi", "N03-c-en", "N04-a-hi", "N05-b-en", "N06-c-hi", "N07-a-en", "N08-b-hi", "N09-c-en", "N10-a-hi"]


def load_questions(qids):
    with open(ROOT / "data" / "part1" / "questions.csv", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return [r for r in rows if not qids or r["qid"] in qids]


def done_keys(path):
    keys, spent = set(), 0.0
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            spent += r.get("cost_usd") or 0
            if r.get("answer"):
                keys.add((r["mode"], r["qid"], r["model"], r["repeat"]))
    return keys, spent


async def ask(client, sem, q, model, mode, repeat, args, state, out):
    cfg = MODELS.get(model, {})
    body = {"usage": {"include": True}}
    if cfg.get("reasoning"):
        body["reasoning"] = {**cfg["reasoning"], "exclude": True}
    if mode.startswith("web"):
        body["plugins"] = [{"id": "web", "engine": args.engine, "max_results": args.web_results}]
        if args.engine == "native":  # provider's own search (e.g. OpenAI / Google); smallest context to limit cost
            body["web_search_options"] = {"search_context_size": "low"}
    async with sem:
        if state["spent"] >= args.budget:
            state["skipped_budget"] += 1
            return
        rec = {"mode": mode, "qid": q["qid"], "need": q["need"], "language": q["language"], "style": q["style"],
               "question": q["question"], "model": model, "repeat": repeat,
               "asked_at": datetime.now(IST).isoformat(timespec="seconds")}
        t0 = time.time()
        for attempt in range(3):
            try:
                resp = await client.chat.completions.create(
                    model=model, messages=[{"role": "user", "content": q["question"]}],
                    max_tokens=args.max_tokens, extra_body=body)
                msg = resp.choices[0].message
                usage = resp.usage.model_dump() if resp.usage else {}
                rec.update({
                    "answer": msg.content, "finish_reason": resp.choices[0].finish_reason,
                    "provider": getattr(resp, "provider", None), "usage": usage,
                    "cost_usd": usage.get("cost"),
                    "citations": [a.model_dump() for a in (getattr(msg, "annotations", None) or [])][:10],
                    "latency_s": round(time.time() - t0, 1), "error": None})
                break
            except Exception as e:  # keep the error in the log; retry twice
                rec.update({"answer": None, "error": f"{type(e).__name__}: {str(e)[:300]}", "cost_usd": 0})
                await asyncio.sleep(5 * (attempt + 1))
        state["spent"] += rec.get("cost_usd") or 0
        state["n"] += 1
        out.write(json.dumps(rec, ensure_ascii=False) + "\n")
        out.flush()
        status = "ok" if rec.get("answer") else f"ERROR {rec['error'][:80]}"
        print(f"[{state['n']}] {mode} {q['qid']} {model} r{repeat}: {status} | ${rec.get('cost_usd') or 0:.5f} | total ${state['spent']:.4f}", flush=True)


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, help="run name, e.g. pilot")
    ap.add_argument("--mode", choices=["memory", "web"], default="memory")
    ap.add_argument("--qids", nargs="*", help="question ids; 'pilot' = the 10 pilot questions; empty = all")
    ap.add_argument("--models", nargs="*", default=list(MODELS))
    ap.add_argument("--repeats", type=int, default=1)
    ap.add_argument("--budget", type=float, required=True, help="hard USD cap for this run file")
    ap.add_argument("--max-tokens", type=int, default=2500)
    ap.add_argument("--web-results", type=int, default=10)
    ap.add_argument("--engine", choices=["exa", "native"], default="exa", help="web mode: Exa for all models, or each provider's own search")
    ap.add_argument("--concurrency", type=int, default=6)
    args = ap.parse_args()

    load_dotenv(ROOT / ".env")
    client = AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=os.environ["OPENROUTER_API_KEY"])
    qids = PILOT_QIDS if args.qids == ["pilot"] else args.qids
    questions = load_questions(qids)
    out_path = ROOT / "logs" / "part1" / f"{args.run}.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    done, spent = done_keys(out_path)
    mode_label = args.mode if args.mode == "memory" else f"web_{args.engine}"
    state = {"spent": spent, "n": 0, "skipped_budget": 0}
    jobs = [(q, m, r) for r in range(1, args.repeats + 1) for q in questions for m in args.models
            if (mode_label, q["qid"], m, r) not in done]
    print(f"{len(jobs)} calls to make ({len(done)} already done), already spent ${spent:.4f}, budget cap ${args.budget}")
    sem = asyncio.Semaphore(args.concurrency)
    with open(out_path, "a", encoding="utf-8") as out:
        await asyncio.gather(*(ask(client, sem, q, m, mode_label, r, args, state, out) for q, m, r in jobs))
    print(f"finished: {state['n']} calls, total spent in this run file ${state['spent']:.4f}"
          + (f", {state['skipped_budget']} skipped because the budget cap was reached" if state["skipped_budget"] else ""))


if __name__ == "__main__":
    asyncio.run(main())
