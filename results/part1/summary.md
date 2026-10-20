# ShelfRank Part 1: "Who gets recommended?" Results (2026-10-21)

## Setup
- **Answers:** 1,360 total, 1,356 scored.
  - **Memory mode:** 60 questions × 3 repeats × 6 cheap models, plus × 1 on GPT-6 Sol, Claude Sonnet 5.5 and Gemini 3.6 Flash. That's 1,260 answers.
  - **Web mode (Exa, 10 pages):** 20 "need + budget" questions × 4 models. 80 answers.
  - **Web mode (each provider's own search):** 10 English questions × GPT-6 Luna and Gemini 3.6 Flash. 20 answers.
- **Scoring:** a cheap model (Claude Haiku 5.5) extracted every recommendation. Each was matched to our catalogue of 57 brands and about 2,100 products, then fact-checked on existence, price, ingredient % and budget.
- **Cost:** answers $3.28 + extraction $0.49.

## Headline numbers
| | Memory | Web (Exa) | Web (own search) |
|---|---|---|---|
| Answers | 1,260 | 80 | 20 |
| **Pilgrim named in** | **2.1%** | **5.0%** | **10.0%** (small sample) |
| Pilgrim's average rank when named | 3.9 | 3.8 | 2.5 |
| Minimalist named in | 28.3% | 28.8% | 40.0% |

## D2C peers: % of answers naming the brand
| Brand | Memory | Web (Exa) | Web (own search) |
|---|---|---|---|
| Minimalist | 28.3 | 28.8 | 40.0 |
| Mamaearth | 13.8 | 18.8 | 0 |
| The Derma Co | 11.5 | 11.2 | 25.0 |
| Plum | 8.6 | 5.0 | 15.0 |
| Dot & Key | 7.1 | 12.5 | 5.0 |
| Re'equil | 5.2 | 8.8 | 5.0 |
| Dr. Sheth's | 4.9 | 8.8 | 0 |
| **Pilgrim** | **2.1** | **5.0** | **10.0** |
| Deconstruct | 1.6 | 2.5 | 20.0 |
| Bare Anatomy | 0.9 | 10.0 | 10.0 |
| Foxtale | 0.7 | 7.5 | 0 |

Global brands are strong in memory mode: Neutrogena 22.7%, Cetaphil 15.1%, The Ordinary 14.0%, Himalaya 15.0%.

## Pilgrim, in detail
- **By need (memory):**
  - Hair growth serum 12.7%
  - Serum for glowing skin 5.6%
  - Serum for acne marks 3.2%
  - **0% for the other 7 needs:** sunscreen, face wash, moisturiser, hair-fall shampoo, dandruff shampoo, hair oil, lipstick.
- **What the AIs know Pilgrim for:** the **3% Redensyl + 4% Anagain hair growth serum** (17 of 33 Pilgrim mentions). Next come the 2% Hyaluronic Acid serum and the 10% Vitamin C Roll-On (3 each). 30 of the 33 mentions name a specific product.
- **By model (memory):**
  - Claude Haiku 11/180
  - Gemini 3.1 Flash-Lite 6/180
  - Gemini 3.6 Flash 4/60
  - DeepSeek 3/180
  - GPT-6 Luna 2/180
  - GPT-6 Sol 1/60
  - **Claude Sonnet 0/60, Llama 4 0/180, Nova 0/180.**
- **By language:** English 1.7% vs Hinglish 2.5%. That's too few mentions to call a difference.
- **By style:** generic 3.3%, need + budget 2.6%, conversational 0.5%.
- **Web, found vs picked:**
  - A Pilgrim page was in the search results for **10 of 100** web answers, and the AI **picked Pilgrim in 3 of those 10**.
  - For comparison, Minimalist was picked in 89% of the answers where it was found, and Himalaya in 100%.
  - **So Pilgrim has both problems: it's rarely found, and rarely picked even when it is found.**
- **Facts about Pilgrim were correct when stated:** 15/15 prices and 5/5 ingredient %s.

## Model behaviour
- **The ChatGPT models often name no brand at all:** GPT-6 Luna in 48% of answers, Sol in 33% (ingredient advice only). When they do name one, it's usually a single product, mostly Minimalist.
- **Accuracy:** "found in catalogue" = the named product exists in the brand's current catalogue.

  | Model | Found in catalogue | Price right (±20%) | Ingredient % right |
  |---|---|---|---|
  | GPT-6 Sol | 94% | 81% | 100% |
  | GPT-6 Luna | 85% | 75% | 100% |
  | Gemini 3.6 Flash | 88% | 67% | 95% |
  | Gemini 3.1 Flash-Lite | 87% | 65% | 96% |
  | Claude Sonnet 5.5 | 86% | 55% | 96% |
  | Claude Haiku 5.5 | 75% | 63% | 98% |
  | DeepSeek V4 Flash | 73% | 65% | 87% |
  | Llama 4 Maverick | **56%** | 50% | 65% |
  | Nova 2 Lite | **53%** | 57% | 73% |

- **Stability** (overlap of the brands named when the same question is repeated; 1 = identical): GPT-6 Luna 0.71, Llama 0.60, Gemini Flash-Lite 0.52, Haiku 0.48, Nova 0.39, DeepSeek 0.32. **Answers change a lot between repeats.**

## Caveats
- We called the models directly; the consumer apps (ChatGPT, Gemini) add their own instructions, personalisation and search.
- Web mode means *Exa's top 10 pages on 2026-10-21*. The own-search check is only 20 answers.
- "Not found in catalogue" ≠ always invented. It can also be a marketplace-only or discontinued product. Some are clearly invented, e.g. "L'Oreal Revlon Total Sun".
- Name matching is automatic, roughly 90% reliable.
- The numbers behind Pilgrim are small (33 mentions), so treat per-need and per-language splits as directional.

## Files
`results/part1/`:
- `answers.csv`, `recommendations.csv`
- `brand_visibility.csv`, `pilgrim_by_*.csv`, `pilgrim_mentions.csv`
- `accuracy.csv`, `stability.csv`, `web_found_vs_picked.csv`
