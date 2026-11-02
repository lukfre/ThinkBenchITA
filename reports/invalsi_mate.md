# INVALSI MATE (`invalsi_mate`)

- **Source:** ai4text/Invalsi@9656a495 (invalsi_mate.csv, split `validation`)
- **Paper:** Puccetti, Cassese, Esuli, 2024, INVALSI - Mathematical and Language Understanding in Italian: A CALAMITA Challenge (CLiC-it 2024, aclanthology.org/2024.clicit-1.129)
- **Licence:** not declared on the dataset card; the items are INVALSI test questions
- **Scorer:** mcq (generated letter), for every item of the benchmark

## Items

| lang | items | ready | pending translation |
|---|---|---|---|
| it | 420 | 420 | 0 |
| en | – (no English side) | | |

Scorer per item: `mcq` 400, `exact_match` 20.

On by default: it/None 397.

## ID alignment between Italian and English

- single-language benchmark: nothing to align.

## Missing or malformed items

| kind | count | examples |
|---|---|---|
| options_not_lettered | 1 | `invalsi-mate-074` the four options are listed without letters; the gold 'A' means the first one |
| gold_duplicated | 1 | `invalsi-mate-157` distractor alt3 equals the gold (20): the right answer appears under two letters |
| broken | 1 | `invalsi-mate-271` no question and no options: the context text is repeated twice; the gold 'C' refers to nothing |
| typo | 1 | `invalsi-mate-289` "Se si sostituisce con un numero naturale": the variable 'a' is missing after 'sostituisce'; still readable |

Full log: [issues/invalsi_mate.jsonl](issues/invalsi_mate.jsonl). Nothing listed here was edited in the data.

## Notes and decisions

- Diagnostic set: every item has meta.diagnostic=true; report it separately from the main results. Italian only.
- Format choice (2026-10-15): multiple choice answered by GENERATION. The paper turns every question into multiple choice and scores by likelihood: scelta multipla and vero/falso are multiple choice already, numero gets four options (the gold plus the authors' distractors alt1-alt3), and the 20 completa frase items are excluded, giving 400 items. We keep the paper's items and options but let the model reason and write its letter, since we evaluate reasoning models. This is easier than open-ended answers, but it keeps the benchmark diverse, and it avoids a real ambiguity of open scoring: several numero questions ask for part of the answer (invalsi-mate-120 asks for the exponent, the gold is 10^26) or are phrased as fill-in-the-blank.
- On by default (meta.default): 397 items = the paper's 400 minus invalsi-mate-271, which is broken, and the two flagged items (074, 157; off since 2026-11-02, 399 before). The 20 completa frase items stay in the file with meta.official=false, scored by exact_match (unreliable on free-form answers), off by default.
- numero options are shuffled with seed 20261015; the order depends on the item id only (meta.options; meta.gold_value keeps the gold as written in the source). Options are added after the question as 'A. ...' lines; scelta multipla items show their options as written in the source, so they are not shuffled.
- Prompt: source text (testo, blank line, domanda), then our Italian instruction 'Rispondi con la lettera dell'opzione corretta, nel formato "Risposta: X".' (true/false: 'Rispondi con V (vero) o F (falso)...'). There is no official generative prompt: the paper only scores likelihoods.
- Figures: 28 items mention a picture, a table or a box ('osserva', 'in figura'). All were read: tables and boxes are given inline as text and the pictures are decorative, so every item is answerable from the text.
- Item problems (issue log): invalsi-mate-271 broken (excluded by default); invalsi-mate-074 options without letters and invalsi-mate-157 gold also among the distractors (off by default since 2026-11-02, not edited); invalsi-mate-289 small typo.
- Numeric options keep the source's decimal point (e.g. 6.12) even where the question text uses a decimal comma.
