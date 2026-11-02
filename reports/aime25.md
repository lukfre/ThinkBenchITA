# AIME 2025 (`aime25`)

- **Source:** en: MathArena/aime_2025@c94da77e; it: fedric95/AIME2025-Multilingual@ae0d215b (config italian)
- **Paper:** MAA American Invitational Mathematics Examination 2025 (I and II); MathArena (Dekoninck et al., 2026, arXiv:2605.00674); AIME2025-Multilingual (Ricciuti & D'Amato, 2025)
- **Licence:** CC BY-NC-SA 4.0 (MathArena). The multilingual card says MIT, but its English is MathArena's text, so the NC-SA terms apply to it too. Problems © MAA.
- **Scorer:** math_verify on the last \boxed{}

## Items

| lang | items | ready | pending translation |
|---|---|---|---|
| it | 30 | 30 | 0 |
| en | 30 | 30 | 0 |

Scorer per item: `math_verify` 60.

## ID alignment between Italian and English

- ids in both languages: **30**
- only in Italian: **0**
- only in English: **0**

## Missing or malformed items

| kind | count | examples |
|---|---|---|
| translation_style | 4 | `aime25-I-10` "pesantemente delineati" is a calque of "heavily outlined"; "bordati in grassetto" would be natural; `aime25-II-03` "rosso è solido, blu è tratteggiato": "solid" is "continuo" for a line; "segmenti di linea unitaria" is awkward ("segmenti unitari"); `aime25-II-12` `$11$-sided` became "con 11 lati" and "11-gono" in plain text, outside math mode (harmless) |

Full log: [issues/aime25.jsonl](issues/aime25.jsonl). Nothing listed here was edited in the data.

## Notes and decisions

- There is no official machine-readable AIME: MAA publishes the exam as booklets. MathArena's copy (extracted, converted to LaTeX and verified for the MathArena leaderboard) is used as the reference English text.
- The Italian is AIME2025-Multilingual's translation of that same text: four candidates per problem (2x GPT-4o, 2x Claude 3.7 Sonnet), GPT-4o picks one, then a manual check by the authors. The build checks that its English still equals MathArena's, problem by problem.
- Prompt: MathArena's instruction placed before the problem, as MathArena does (template matharena-aime-v1). The Italian instruction is our translation; MathArena has none.
- 5 problems carry their figure as TikZ or Asymptote code in both languages: aime25-I-02, aime25-I-11, aime25-II-03, aime25-II-05, aime25-II-06.
- Translation style issues are in the issue log (kind translation_style); none changes the mathematics.
- Ids follow the exam order: aime25-I-01 ... aime25-II-15. Previous sources (opencompass/AIME2025, yentinglin/aime_2025) were dropped: their Part II is a looser re-transcription, and they drop figures.
