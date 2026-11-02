"""Alice in Wonderland (AIW): simple family-logic problems (Nezhurina et al., 2024).

The paper's core sets, by the prompt ids of its supplementary tables, from the authors'
prompt file (github.com/LAION-AI/AIW, prompts/prompts.json):
  main    AIW variations 1-4 x STANDARD / THINKING / RESTRICTED     (Tab. 2)
  light   controls: siblings (Tab. 3), family (Tab. 4), total girls (Tab. 5), variations 1-4
  plus    AIW+ variations 1-6                                       (Tab. 10)

English is the authors' text, verbatim. Italian is ours: each English prompt is parsed into
its numbers and parts, the parse must rebuild the English exactly, and the same parts are
rendered with Italian templates, so the two languages are item-parallel.
"""

import re

from ..schema import Built, Issues, Item, user
from . import register, release_file

COMMIT = "73f8298f76f15d5cbcef4c92a5a261fb42a3fcf4"
URL = f"https://raw.githubusercontent.com/LAION-AI/AIW/{COMMIT}/prompts/prompts.json"
SHA256 = "33aad0d2e5e5332e19076df9dd903fd395a339fb50d62040b2bb0ab8e5986d5c"

# prompt id -> (set, subset, variation, prompt type), as in the paper's supplementary tables
CORE = {
    55: ("main", "aiw", 1, "standard"), 57: ("main", "aiw", 1, "thinking"), 53: ("main", "aiw", 1, "restricted"),
    56: ("main", "aiw", 2, "standard"), 58: ("main", "aiw", 2, "thinking"), 54: ("main", "aiw", 2, "restricted"),
    63: ("main", "aiw", 3, "standard"), 64: ("main", "aiw", 3, "thinking"), 65: ("main", "aiw", 3, "restricted"),
    69: ("main", "aiw", 4, "standard"), 70: ("main", "aiw", 4, "thinking"), 71: ("main", "aiw", 4, "restricted"),
    277: ("light", "siblings", 1, "thinking"), 278: ("light", "siblings", 2, "thinking"),
    279: ("light", "siblings", 3, "thinking"), 280: ("light", "siblings", 4, "thinking"),
    271: ("light", "family", 1, "thinking"), 272: ("light", "family", 2, "thinking"),
    273: ("light", "family", 3, "thinking"), 274: ("light", "family", 4, "thinking"),
    343: ("light", "total_girls", 1, "thinking"), 344: ("light", "total_girls", 2, "thinking"),
    345: ("light", "total_girls", 3, "thinking"), 346: ("light", "total_girls", 4, "thinking"),
    559: ("plus", "aiw_plus", 1, "thinking"), 560: ("plus", "aiw_plus", 2, "thinking"), 561: ("plus", "aiw_plus", 3, "thinking"),
    562: ("plus", "aiw_plus", 4, "thinking"), 563: ("plus", "aiw_plus", 5, "thinking"), 564: ("plus", "aiw_plus", 6, "thinking"),
}  # fmt: skip

# --- English parts (exact strings of the authors' prompts) ------------------------------------
INSTR_EN = {
    "standard": 'Solve this problem and provide the final answer in following form: "### Answer: ".',
    "thinking_v1": 'Before providing answer to this problem, think carefully and double check the path to the correct solution for any mistakes. Provide then the final answer in following form: "### Answer: ".',
    "thinking_v2": 'Before providing answer to this problem, think carefully step by step and double check the path to the correct solution for any mistakes. Provide then the final answer in following form: "### Answer: ".',
    "restricted": 'To answer the question, DO NOT OUTPUT ANY TEXT EXCEPT following format that contains final answer: "### Answer: ".',
}
QUESTION_EN = {
    "sisters_of_brother": "How many sisters does Alice's brother have?",
    "siblings": "How many siblings does Alice have?",
    "brothers_of_sister": "How many brothers does Alice's sister have?",
    "total_girls": "How many girls are there in total?",
}
PLUS_EN = re.compile(
    r"Alice has (\d+) (sisters?) and (\d+) (brothers?) in total\. Her mother has (\d+) brothers\. She also has (\d+) sister "
    r"who does not have children and who has (\d+) nephews and nieces in total\. Alice's father has (\d+) sisters\. He also has "
    r"a brother who has (\d+) nephews and nieces in total, and who also has (\d+) (sons?|daughters?)\. How many cousins does "
    r"Alice's sister have\? "
)
BASE_EN = re.compile(r"Alice has (\d+) (brothers?|sisters?) and she also has (\d+) (brothers?|sisters?)\. ")

