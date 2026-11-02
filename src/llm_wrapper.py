from dataclasses import dataclass
from typing import List, Optional

from vllm import LLM, SamplingParams

MODELS = {
    "smol2": "HuggingFaceTB/SmolLM2-1.7B-Instruct",  # for quick testing
    "llama3": "meta-llama/Llama-3.1-8B-Instruct",
    "qwen3": "Qwen/Qwen3-8B",
    # "qwen1M": "Qwen/Qwen2.5-7B-Instruct-1M",
}


@dataclass
class vLLMReq:
    """Represents a single generation request"""

    request_id: str
    messages: list[dict]
    question: str
    references: Optional[List[str]]
    metadata: Optional[dict]

    def to_row(self, include_prompt_text: bool = False) -> dict:
        """Flatten the request into a dict suitable for TSV/CSV rows."""
        row = {
            "request_id": self.request_id,
            "question": self.question,
            "references": self.references,
        }
        if include_prompt_text:
            row["messages"] = self.messages
        if self.metadata:
            row.update(self.metadata)
        return row


@dataclass
class vLLMRes(vLLMReq):
    """Store generation results, extending vLLMReq with model outputs"""

    llm_response: str
    num_output_tokens: int  # Tokens in generated response
    reasoning_text: Optional[str] = None  # <think>...</think> content, only
    # populated when batch_generate's strip_thinking split one off (see
    # _get_response_text) -- None for non-thinking-mode requests, and for
    # thinking-mode requests whose output had no `</think>` tag at all.

    def to_row(self, include_prompt_text: bool = False) -> dict:
        """Flatten the result into a dict suitable for TSV/CSV rows.

        Extends the base row with model outputs.
        """
        base = super().to_row(include_prompt_text=include_prompt_text)
        base.update(
            {
                "response": self.llm_response,
                "num_output_tokens": self.num_output_tokens,
            }
        )
        return base


