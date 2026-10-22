"""Write results/part2/shelves_review.md: the 10 shelves and their cards, for the user to review before spending."""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
ROLE = {"pilgrim": "Pilgrim", "part1_favourite": "AI favourite", "d2c_peer": "D2C peer", "legacy": "Legacy",
        "wrong_over_budget": "❌ over budget", "wrong_concern": "❌ wrong fit"}


def main():
    sh = pd.read_csv(ROOT / "data" / "part2" / "shelves.csv")
    cards = pd.read_csv(ROOT / "data" / "part2" / "cards.csv").fillna("")
    d = sh.merge(cards[["shelf", "product_key", "name", "size", "key_ingredients", "good_for", "claims"]],
                 on=["shelf", "product_key"], how="left")
    q = pd.read_csv(ROOT / "data" / "part1" / "questions.csv").set_index("qid").question
    lines = ["# Part 2 shelves, for review", "",
             "Each shelf = the Part 1 \"need + budget\" question + 8 products from 8 brands, picked by the written rule in "
             "`src/part2_shelves.py`. **AI favourite** = among the brands the AIs named most for this need in Part 1. "
             "**❌** = deliberately wrong (over budget, or a different concern), to check whether the AI notices. "
             "*Mentions* = how often the AIs named this brand for this need in Part 1.", ""]
    for sid, g in d.groupby("shelf"):
        lines += [f"## {sid}: {g.need.iloc[0]} (budget ₹{g.budget_inr.iloc[0]})", f"> {q[f'{sid}-b-en']}", "",
                  "| Role | Brand | Product (card name) | Size | Price | Key ingredients | Mentions |", "|---|---|---|---|---|---|---|"]
        for r in g.itertuples():
            flag = " ⚠ thin card" if not r.key_ingredients and not r.claims else ""
            lines.append(f"| {ROLE[r.role]} | {r.brand} | {r.name}{flag} | {r.size} | ₹{r.price} | "
                         f"{str(r.key_ingredients).replace(';', ',')} | {r.brand_need_mentions_part1} |")
        lines.append("")
    out = ROOT / "results" / "part2" / "shelves_review.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