# --- Italian parts (our translation; native read pending) -------------------------------------
# "fratelli" means both "brothers" and "siblings" in Italian: questions about brothers say
# "fratelli maschi", questions about siblings say "fratelli e sorelle".
NOUN_IT = {"brother": ("fratello", "fratelli"), "sister": ("sorella", "sorelle"), "son": ("figlio maschio", "figli maschi"), "daughter": ("figlia", "figlie")}
INSTR_IT = {
    "standard": 'Risolvi questo problema e fornisci la risposta finale nella forma seguente: "### Risposta: ".',
    "thinking_v1": 'Prima di rispondere a questo problema, rifletti attentamente e ricontrolla il ragionamento per individuare eventuali errori. Fornisci poi la risposta finale nella forma seguente: "### Risposta: ".',
    "thinking_v2": 'Prima di rispondere a questo problema, rifletti attentamente passo dopo passo e ricontrolla il ragionamento per individuare eventuali errori. Fornisci poi la risposta finale nella forma seguente: "### Risposta: ".',
    "restricted": 'Per rispondere alla domanda, NON SCRIVERE NESSUN ALTRO TESTO OLTRE AL formato seguente, che contiene la risposta finale: "### Risposta: ".',
}
QUESTION_IT = {
    "sisters_of_brother": "Quante sorelle ha il fratello di Alice?",
    "siblings": "Quanti fratelli e sorelle ha Alice?",
    "brothers_of_sister": "Quanti fratelli maschi ha la sorella di Alice?",
    "total_girls": "Quante ragazze ci sono in totale?",
}


def _it(n: str, noun: str) -> str:
    singular, plural = NOUN_IT[noun.rstrip("s")]
    return f"{n} {singular if n == '1' else plural}"


def parse(text: str) -> dict:
    """Split one English prompt into its parts; raises if the text is not one of the known forms."""
    text = text.replace("’", "'")
    instr = next((k for k, v in INSTR_EN.items() if text.endswith(v)), None)
    if instr is None:
        raise ValueError("unknown instruction")
    body = text[: -len(INSTR_EN[instr])]
    m = PLUS_EN.fullmatch(body)
    if m:
        return {"form": "plus", "groups": m.groups(), "instr": instr}
    m = BASE_EN.match(body)
    if not m:
        raise ValueError("unknown statement")
    question = body[m.end():].rstrip()
    q = next((k for k, v in QUESTION_EN.items() if v == question), None)
    if q is None:
        raise ValueError(f"unknown question {question!r}")
    return {"form": "base", "groups": m.groups(), "question": q, "instr": instr}


def render_en(p: dict) -> str:
    g = p["groups"]
    if p["form"] == "plus":
        body = (f"Alice has {g[0]} {g[1]} and {g[2]} {g[3]} in total. Her mother has {g[4]} brothers. She also has {g[5]} sister "
                f"who does not have children and who has {g[6]} nephews and nieces in total. Alice's father has {g[7]} sisters. He also has "
                f"a brother who has {g[8]} nephews and nieces in total, and who also has {g[9]} {g[10]}. How many cousins does Alice's sister have? ")
    else:
        body = f"Alice has {g[0]} {g[1]} and she also has {g[2]} {g[3]}. {QUESTION_EN[p['question']]} "
    return body + INSTR_EN[p["instr"]]


def render_it(p: dict) -> str:
    g = p["groups"]
    if p["form"] == "plus":
        body = (f"Alice ha in totale {_it(g[0], g[1])} e {_it(g[2], g[3])}. Sua madre ha {g[4]} fratelli. Ha anche {_it(g[5], 'sister')} "
                f"che non ha figli e che ha in totale {g[6]} nipoti. Il padre di Alice ha {g[7]} sorelle. Ha anche un fratello che ha "
                f"in totale {g[8]} nipoti e che ha anche {_it(g[9], g[10])}. Quanti cugini ha la sorella di Alice? ")
    else:
        body = f"Alice ha {_it(g[0], g[1])} e ha anche {_it(g[2], g[3])}. {QUESTION_IT[p['question']]} "
    return body + INSTR_IT[p["instr"]]


