"""Readable copies of the raw model logs, for browsing on GitHub.

Part 1: results/readable/part1/<qid>.md   - every model's full answer to that question (all modes, repeats),
                                            plus the web pages each answer cited
Part 2: results/readable/part2/<run>/<shelf>.md - the exact prompt the models saw, then every trial:
                                            what changed, the product order, and each model's pick + reason

The raw JSONL logs themselves are in logs/ (one line per API call, with usage and cost).

  .venv/Scripts/python src/export_readable.py --part1 --part2 pilot
"""

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results" / "readable"
P1_RUNS = ["pilot_memory", "pilot_web", "costtest", "full_memory", "full_web"]
ROLE = {"pilgrim": "Pilgrim", "part1_favourite": "AI favourite", "d2c_peer": "D2C peer", "legacy": "Legacy",
        "wrong_over_budget": "❌ over budget", "wrong_concern": "❌ wrong fit"}


def read_jsonl(path):
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def part1():
    rows = []
    for run in P1_RUNS:
        p = ROOT / "logs" / "part1" / f"{run}.jsonl"
        if p.exists():
            rows += [{**r, "run": run} for r in read_jsonl(p)]
    d = pd.DataFrame(rows)
    d = d[d.answer.notna()]
    out = OUT / "part1"
    out.mkdir(parents=True, exist_ok=True)
    index = ["# Part 1: every model's answer, by question", "",
             "| Question id | Need | Style | Language | Question | Answers |", "|---|---|---|---|---|---|"]
    for qid, g in d.groupby("qid", sort=True):
        f = g.iloc[0]
        lines = [f"# {qid}: {f.need} ({f['style']}, {f.language})", "", f"> {f.question}", "",
                 f"{len(g)} answers. Run files: {', '.join(sorted(g.run.unique()))}. "
                 "Modes: memory = no internet; web_exa = Exa search, 10 pages; web_native = the provider's own search.", ""]
        for (mode, model), h in g.sort_values(["mode", "model", "run", "repeat"]).groupby(["mode", "model"], sort=False):
            lines.append(f"## {mode} · {model}")
            for r in h.itertuples():
                cost = f"${r.cost_usd:.5f}" if isinstance(r.cost_usd, float) else ""
                lines += ["", f"**Run `{r.run}`, repeat {r.repeat}** ({cost})", "", str(r.answer).strip(), ""]
                cites = [c.get("url_citation", {}).get("url") or c.get("url") for c in (r.citations or []) if isinstance(c, dict)]
                cites = [c for c in cites if c]
                if cites:
                    lines.append("Pages cited: " + ", ".join(f"<{c}>" for c in cites[:10]))
                    lines.append("")
                lines.append("---")
        (out / f"{qid}.md").write_text("\n".join(lines), encoding="utf-8")
        index.append(f"| [{qid}]({qid}.md) | {f.need} | {f['style']} | {f.language} | {f.question} | {len(g)} |")
    (out / "README.md").write_text("\n".join(index), encoding="utf-8")
    print(f"part1: {d.qid.nunique()} question pages, {len(d)} answers -> {out}")


def part2(run):
    sys.path.insert(0, str(ROOT / "src"))
    from part2_run import SYSTEM, load_cards, render

    cards = load_cards()
    sh = pd.read_csv(ROOT / "data" / "part2" / "shelves.csv")
    brand = dict(zip(sh.product_key, sh.brand))
    role = dict(zip(sh.product_key, sh.role))
    name = {k: c.name for k, c in cards.items()}
    log = [r for r in read_jsonl(ROOT / "logs" / "part2" / f"{run}.jsonl") if r.get("raw") is not None]
    trial_files = {"pilot": "pilot", "main": "full", "premium": "full", "card": "card"}
    trials = {t["trial_id"]: t for t in read_jsonl(ROOT / "data" / "part2" / f"trials_{trial_files.get(run, 'full')}.jsonl")}
    by_trial = {}
    for r in log:
        by_trial.setdefault(r["trial_id"], []).append(r)
    out = OUT / "part2" / run
    out.mkdir(parents=True, exist_ok=True)
    index = [f"# Part 2 `{run}`: every trial, every model's pick", "", "| Shelf | Trials | Answers |", "|---|---|---|"]
    for sid in sorted({r["shelf"] for r in log}):
        tids = [t for t in by_trial if trials.get(t, {}).get("shelf") == sid]
        first = trials[tids[0]]
        lines = [f"# Shelf {sid}: run `{run}`", "",
                 "## The products", "", "| Role | Brand | Product | Price |", "|---|---|---|---|"]
        for p in sh[sh.shelf == sid].itertuples():
            lines.append(f"| {ROLE[p.role]} | {p.brand} | {name.get(p.product_key, p.title)} | ₹{p.price} |")
        base = next((trials[t] for t in tids if trials[t]["condition"] == "base"), first)
        lines += ["", "## Exact prompt the models saw (one base trial)", "", "```", SYSTEM, "", render(base, cards), "```", "",
                  "## Trials", "Each trial changes ONE thing. *Order* = brands in slots 1–8 as shown.", ""]
        for t in sorted(tids, key=lambda x: (trials[x]["condition"], str(trials[x]["level"]), x)):
            tr = trials[t]
            what = tr["condition"] + (f" = {tr['level']}" if tr["level"] not in (None, "None") else "")
            if tr["target"]:
                what += f" on **{brand.get(tr['target'])}**"
            order = " · ".join(f"{i}. {brand[k]}" for i, k in enumerate(tr["order"], 1))
            lines += [f"### {what} ({tr['language']})", f"Order: {order}", "",
                      "| Model | Picked | Product | Reason |", "|---|---|---|---|"]
            for r in sorted(by_trial[t], key=lambda r: r["model"]):
                k = r.get("pick_key")
                picked = f"{r['pick_slot']}. {brand.get(k, '?')} ({ROLE.get(role.get(k), '')})" if k else "unparsed"
                reason = str(r.get("reason") or r.get("raw") or "").replace("|", "/").replace("\n", " ")
                lines.append(f"| {r['model'].split('/')[1]} | {picked} | {name.get(k, '')} | {reason} |")
            lines.append("")
        (out / f"{sid}.md").write_text("\n".join(lines), encoding="utf-8")
        index.append(f"| [{sid}]({sid}.md) | {len(tids)} | {sum(len(by_trial[t]) for t in tids)} |")
    (out / "README.md").write_text("\n".join(index), encoding="utf-8")
    print(f"part2 {run}: {len(by_trial)} trials, {len(log)} answers -> {out}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--part1", action="store_true")
    ap.add_argument("--part2", nargs="*", default=[], help="Part 2 run names, e.g. pilot main premium card")
    args = ap.parse_args()
    if args.part1:
        part1()
    for run in args.part2:
        part2(run)


if __name__ == "__main__":
    main()
