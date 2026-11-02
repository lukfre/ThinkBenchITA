"""Thinking / final-answer split (kept free of vLLM imports so scoring runs without a GPU)."""


def split_completion(completion: str, delims: list[str]) -> tuple[str, str, bool]:
    """(thinking, answer, think_closed). Same rules as trace_criteria.io.split_completion:
    an unclosed block is all thinking (so a truncated trace has an empty answer
    and scores as wrong); with no delimiters at all everything is answer."""
    open_d, close_d = delims
    start = completion.find(open_d)
    think_start = start + len(open_d) if start != -1 else 0
    end = completion.find(close_d, think_start)
    if end != -1:
        return completion[think_start:end].strip(), completion[end + len(close_d):].strip(), True
    if start != -1:
        return completion[think_start:].strip(), "", False
    return "", completion.strip(), False