def solve(p: dict) -> int:
    """The answer recomputed from the family structure, independently of the file's gold."""
    g = p["groups"]
    if p["form"] == "plus":
        a, b = int(g[0]), int(g[2])
        children = 1 + a + b  # Alice, her sisters, her brothers
        mother_side = int(g[6]) - children  # the childless aunt's nephews and nieces, minus Alice's family
        father_sisters_side = int(g[8]) - children  # the uncle's nephews and nieces, minus Alice's family
        return mother_side + father_sisters_side + int(g[9])
    counts = {g[1].rstrip("s"): int(g[0]), g[3].rstrip("s"): int(g[2])}
    return {"sisters_of_brother": counts["sister"] + 1, "siblings": counts["sister"] + counts["brother"],
            "brothers_of_sister": counts["brother"], "total_girls": counts["sister"] + 1}[p["question"]]


@register("aiw")
def build() -> Built:
    import json

    issues = Issues()
    prompts = {r["id"]: r for r in json.load(open(release_file(URL, SHA256), encoding="utf-8"))}
    items = {"it": [], "en": []}
    for pid, (set_, subset, var, ptype) in CORE.items():
        row = prompts[pid]
        parts = parse(row["prompt"])
        if render_en(parts) != row["prompt"].replace("’", "'"):
            raise AssertionError(f"prompt {pid}: the parse does not rebuild the English text")
        id_ = {"main": f"aiw-main-v{var}-{ptype}", "light": f"aiw-light-{subset.replace('_', '-')}-v{var}", "plus": f"aiw-plus-v{var}"}[set_]
        if solve(parts) != int(row["right_answer"]):
            issues.add("gold_differs_from_recomputed", f"file says {row['right_answer']}, recomputed {solve(parts)}", id_)
        meta = {"set": set_, "subset": subset, "variation": var, "prompt_type": ptype, "instruction": parts["instr"],
                "source_id": pid, "source_description": row.get("description"), "integer": True}
        for lang, text in (("en", row["prompt"]), ("it", render_it(parts))):
            items[lang].append(Item(id=id_, lang=lang, messages=user(text), answer=str(row["right_answer"]), scorer="exact_match",
                                    meta={**meta, "source_prompt": row["prompt"] if lang == "en" else text, "template": f"aiw-{parts['instr']}"}))
    return Built(
        items,
        issues,
        {
            "name": "Alice in Wonderland (AIW)",
            "source": f"github.com/LAION-AI/AIW@{COMMIT[:8]} (prompts/prompts.json, sha256 {SHA256[:12]})",
            "paper": "Nezhurina, Cipolina-Kun, Cherti, Jitsev, 2024, Alice in Wonderland: Simple Tasks Showing Complete Reasoning Breakdown in State-Of-the-Art Large Language Models (arXiv:2406.02061; TMLR)",
            "licence": "Apache 2.0 (code and prompts)",
            "scorer": "exact_match on the integer after the last answer marker ('### Answer:' / '### Risposta:', within 100 characters, next lines included), else a final \\boxed{n}; score.found_by records which",
            "notes": [
                "The paper's core sets, by the prompt ids of its supplementary tables: AIW variations 1-4 in three prompt types (STANDARD, THINKING, RESTRICTED; Tab. 2), the AIW Light controls (siblings, family, total girls; Tab. 3-5), and AIW+ variations 1-6 (Tab. 10). 30 prompts per language. The authors' file has 826 prompts, most of them exploratory variants not used for the paper's main results.",
                "English is the authors' text verbatim (curly apostrophes normalised). The main AIW THINKING prompts use the authors' 'V1' wording and the Light and AIW+ ones 'V2' ('think carefully step by step'), as in the paper.",
                "Italian (ours, native read pending): every English prompt is parsed into its numbers and parts, the parse must rebuild the English exactly, and the same parts are rendered in Italian, so items are parallel by id. 'fratelli' means both brothers and siblings in Italian: questions about brothers say 'fratelli maschi', about siblings 'fratelli e sorelle'. 'nephews and nieces' -> 'nipoti', 'sons' -> 'figli maschi'. The answer marker is '### Risposta:' in Italian.",
                "RESTRICTED forbids any text besides the answer line; for a reasoning model this constrains only the final answer, not the thinking block.",
                "The paper samples many times per prompt (60-100). Report the mean correct rate per variation and the spread across variations of the same problem, the paper's main signal (meta.variation, meta.subset, meta.prompt_type).",
                "Gold answers: all 30 recomputed from the family structure (a check independent of the file) and equal to the authors' answers.",
                "Caveat: the problem is famous since 2024 and likely in the training data of recent models; the Light controls help separate memorised answers from reasoning only partly.",
            ],
        },
    )