class vLLMReader:
    """Enhanced vLLM wrapper for RAG tasks with efficient batching"""

    def __init__(
        self,
        model_path: str,
        max_model_len: int = 8192,
        tensor_parallel_size: int = 1,
        temperature: float = 0.1,
        max_tokens: int = 512,
        seed: int = 42,
        system_prompt: str = "",
        user_prompt_template: str = "",
        assistant_prompt: str = "",
        top_p: float = 1.0,
        top_k: int = -1,
        presence_penalty: float = 0.0,
        repetition_penalty: float = 1.0,
        enable_prefix_caching: bool = False,
        rope_scaling: dict | None = None,
        stop: list[str] | None = None,
        kv_cache_dtype: str = "auto",
        hf_overrides: dict | None = None,
        gpu_memory_utilization: float = 0.9,  # vLLM's own default; raise it
        # for a model whose weights leave too little room for the KV cache
    ):
        self.model_path = model_path
        # rope_scaling is the long-standing special case; hf_overrides is the
        # general escape hatch for a checkpoint whose config.json vLLM reads
        # wrongly. Both land in the same vLLM kwarg, rope_scaling last so an
        # explicit rope_scaling= still wins if someone passes both.
        if callable(hf_overrides):
            # vLLM also accepts a callable that mutates the resolved config --
            # the only way to reach a NESTED config (e.g. a multimodal
            # checkpoint's text_config), which a dict of kwargs cannot touch.
            if rope_scaling:
                raise ValueError(
                    "pass rope_scaling inside the hf_overrides callable when "
                    "using the callable form; vLLM takes one or the other"
                )
            overrides = hf_overrides
        else:
            overrides = {**(hf_overrides or {})}
            if rope_scaling:
                overrides["rope_scaling"] = rope_scaling
        self.model = LLM(
            model=model_path,
            max_model_len=max_model_len,
            tensor_parallel_size=tensor_parallel_size,
            enable_prefix_caching=enable_prefix_caching,
            kv_cache_dtype=kv_cache_dtype,
            gpu_memory_utilization=gpu_memory_utilization,
            **({"hf_overrides": overrides} if overrides else {}),
        )
        self.tokenizer = self.model.get_tokenizer()
        self.sampling_params = SamplingParams(
            temperature=temperature,
            max_tokens=max_tokens,
            seed=seed,
            top_p=top_p,
            top_k=top_k,
            presence_penalty=presence_penalty,
            repetition_penalty=repetition_penalty,
            stop=stop,
            # how to check predefined parameters like top_p, top_k when not set?
        )
        self.system_prompt = system_prompt
        self.user_prompt_template = user_prompt_template
        self.assistant_prompt = assistant_prompt
        self.max_model_len = max_model_len

    def _build_messages(
        self, formatted_content: str, add_assistant_prompt: bool = True
    ) -> str:
        """
        Build final prompt with chat template.

        Args:
            formatted_content: Already formatted user message content
            add_assistant_prompt: Whether to append assistant prompt
        """
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": formatted_content},
            {"role": "assistant", "content": self.assistant_prompt},
        ]

        return messages

    def _get_response_text(
        self, output, strip_thinking: bool = False, index: int = 0
    ) -> tuple[str, str | None]:
        """Extract (response_text, reasoning_text) from vLLM output object.

        strip_thinking=True splits off everything up to and including the
        last `</think>` tag into reasoning_text (whatever preceded it, minus
        a leading "<think>" tag if the raw output happened to include one --
        usually it won't, since the chat template injects that opening tag
        into the PROMPT, not the generated tokens) and returns only what
        follows as response_text -- used when the request's messages end on
        a "role": "user" turn (no prefilled assistant turn) so the model
        reasons freely before answering; see batch_generate's
        continue_final_message param. A response with no `</think>` tag
        (e.g. a hybrid-checkpoint response that happened not to think, or a
        checkpoint with no thinking mode at all) returns (text, None)
        unchanged. strip_thinking=False always returns (text, None).

        `index` selects which of a request's completions to read -- 0 for
        every single-sample call (SamplingParams.n == 1 produces exactly one
        entry); batch_sample below passes 0..n-1 to read all of them."""
        text = output.outputs[index].text.strip()
        reasoning_text = None
        if strip_thinking and "</think>" in text:
            reasoning_text, text = text.rsplit("</think>", 1)
            reasoning_text = reasoning_text.split("<think>", 1)[-1].strip()
            text = text.strip()
        return text, reasoning_text

    def batch_generate(
        self,
        requests: list[vLLMReq],
        sampling_params: SamplingParams | None = None,
        continue_final_message: bool = True,
    ) -> list[vLLMRes]:
        """
        Execute batch generation on prepared requests.

        Args:
            requests: List of vLLMReq objects
            sampling_params: Optional custom sampling params (uses default if None)
            continue_final_message: True (default) treats each request's last
                message as a prefilled assistant turn to continue from --
                the non-thinking-mode trick used everywhere else in this repo
                (see e.g. generate_oracle_proxy_context.py's module docstring).
                False instead asks the model for a fresh assistant turn
                (add_generation_prompt=True) -- pass this when `requests`'
                messages end on a "user" turn instead, to let a
                thinking-capable checkpoint reason in a <think> block before
                its actual output (then stripped via _get_response_text).

        Returns:
            List of vLLMRes objects
        """
        if not requests:
            return []

        # Extract prompts
        prompts = [req.messages for req in requests]

        # Generate
        params = sampling_params or self.sampling_params
        outputs = self.model.chat(
            prompts,
            params,
            add_generation_prompt=not continue_final_message,
            continue_final_message=continue_final_message,
        )

        # Convert to vLLMRes objects
        results: list[vLLMRes] = []
        for req, output in zip(requests, outputs):
            response_text, reasoning_text = self._get_response_text(
                output, strip_thinking=not continue_final_message
            )

            # Add output token count to metadata
            output_tokens = len(self.tokenizer.encode(response_text))

            result = vLLMRes(
                **vars(req),
                llm_response=response_text,
                num_output_tokens=output_tokens,
                reasoning_text=reasoning_text,
            )
            results.append(result)

        return results

    def batch_sample(
        self,
        requests: list[vLLMReq],
        n: int,
        sampling_params: SamplingParams | None = None,
        continue_final_message: bool = True,
    ) -> list[vLLMRes]:
        """batch_generate, but drawing `n` independent samples per request --
        the GRPO-style rollout group. Returns ONE flattened list of
        n * len(requests) results, each carrying its 0-based "rollout_index"
        in metadata and a "<request_id>#<k>" request_id, so a caller can write
        them straight to JSONL and regroup by request_id later.

        Its own method rather than an `n=` argument on batch_generate because
        the return shape genuinely differs: batch_generate reads outputs[0]
        and promises exactly one result per request, which is what all of its
        existing callers destructure. Handing that method SamplingParams(n>1)
        would silently DISCARD n-1 completions instead of failing, so the
        multi-sample path is separated rather than bolted on.

        The samples must come from ONE request with n=k, never k copies of the
        same request: SamplingParams carries a fixed `seed`, so k duplicated
        requests return k IDENTICAL strings. vLLM decorrelates the n samples
        drawn within a single request, which is the whole point here.
        """
        if n < 1:
            raise ValueError(f"n must be >= 1, got {n}")
        if not requests:
            return []

        params = sampling_params or self.sampling_params
        if params.n != n:
            # Copy, never mutate: `params` defaults to self.sampling_params,
            # which is shared with every other call on this reader.
            params = params.clone()
            params.n = n

        outputs = self.model.chat(
            [req.messages for req in requests],
            params,
            add_generation_prompt=not continue_final_message,
            continue_final_message=continue_final_message,
        )

        results: list[vLLMRes] = []
        for req, output in zip(requests, outputs):
            for k in range(len(output.outputs)):
                response_text, reasoning_text = self._get_response_text(
                    output, strip_thinking=not continue_final_message, index=k
                )
                fields = vars(req).copy()
                fields["request_id"] = f"{req.request_id}#{k}"
                fields["metadata"] = {**(req.metadata or {}), "rollout_index": k}
                results.append(
                    vLLMRes(
                        **fields,
                        llm_response=response_text,
                        num_output_tokens=len(self.tokenizer.encode(response_text)),
                        reasoning_text=reasoning_text,
                    )
                )
        return results
