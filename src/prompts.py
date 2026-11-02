"""Answer-format instructions appended to the source text, one per scorer and language.

The sources (except PolyMath, which ships its own) do not say how the final
answer must be formatted, and the scorers need a fixed format. Each template is
recorded by id in `meta.template`, and the source text is appended to verbatim.
Changing a string here changes the benchmark: bump the id.

The Italian texts we wrote live in src/italian.yaml (one file, for native review and editing);
this module only adds the whitespace that joins them to the rest of the prompt.
"""

from pathlib import Path

import yaml

_IT = yaml.safe_load((Path(__file__).parent / "italian.yaml").read_text(encoding="utf-8"))


def italian(key: str) -> str:
    """An Italian text from src/italian.yaml."""
    return _IT[key]["it"]


# PolyMath's official suffixes, from QwenLM/PolyMath instruction.py (query_dic).
# The source strings are Python literals with `\{\}`, i.e. the model is shown
# `$\boxed\{\}$`; kept as shipped.
POLYMATH = {
    "en": "Note: Please put the final answer in the $\\boxed\\{\\}$.",
    "it": "Nota: Per favore, metti la risposta finale nel $\\boxed\\{\\}$.",
}


# MathArena's AIME instruction (eth-sri/matharena, configs/competitions/aime/aime_2025.yaml),
# placed BEFORE the problem as MathArena does: "{instruction}\n\n{problem}". Template id:
# matharena-aime-v1. MathArena has no Italian version: the Italian line is our translation.
MATHARENA_AIME = {
    "en": "Put your final answer within \\boxed{}.\nThe answer is an integer between 0 and 999 inclusive.",
    "it": italian("aime"),
}

# MATH-500, the de facto prompt for reasoning models (Qwen2.5-Math, DeepSeek-R1; MCLM's code
# for several models): the problem, then this line. Template id: math-standard-v1. Italian ours.
MATH_STANDARD = {
    "en": "Please reason step by step, and put your final answer within \\boxed{}.",
    "it": italian("math100"),
}
MCQ = {  # template id: mcq-v1
    "en": "Answer with the letter of the correct option, in the format \"Answer: X\".",
    "it": italian("invalsi_mcq"),
}

# GPQA, Olmo 3 format (OLMES task "gpqa::olmo3:adapt", oe_eval/configs/tasks.py). The user
# message is DESCRIPTION + "Question: {q}\nChoices:\n (A) ...\n" + FINAL, as OLMES builds it.
# Template id: gpqa-olmo3-v1. The Italian strings are our translation.
GPQA_OLMO3 = {
    "en": {
        "description": 'Answer the following multiple-choice question by giving the correct answer letter in parentheses. Provide CONCISE reasoning for the answer, and make sure to finish the response with "Therefore, the answer is (ANSWER_LETTER)" where (ANSWER_LETTER) is one of (A), (B), (C), (D).\n\n',
        "question": "Question: ",
        "choices": "\nChoices:\n",
        "final": '\n\nAnswer the above question and REMEMBER to finish your response with the exact phrase "Therefore, the answer is (ANSWER_LETTER)" where (ANSWER_LETTER) is one of (A), (B), (C), (D).',
    },
    "it": {
        "description": italian("gpqa_description") + "\n\n",
        "question": italian("gpqa_question") + " ",
        "choices": "\n" + italian("gpqa_choices") + "\n",
        "final": "\n\n" + italian("gpqa_final"),
    },
}

# GPQA, OpenAI simple-evals format (QUERY_TEMPLATE_MULTICHOICE), the one most reasoning-model
# reports use. Not the default; kept so the alternative is one switch away (loaders/gpqa.py,
# TEMPLATE). Template id: gpqa-simple-evals-v1. The Italian is our translation.
GPQA_SIMPLE_EVALS = {
    "en": "Answer the following multiple choice question. The last line of your response should be of the following format: 'Answer: $LETTER' (without quotes) where LETTER is one of ABCD. Think step by step before answering.\n\n{question}\n\nA) {A}\nB) {B}\nC) {C}\nD) {D}",
    "it": italian("gpqa_simple_evals"),
}

