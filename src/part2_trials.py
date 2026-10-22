"""Part 2: generate the trials (one line per shelf variation) from data/part2/shelves.csv.

Each trial = one shelf + ONE change + a product order. The AI sees the shopper's question and 8 cards.
Conditions:
  base          no ratings, no badges, real prices; 8 rotations (each product once in each slot) x repeats
  hinglish      same as base, question in Hinglish
  no_budget     same as base, the question's "under ₹X" removed (like Part 1's generic style)
  rating_ctrl   every product shows 4.2★ (1,200 reviews)
  rating        one target shows 4.0/3.8/3.4 or 4.4/4.6/4.8/5.0★, the rest 4.2★ (1,200 reviews)
  reviews       one target shows 4.2★ with 50 or 5,000 reviews, the rest 4.2★ (1,200 reviews)
  badge         one target gets "Bestseller" / "Dermatologist recommended" / "Sponsored"
  price         one target's price -20% / -10% / +10% / +20%
  brand_hidden  no brand names on any card
  brand_swap    Pilgrim's card carries the top Part 1 favourite's brand name, and vice versa
Every one-product change is applied to each of the 8 products in turn. Product orders are random
(seeded) for one-product changes and cyclic rotations for whole-shelf conditions, so position effects
average out and can be measured.

Writes data/part2/trials_<set>.jsonl     sets: full | pilot
"""

import argparse
import json
import random
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RATING_LEVELS = [-0.8, -0.4, -0.2, 0.2, 0.4, 0.6, 0.8]
BADGES = ["Bestseller", "Dermatologist recommended", "Sponsored"]
PRICE_LEVELS = [-0.2, -0.1, 0.1, 0.2]


def rotation(keys, r):
    return keys[r:] + keys[:r]


def make(shelves, questions, which="full", base_repeats=2, seed=7):
    rng = random.Random(seed)
    trials = []
    for sid, sh in shelves.groupby("shelf", sort=True):
        keys = sh.product_key.tolist()
        role = dict(zip(sh.product_key, sh.role))
        brand = dict(zip(sh.product_key, sh.brand))
        q = {lang: questions[(questions.qid == f"{sid}-b-{'en' if lang == 'en' else 'hi'}")].question.iloc[0]
             for lang in ("en", "hinglish")}
        q["no_budget"] = re.sub(r",?\s*under ₹\d+", "", q["en"])  # same question, price limit removed
        pilgrim = next(k for k in keys if role[k] == "pilgrim")
        fav = next(k for k in keys if role[k] == "part1_favourite")  # the most-named favourite (first added)
        targets = keys
        rots = range(8)
        if which == "pilot":  # smaller: two targets (Pilgrim + top favourite), half the rotations
            targets, rots = [pilgrim, fav], range(0, 8, 2)

        def add(cond, level=None, target=None, order=None, lang="en", rep=1, **mods):
            trials.append({"trial_id": f"{sid}|{cond}|{level}|{target}|{lang}|{rep}|{len(trials)}",
                           "shelf": sid, "condition": cond, "level": level, "target": target,
                           "target_brand": brand.get(target), "target_role": role.get(target),
                           "language": lang, "repeat": rep, "question": q[lang],
                           "order": order or rng.sample(keys, len(keys)), "mods": mods})

        for rep in range(1, (1 if which == "pilot" else base_repeats) + 1):
            for r in rots:
                add("base", order=rotation(keys, r), rep=rep)
        for r in rots:
            add("hinglish", order=rotation(keys, r), lang="hinglish")
            add("no_budget", order=rotation(keys, r), lang="no_budget")
            add("rating_ctrl", order=rotation(keys, r), ratings={k: [4.2, 1200] for k in keys})
            add("brand_hidden", order=rotation(keys, r), hide_brands=True)
            add("brand_swap", order=rotation(keys, r), brand_swap=[pilgrim, fav])
        for t in targets:
            for lv in RATING_LEVELS:
                add("rating", level=lv, target=t,
                    ratings={k: [round(4.2 + (lv if k == t else 0), 1), 1200] for k in keys})
            for n in (50, 5000):
                add("reviews", level=n, target=t, ratings={k: [4.2, n if k == t else 1200] for k in keys})
            for b in BADGES:
                add("badge", level=b, target=t, badge={t: b})
            for lv in PRICE_LEVELS:
                add("price", level=lv, target=t, price_change={t: lv})
    return trials


def make_card_test(shelves, questions, cards):
    """Pilgrim card test: only Pilgrim's card changes (hypothetical copy, not Pilgrim's real claims).
    plain          no claims, no texture line
    shopper_words  'Good for' leads with the shopper's own words from the question
    derm_tested    second claim replaced by 'Dermatologically tested'
    clinical       second claim replaced by 'Clinically tested: visible results in 4 weeks'
    Compared against the base condition of the main run (same shelves, same 8 rotations)."""
    trials = []
    for sid, sh in shelves.groupby("shelf", sort=True):
        keys = sh.product_key.tolist()
        pk = sh[sh.role == "pilgrim"].product_key.iloc[0]
        card = cards[(cards.shelf == sid) & (cards.product_key == pk)].iloc[0]
        qrow = questions[questions.qid == f"{sid}-b-en"].iloc[0]
        claims = [x for x in str(card.claims).split(" | ") if x]
        words = ", ".join(w.strip().capitalize() for w in str(qrow.concern).split(";"))
        words = {"Natural shade": "Natural everyday shades"}.get(words, words).replace("No white layer", "No white cast")
        variants = {
            "plain": {"claims": "", "texture": ""},
            "shopper_words": {"good_for": f"{words}; {str(card.good_for).split(';')[0]}"},
            "derm_tested": {"claims": " | ".join(claims[:1] + ["Dermatologically tested"])},
            "clinical": {"claims": " | ".join(claims[:1] + ["Clinically tested: visible results in 4 weeks"])},
        }
        for v, ov in variants.items():
            for r in range(8):
                trials.append({"trial_id": f"{sid}|pilgrim_card|{v}|{pk}|en|1|{len(trials)}", "shelf": sid,
                               "condition": "pilgrim_card", "level": v, "target": pk, "target_brand": "Pilgrim",
                               "target_role": "pilgrim", "language": "en", "repeat": 1, "question": qrow.question,
                               "order": rotation(keys, r), "mods": {"card_override": {pk: ov}}})
    return trials


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", choices=["full", "pilot", "card"], default="full")
    ap.add_argument("--shelves", nargs="*", help="limit to these shelf ids, e.g. N01 N07")
    args = ap.parse_args()
    shelves = pd.read_csv(ROOT / "data" / "part2" / "shelves.csv")
    if args.shelves:
        shelves = shelves[shelves.shelf.isin(args.shelves)]
    questions = pd.read_csv(ROOT / "data" / "part1" / "questions.csv")
    if args.set == "card":
        trials = make_card_test(shelves, questions, pd.read_csv(ROOT / "data" / "part2" / "cards.csv").fillna(""))
    else:
        trials = make(shelves, questions, args.set)
    out = ROOT / "data" / "part2" / f"trials_{args.set}.jsonl"
    with open(out, "w", encoding="utf-8") as f:
        for t in trials:
            f.write(json.dumps(t, ensure_ascii=False) + "\n")
    print(f"{len(trials)} trials -> {out}")
    print(pd.DataFrame(trials).groupby(["shelf", "condition"]).size().unstack(fill_value=0).to_string())


if __name__ == "__main__":
    main()
