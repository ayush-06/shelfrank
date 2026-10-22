"""Part 2 scoring: what makes a product win on the shelf?

In:  logs/part2/<run>.jsonl (one or more), data/part2/shelves.csv
Out: results/part2/*.csv  and a printed summary

Metrics (all per model and overall):
  pick share     how often each product / brand is picked in the base condition (fair share = 1 in 8)
  position       pick rate by slot 1-8 across whole-shelf conditions (fair = 12.5%)
  lift           target's pick rate with a change minus its pick rate without it (badge/price vs base,
                 rating/reviews vs rating_ctrl), with a 95% interval (normal approximation)
  badge in ₹     the price cut that gives the same lift as a badge (interpolated from the price ladder)
  brand effect   Pilgrim's share with real names vs names hidden vs names swapped
  wrong picks    picks of the deliberately wrong product, and picks over the shopper's budget
  consistency    same answer for the identical trial asked twice (base repeat 1 vs 2)
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results" / "part2"


def load(runs):
    rows = []
    for r in runs:
        for line in (ROOT / "logs" / "part2" / f"{r}.jsonl").read_text(encoding="utf-8").splitlines():
            rows.append(json.loads(line))
    d = pd.DataFrame(rows)
    d = d[d.raw.notna()].copy()
    d["model"] = d.model.str.split("/").str[1]
    d["level"] = d.level.astype(str)
    return d


def ci(p1, n1, p0, n0):
    se = np.sqrt(p1 * (1 - p1) / max(n1, 1) + p0 * (1 - p0) / max(n0, 1))
    return 1.96 * se


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="+")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    d = load(args.runs)
    sh = pd.read_csv(ROOT / "data" / "part2" / "shelves.csv")
    role = dict(zip(sh.product_key, sh.role))
    brand = dict(zip(sh.product_key, sh.brand))
    price = dict(zip(sh.product_key, sh.price))
    budget = dict(zip(sh.shelf, sh.budget_inr))
    d["pick_role"] = d.pick_key.map(role)
    d["pick_brand"] = d.pick_key.map(brand)
    print(f"{len(d)} answers, {d.pick_key.isna().sum()} unparsed ({d.pick_key.isna().mean():.1%})")
    d = d[d.pick_key.notna()].copy()
    models = ["ALL"] + sorted(d.model.unique())

    def per_model(fn):
        out = []
        for m in models:
            x = d if m == "ALL" else d[d.model == m]
            r = fn(x)
            if r is not None:
                r.insert(0, "model", m)
                out.append(r)
        return pd.concat(out, ignore_index=True) if out else pd.DataFrame()

    # 1. pick share in base (real names, no ratings/badges), by brand role and by brand
    base = d[d.condition == "base"]
    share_role = per_model(lambda x: (x[x.condition == "base"].pick_role.value_counts(normalize=True).mul(100).round(1)
                                      .rename("pick_pct").rename_axis("role").reset_index()))
    share_role.to_csv(OUT / "pick_share_by_role.csv", index=False)
    share_shelf = (base.groupby(["shelf", "pick_brand"]).size() / base.groupby("shelf").size() * 100).round(1)
    share_shelf.rename("pick_pct").reset_index().to_csv(OUT / "pick_share_by_shelf_brand.csv", index=False)
    pil = per_model(lambda x: x[x.condition == "base"].groupby("shelf").apply(
        lambda g: (g.pick_role == "pilgrim").mean() * 100).round(1).rename("pilgrim_pick_pct").reset_index())
    pil.to_csv(OUT / "pilgrim_by_shelf.csv", index=False)

    # 2. position bias (whole-shelf conditions, all products rotated through every slot)
    whole = d[d.condition.isin(["base", "hinglish", "no_budget", "rating_ctrl", "brand_hidden", "brand_swap"])]
    pos = per_model(lambda x: (x[x.condition.isin(whole.condition.unique())].pick_slot
                               .value_counts(normalize=True).sort_index().mul(100).round(1)
                               .rename("pick_pct").rename_axis("slot").reset_index()))
    pos.to_csv(OUT / "position_bias.csv", index=False)

    # 3. lift for one-product changes
    rows = []
    for m in models:
        x = d if m == "ALL" else d[d.model == m]
        ref = {"badge": "base", "price": "base", "rating": "rating_ctrl", "reviews": "rating_ctrl"}
        for cond, refc in ref.items():
            y = x[x.condition == cond]
            r = x[x.condition == refc]
            if y.empty or r.empty:
                continue
            for lv, g in y.groupby("level"):
                hit = (g.pick_key == g.target).mean()
                # reference: how often the same target products are picked with no change
                base_rate = np.mean([(r[r.shelf == s].pick_key == t).mean() for s, t in
                                     g[["shelf", "target"]].drop_duplicates().itertuples(index=False)
                                     if (r.shelf == s).any()])
                n0 = len(r[r.shelf.isin(g.shelf.unique())])
                rows.append({"model": m, "condition": cond, "level": lv, "n": len(g),
                             "target_pick_pct": round(hit * 100, 1), "reference_pct": round(base_rate * 100, 1),
                             "lift_pts": round((hit - base_rate) * 100, 1),
                             "ci95_pts": round(ci(hit, len(g), base_rate, n0) * 100, 1)})
    lift = pd.DataFrame(rows)
    lift.to_csv(OUT / "lift.csv", index=False)

    # 3b. badge worth in rupees: price cut % with the same lift, times the average shelf price
    worth = []
    for m in models:
        L = lift[lift.model == m]
        pr = L[L.condition == "price"].copy()
        if pr.empty:
            continue
        pr["pct"] = pr.level.astype(float)
        pr = pr.sort_values("lift_pts")
        avg_price = np.mean(list(price.values()))
        for _, b in L[L.condition == "badge"].iterrows():
            cut = np.interp(b.lift_pts, pr.lift_pts, -pr.pct * 100, left=np.nan, right=np.nan)
            worth.append({"model": m, "badge": b.level, "lift_pts": b.lift_pts,
                          "same_as_price_cut_pct": None if np.isnan(cut) else round(cut, 1),
                          "approx_inr": None if np.isnan(cut) else round(cut / 100 * avg_price)})
    pd.DataFrame(worth).to_csv(OUT / "badge_worth.csv", index=False)

    # 4. brand effect: Pilgrim product pick rate with names, hidden, swapped (Pilgrim's product wearing the favourite's name)
    def brand_eff(x):
        out = {}
        for c in ["base", "brand_hidden", "brand_swap"]:
            y = x[x.condition == c]
            if len(y):
                out[c] = round((y.pick_role == "pilgrim").mean() * 100, 1)
        fav = x[x.condition.isin(["base", "brand_hidden", "brand_swap"])]
        out.update({f"fav_{c}": round(((fav.condition == c) & (fav.pick_role == "part1_favourite")).sum()
                                      / max((fav.condition == c).sum(), 1) * 100, 1)
                    for c in ["base", "brand_hidden", "brand_swap"]})
        return pd.DataFrame([out])
    per_model(brand_eff).to_csv(OUT / "brand_effect.csv", index=False)

    # 5. wrong picks and budget breaks (base and hinglish)
    def wrong(x):
        out = []
        for c in ["base", "hinglish", "no_budget"]:
            y = x[x.condition == c]
            if len(y):
                over = y.apply(lambda r: price.get(r.pick_key, 0) > budget[r.shelf], axis=1).mean()
                out.append({"condition": c, "n": len(y), "wrong_product_pct": round((y.pick_role.str.startswith("wrong")).mean() * 100, 1),
                            "over_budget_pct": round(over * 100, 1), "pilgrim_pct": round((y.pick_role == "pilgrim").mean() * 100, 1)})
        return pd.DataFrame(out)
    per_model(wrong).to_csv(OUT / "wrong_picks_and_language.csv", index=False)

    # 6. consistency: identical base trial (same shelf, same order) asked twice
    b = d[d.condition == "base"].copy()
    b["okey"] = b.shelf + "|" + b.order.apply(lambda o: ",".join(o))
    pairs = b.groupby(["model", "okey"]).pick_key.agg(list)
    pairs = pairs[pairs.apply(len) >= 2]
    cons = pairs.apply(lambda l: l[0] == l[1]).groupby("model").mean().mul(100).round(1)
    cons.rename("same_answer_pct").reset_index().to_csv(OUT / "consistency.csv", index=False)

    pd.set_option("display.width", 200)
    print("\nPick share by role (base):\n", share_role.pivot(index="role", columns="model", values="pick_pct").to_string())
    print("\nPosition (all models):\n", pos[pos.model == "ALL"].to_string(index=False))
    print("\nLift (all models):\n", lift[lift.model == "ALL"].to_string(index=False))
    print("\nBrand effect:\n", pd.read_csv(OUT / "brand_effect.csv").to_string(index=False))
    print("\nWrong picks:\n", pd.read_csv(OUT / "wrong_picks_and_language.csv").to_string(index=False))
    print("\nConsistency:\n", cons.to_string())


if __name__ == "__main__":
    main()
