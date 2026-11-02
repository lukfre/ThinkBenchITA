"""AlpacaEval 2-style pairwise judge for X-AlpacaEval, through an OpenAI-compatible endpoint.

Preference is read as AlpacaEval does (logprob_parser): P(id of the model output) among the two
ids "m"/"M", from the judge's top log-probabilities of its single output token. The model output
is placed first or second at random, seeded per item. Scale: AlpacaEval's 1..2, where 2 means
the model output (generator_2) is preferred over the reference (generator_1).
"""

import hashlib
import math
import os
import random
from concurrent.futures import ThreadPoolExecutor

import yaml

from . import prompts
from .schema import ROOT

PLACEHOLDER = "PLACEHOLDER"


def load_config(path: str | None = None) -> dict:
    return yaml.safe_load(open(path or ROOT / "config" / "judge.yaml", encoding="utf-8"))


def prompt_hash(lang: str) -> str:
    t = prompts.ALPACA_JUDGE[lang]
    return hashlib.sha256((t["system"] + "\x00" + t["user"]).encode("utf-8")).hexdigest()[:16]


def client_for(spec: dict):
    if PLACEHOLDER in spec["model"]:
        raise SystemExit(f"config/judge.yaml: set a real model name instead of {spec['model']!r}")
    key = os.environ.get(spec["api_key_env"])
    if not key:
        raise SystemExit(f"environment variable {spec['api_key_env']} is not set")
    from openai import OpenAI

    return OpenAI(base_url=spec["base_url"], api_key=key)


def model_first(item_id: str, seed: int) -> bool:
    """True when the model output is shown first ("m"). Depends on the item and the seed only."""
    return random.Random(f"{seed}:{item_id}").random() < 0.5


def judge_messages(lang: str, instruction: str, output_1: str, output_2: str) -> list[dict]:
    t = prompts.ALPACA_JUDGE[lang]
    user = t["user"].replace("{instruction}", instruction).replace("{output_1}", output_1).replace("{output_2}", output_2)
    return [{"role": "system", "content": t["system"]}, {"role": "user", "content": user}]


def p_first(top_logprobs: dict[str, float]) -> float | None:
    """P("m") / (P("m") + P("M")) from {token: logprob}; None if neither id is among the top tokens."""
    pm = sum(math.exp(lp) for tok, lp in top_logprobs.items() if tok.strip() == "m")
    pM = sum(math.exp(lp) for tok, lp in top_logprobs.items() if tok.strip() == "M")
    return pm / (pm + pM) if pm + pM > 0 else None


def preference(p_m: float | None, model_is_first: bool) -> float | None:
    """AlpacaEval scale: 1 = reference preferred, 2 = model preferred."""
    if p_m is None:
        return None
    p_model = p_m if model_is_first else 1 - p_m
    return 1 + p_model


def judge_one(client, spec: dict, messages: list[dict]) -> dict:
    response = client.chat.completions.create(
        model=spec["model"], messages=messages, temperature=spec["temperature"], max_tokens=spec["max_tokens"],
        logprobs=True, top_logprobs=spec.get("top_logprobs", 5),
    )
    choice = response.choices[0]
    top = {t.token: t.logprob for t in (choice.logprobs.content[0].top_logprobs if choice.logprobs and choice.logprobs.content else [])}
    return {"text": choice.message.content or "", "top_logprobs": top}


def chat(client, spec: dict, messages: list[dict]) -> str:
    response = client.chat.completions.create(model=spec["model"], messages=messages, temperature=spec["temperature"], max_tokens=spec["max_tokens"])
    return response.choices[0].message.content or ""


def map_parallel(fn, items: list, concurrency: int) -> list:
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        return list(pool.map(fn, items))


def length_controlled(annotations: list[dict]) -> dict:
    """AlpacaEval 2's length-controlled win rate, via the alpaca_eval package.

    `annotations`: one dict per item with instruction, output_1 (reference), output_2 (model),
    generator_1, generator_2, preference (1..2) and index (AlpacaEval instruction index, 0..804).

    Returns the standard LC (length_controlled_v1, AlpacaEval 2's headline) and the unregularised
    variant (length_controlled_noreg). v1 regularises the length coefficient towards one fitted on
    AlpacaEval's own length-gamed ENGLISH baselines: with outputs systematically longer than the
    reference it lowers the win rate even when the verdicts ignore length (synthetic check, README).
    Both use English-derived instruction difficulties: NOT validated for Italian yet.
    """
    import pandas as pd
    from alpaca_eval.metrics.glm_winrate import get_length_controlled_winrate

    out = {}
    for name in ("length_controlled_v1", "length_controlled_noreg"):
        r = get_length_controlled_winrate(pd.DataFrame(annotations), glm_name=name, save_weights_dir=None, is_warn_extreme_changes=False)
        out[name] = {"win_rate": r["length_controlled_winrate"], "standard_error": r["lc_standard_error"]}
    out["raw_win_rate"] = r["win_rate"]
    return out
