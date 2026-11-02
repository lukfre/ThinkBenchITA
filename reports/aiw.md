# Alice in Wonderland (AIW) (`aiw`)

- **Source:** github.com/LAION-AI/AIW@73f8298f (prompts/prompts.json, sha256 33aad0d2e5e5)
- **Paper:** Nezhurina, Cipolina-Kun, Cherti, Jitsev, 2024, Alice in Wonderland: Simple Tasks Showing Complete Reasoning Breakdown in State-Of-the-Art Large Language Models (arXiv:2406.02061; TMLR)
- **Licence:** Apache 2.0 (code and prompts)
- **Scorer:** exact_match on the integer after the last answer marker ('### Answer:' / '### Risposta:', within 100 characters, next lines included), else a final \boxed{n}; score.found_by records which

## Items

| lang | items | ready | pending translation |
|---|---|---|---|
| it | 30 | 30 | 0 |
| en | 30 | 30 | 0 |

Scorer per item: `exact_match` 60.

## ID alignment between Italian and English

- ids in both languages: **30**
- only in Italian: **0**
- only in English: **0**

## Missing or malformed items

None found.

## Notes and decisions

- The paper's core sets, by the prompt ids of its supplementary tables: AIW variations 1-4 in three prompt types (STANDARD, THINKING, RESTRICTED; Tab. 2), the AIW Light controls (siblings, family, total girls; Tab. 3-5), and AIW+ variations 1-6 (Tab. 10). 30 prompts per language. The authors' file has 826 prompts, most of them exploratory variants not used for the paper's main results.
- English is the authors' text verbatim (curly apostrophes normalised). The main AIW THINKING prompts use the authors' 'V1' wording and the Light and AIW+ ones 'V2' ('think carefully step by step'), as in the paper.
- Italian (ours, native read pending): every English prompt is parsed into its numbers and parts, the parse must rebuild the English exactly, and the same parts are rendered in Italian, so items are parallel by id. 'fratelli' means both brothers and siblings in Italian: questions about brothers say 'fratelli maschi', about siblings 'fratelli e sorelle'. 'nephews and nieces' -> 'nipoti', 'sons' -> 'figli maschi'. The answer marker is '### Risposta:' in Italian.
- RESTRICTED forbids any text besides the answer line; for a reasoning model this constrains only the final answer, not the thinking block.
- The paper samples many times per prompt (60-100). Report the mean correct rate per variation and the spread across variations of the same problem, the paper's main signal (meta.variation, meta.subset, meta.prompt_type).
- Gold answers: all 30 recomputed from the family structure (a check independent of the file) and equal to the authors' answers.
- Caveat: the problem is famous since 2024 and likely in the training data of recent models; the Light controls help separate memorised answers from reasoning only partly.
