"""Quick look at Part 1 answers: which brands each answer mentions (simple name matching, first-mention order).

This is a rough first pass for eyeballing the pilot. The real scoring uses an extraction step
plus matching against our product catalogue.
"""

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUR = pd.read_csv(ROOT / "data" / "brands.csv").brand.tolist()
OUTSIDE = ["The Ordinary", "Cetaphil", "La Roche-Posay", "Neutrogena", "CeraVe", "Bioderma", "Simple", "Olay", "Sebamed",
           "Kama Ayurveda", "Forest Essentials", "Nykaa", "Kay Beauty", "Paula's Choice", "Cosrx", "Beauty of Joseon",
           "Innisfree", "Some By Mi", "Uriage", "Avene", "Eucerin", "Aveeno", "Nizoral", "Selsun", "Scalpe", "Kerastase",
           "Matrix", "Wella", "Schwarzkopf", "Mintop", "Tugain", "Vaseline", "Glow & Lovely", "Clean & Clear", "Garnier",
           "Maybelline", "L'Oreal", "Revlon", "MAC", "Huda Beauty", "Charlotte Tilbury", "Ponds", "Sesderma", "Sotrue",
           "Re'equil", "Fixderma", "Minimalist", "Mamaearth", "Plum", "WOW", "Indulekha", "Parachute", "Dabur", "Biotique",
           "Himalaya", "Lotus", "Pilgrim", "Dot & Key", "Foxtale", "The Derma Co", "Deconstruct", "Aqualogica", "Bare Anatomy",
           "Traya", "Man Matters", "Bodywise", "Plix", "Kesh King", "Navratna", "Bajaj", "Clinic Plus", "Sunsilk", "Dove",
           "Head & Shoulders", "Pantene", "TRESemme", "SUGAR", "Swiss Beauty", "Renee", "Faces Canada", "Insight", "Mars",
           "Colorbar", "Lakme", "Nivea", "Hyphen", "Dr. Sheth's", "Arata", "ThriveCo", "Bblunt", "Juicy Chemistry",
           "Conscious Chemist", "Earth Rhythm", "Chemist at Play", "mCaffeine", "Lacto Calamine", "Joy", "Jovees", "VLCC"]
ALIASES = {"Lakme": r"lakm[eē]", "L'Oreal": r"l['’]?or[eé]al", "Ponds": r"pond['’]?s", "Re'equil": r"re['’]?equil",
           "TRESemme": r"tresemm[eé]", "Head & Shoulders": r"head\s*(&|and)\s*shoulders", "Dot & Key": r"dot\s*(&|and)\s*key",
           "Dr. Sheth's": r"dr\.?\s*sheth", "The Derma Co": r"derma\s*co\b", "Bodywise": r"bodywise", "WOW": r"\bwow\b",
           "MAC": r"\bmac\b(?! ?book)", "Joy": r"\bjoy\b(?= (skin|cosmetic|sun))", "Simple": r"\bsimple\b(?= (kind|refreshing|daily|water|hydrating|micellar|moistur))",
           "Mars": r"\bmars\b(?= (cosmetic|lip|matte))", "Insight": r"\binsight\b(?= cosmetic| lip)", "Bajaj": r"bajaj",
           "Pilgrim": r"pilgrim", "Mamaearth": r"mama\s*earth", "SUGAR": r"\bsugar\b(?= (cosmetic|matte|smudge|lip|pop))"}
BRANDS = sorted({b for b in OUR + OUTSIDE if b not in ("Zandu Care (Navratna)", "L'Oreal Paris", "Pond's", "Be Bodywise", "WOW Skin Science", "Bajaj Almond Drops", "Lotus Herbals")})


def brand_rx(b):
    return re.compile(ALIASES.get(b, r"\b" + re.escape(b) + r"\b"), re.I)


RX = {b: brand_rx(b) for b in BRANDS}


def mentions(text):
    hits = []
    for b, rx in RX.items():
        m = rx.search(text or "")
        if m:
            hits.append((m.start(), b))
    return [b for _, b in sorted(hits)]


def main(files):
    rows = []
    for f in files:
        for line in Path(f).read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            if r.get("answer"):
                r["brands"] = mentions(r["answer"])
                rows.append(r)
    df = pd.DataFrame(rows)
    df["model_short"] = df.model.str.split("/").str[1]
    df["pilgrim"] = df.brands.apply(lambda b: "Pilgrim" in b)
    df["pilgrim_rank"] = df.brands.apply(lambda b: b.index("Pilgrim") + 1 if "Pilgrim" in b else None)
    df["n_brands"] = df.brands.str.len()
    df["answer_words"] = df.answer.str.split().str.len()
    print(f"answers: {len(df)} | total cost ${df.cost_usd.sum():.3f}\n")
    for mode, d in df.groupby("mode"):
        cnt = Counter(b for bl in d.brands for b in bl)
        top = ", ".join(f"{b} {round(100 * c / len(d))}%" for b, c in cnt.most_common(15))
        print(f"[{mode}] % of answers mentioning each brand (top 15): {top}")
        print(f"[{mode}] Pilgrim mentioned in {d.pilgrim.sum()}/{len(d)} answers\n")
    print(df.groupby(["mode", "model_short"]).agg(answers=("qid", "size"), avg_brands=("n_brands", "mean"),
          avg_words=("answer_words", "mean"), pilgrim_mentions=("pilgrim", "sum"), avg_cost=("cost_usd", "mean")).round(4).to_string())
    print("\nPilgrim mentions:")
    print(df[df.pilgrim][["mode", "qid", "model_short", "pilgrim_rank", "n_brands"]].to_string(index=False))
    out = ROOT / "logs" / "part1" / "peek.csv"
    df[["mode", "qid", "need", "language", "style", "model_short", "brands", "pilgrim", "pilgrim_rank", "n_brands", "answer_words", "cost_usd", "answer"]].to_csv(out, index=False, encoding="utf-8-sig")
    print(f"\nper-answer table: {out}")


if __name__ == "__main__":
    main(sys.argv[1:])