TRUE_FALSE_IT = italian("invalsi_true_false")  # tf-v1
EXACT_IT = italian("invalsi_exact")  # exact-v1


# EvalPlus's own chat instruction (evalplus/codegen.py, instruction_prefix; provider/utility.py,
# make_raw_chat_prompt): instruction, then the task prompt in a ``` block. The task prompt is
# EvalPlus's docstring: task text + one assert. EvalPlus also prefills the assistant turn
# ("Below is a Python script ..."); we do not, so the model can think first. The Italian is ours.
# Template id: evalplus-instruct-v1.
EVALPLUS = {
    "en": "Please provide a self-contained Python script that solves the following problem in a markdown code block:",
    "it": italian("evalplus"),
}


def evalplus_prompt(lang: str, task_prompt: str) -> str:
    return f"{EVALPLUS[lang]}\n```\n{task_prompt.strip()}\n```\n"


# LiveCodeBench's own prompt (lcb_runner/prompts/code_generation.py), as OLMES builds it:
# a system message, then "### Question / ### Format / ### Answer". Template id: lcb-official.
# The Italian strings are our translation (the problem statement is translated by the
# translation pipeline; code blocks, sample inputs and outputs stay as they are).
LCB = {
    "en": {
        "system": "You are an expert Python programmer. You will be given a question (problem specification) and will generate a correct Python program that matches the specification and passes all tests.",
        "starter": "You will use the following starter code to write the solution to the problem and enclose your code within delimiters.\n```python\n{starter}\n```",
        "stdin": "Read the inputs from stdin solve the problem and write the answer to stdout (do not directly test on the sample inputs). Enclose your code within delimiters as follows. Ensure that when the python program runs, it reads the inputs, runs the algorithm and writes output to STDOUT.\n```python\n# YOUR CODE HERE\n```",
        "user": "### Question:\n{question}\n\n### Format: {format}\n### Answer: (use the provided format with backticks)\n\n",
    },
    "it": {
        "system": italian("lcb_system"),
        "starter": italian("lcb_starter"),
        "stdin": italian("lcb_stdin"),
        "user": italian("lcb_user") + "\n\n",
    },
}


def lcb_messages(lang: str, question: str, starter: str) -> list[dict]:
    t = LCB[lang]
    fmt = t["starter"].format(starter=starter) if starter.strip() else t["stdin"]
    return [{"role": "system", "content": t["system"]}, {"role": "user", "content": t["user"].format(question=question, format=fmt)}]


def with_suffix(text: str, suffix: str) -> str:
    return f"{text}\n\n{suffix}"


# AlpacaEval 2 judge prompt (alpaca_eval evaluators_configs/alpaca_eval_clf_gpt4_turbo/
# alpaca_eval_clf.txt, commit cd543a14), verbatim. The judge answers with one id: "m" (first
# output) or "M" (second). The Italian is our translation, used for Italian runs; the ids stay m/M.
ALPACA_JUDGE = {
    "en": {
        "system": "You are a highly efficient assistant, who evaluates and selects the best large language model (LLMs) based on the quality of their responses to a given instruction. This process will be used to create a leaderboard reflecting the most accurate and human-preferred answers.",
        "user": '''I require a leaderboard for various large language models. I'll provide you with prompts given to these models and their corresponding outputs. Your task is to assess these responses, and select the model that produces the best output from a human perspective.

## Instruction

{
    "instruction": """{instruction}""",
}

## Model Outputs

Here are the unordered outputs from the models. Each output is associated with a specific model, identified by a unique model identifier.

{
    {
        "model_identifier": "m",
        "output": """{output_1}"""
    },
    {
        "model_identifier": "M",
        "output": """{output_2}"""
    }
}

## Task

Evaluate the models based on the quality and relevance of their outputs, and select the model that generated the best output. Answer by providing the model identifier of the best model. We will use your output as the name of the best model, so make sure your output only contains one of the following model identifiers and nothing else (no quotes, no spaces, no new lines, ...): m or M.

## Best Model Identifier''',
    },
    "it": {"system": italian("alpaca_judge_system"), "user": italian("alpaca_judge_user")},
}
