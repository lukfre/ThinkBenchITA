"""Generation with vLLM: chat template, n samples per prompt, thinking / answer split.

Builds on src/llm_wrapper.vLLMReader (model loading, tokenizer). The wrapper's
batch_sample keeps neither the finish reason nor the token counts, which the
trace metrics need, and returns only when the whole batch is done; so
`EvalReader.stream` drives vLLM's engine itself and yields each prompt's samples
as soon as they are finished.
"""

import time
from collections.abc import Iterator
from dataclasses import dataclass

from vllm.sampling_params import RequestOutputKind

from .llm_wrapper import vLLMReader
from .split import split_completion


@dataclass
class Sample:
    completion: str  # full output; starts with the opening delimiter when the model thinks
    thinking: str
    answer: str  # the only part that is scored
    think_closed: bool
    finish_reason: str | None
    prompt_tokens: int
    completion_tokens: int
    thinking_tokens: int
    answer_tokens: int


class EvalReader(vLLMReader):
    def __init__(self, model_path: str, think_delims: list[str], chat_template_kwargs: dict | None = None, **kwargs):
        super().__init__(model_path, **kwargs)
        self.think_delims = think_delims
        self._batch = 0  # request-id prefix of each stream() call
        self.chat_template_kwargs = chat_template_kwargs or {}
        # Some templates (e.g. DeepSeek-R1) open the thinking block in the PROMPT, so the
        # generated text starts inside it with no opening tag. Detect that once and put
        # the tag back in front of every completion, so the stored trace is well formed.
        probe = self.tokenizer.apply_chat_template(
            [{"role": "user", "content": "x"}], tokenize=False, add_generation_prompt=True, **self.chat_template_kwargs
        )
        self.think_open_in_prompt = probe.rstrip().endswith(think_delims[0])
        # Delimiters the model never writes would leave every output "unclosed": stop before generating.
        template = self.tokenizer.chat_template or ""
        template = " ".join(template.values()) if isinstance(template, dict) else template
        vocab = self.tokenizer.get_vocab()
        missing = [d for d in think_delims if d not in template and d not in vocab]
        if missing:
            raise ValueError(f"think_delims {missing} appear neither in the chat template nor in the vocabulary of {model_path}")

    def _count(self, text: str) -> int:
        return len(self.tokenizer.encode(text, add_special_tokens=False)) if text else 0

    def sample(self, messages: list[list[dict]], n: int, **sampling) -> list[list[Sample]]:
        """`n` samples for each chat prompt, in prompt order (see `stream`)."""
        results = [None] * len(messages)
        for index, samples in self.stream(messages, n, **sampling):
            results[index] = samples
        return results

    def stream(self, messages: list[list[dict]], n: int, **sampling) -> Iterator[tuple[int, list[Sample]]]:
        """(prompt index, its `n` samples) as each prompt finishes, so callers can save outputs
        as they come instead of after the whole batch. The `n` samples are drawn within one
        request (one seed, n decorrelated samples), never as n copies of the request."""
        params = self.sampling_params.clone()
        for key, value in {**sampling, "n": n}.items():
            setattr(params, key, value)
        params.output_kind = RequestOutputKind.FINAL_ONLY  # one output per request, with all n samples
        engine = self.model.llm_engine
        for i, m in enumerate(messages):
            # Render the chat template ourselves and hand vLLM the token ids: the same text
            # LLM.chat would build, but it lets chat_template_kwargs through (LLM.chat does
            # not take them in every vLLM version) and cannot add a second BOS token.
            ids = self.tokenizer.apply_chat_template(m, tokenize=True, add_generation_prompt=True, **self.chat_template_kwargs)
            engine.add_request(f"{self._batch}-{i}", {"prompt_token_ids": ids}, params)
        prefix, self._batch = f"{self._batch}-", self._batch + 1
        done, start, last_report = 0, time.time(), time.time()
        while engine.has_unfinished_requests():
            for output in engine.step():
                if not output.finished or not output.request_id.startswith(prefix):
                    continue
                done += 1
                yield int(output.request_id[len(prefix):]), [self._sample(output, choice) for choice in output.outputs]
                if time.time() - last_report > 60 or done == len(messages):
                    print(f"generated {done}/{len(messages)} prompts in {(time.time() - start) / 60:.1f} min", flush=True)
                    last_report = time.time()

    def _sample(self, output, choice) -> Sample:
        text = choice.text
        if self.think_open_in_prompt and self.think_delims[0] not in text:
            text = self.think_delims[0] + "\n" + text
        thinking, answer, closed = split_completion(text, self.think_delims)
        return Sample(
            completion=text,
            thinking=thinking,
            answer=answer,
            think_closed=closed,
            finish_reason=choice.finish_reason,
            prompt_tokens=len(output.prompt_token_ids or []),
            completion_tokens=len(choice.token_ids),
            thinking_tokens=self._count(thinking),
            answer_tokens=self._count(answer),
        )
