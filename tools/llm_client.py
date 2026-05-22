from __future__ import annotations

import os
import time
import threading
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class LLMUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0


@dataclass
class LLMResponse:
    text: str
    usage: LLMUsage = field(default_factory=LLMUsage)


class LLMClient:
    def __init__(self, model: str, fast_model: Optional[str] = None, max_retries: int = 3, timeout: int = 120):
        self.model = model
        self.fast_model = fast_model or model
        self.max_retries = max_retries
        self.timeout = timeout

    def complete(self, messages: list, max_tokens: int = 1024, temperature: float = 0.1, use_fast: bool = False) -> LLMResponse:
        try:
            from litellm import completion
        except ImportError:
            raise RuntimeError("litellm not installed. Run: pip install litellm")

        model = self.fast_model if use_fast else self.model

        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                response = completion(
                    model=model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    timeout=self.timeout,
                )
                text = response.choices[0].message.content
                usage_obj = getattr(response, "usage", None)
                prompt_tokens = usage_obj.prompt_tokens if usage_obj else 0
                completion_tokens = usage_obj.completion_tokens if usage_obj else 0
                usage = LLMUsage(
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                )
                accumulate_usage(prompt_tokens, completion_tokens)
                return LLMResponse(text=text, usage=usage)
            except Exception as e:
                last_error = e
                err_str = str(e)
                is_retryable = attempt < self.max_retries and any(kw in err_str for kw in [
                    "RateLimitError", "rate_limit", "rate limit",
                    "APIConnectionError", "ConnectionError", "connection",
                    "APIStatusError", "ServiceUnavailable",
                    "429", "502", "503", "500",
                    "timeout", "timed out", "overloaded",
                ])
                if is_retryable:
                    delay = 2 ** attempt
                    print(f"  [retry] attempt {attempt + 1}/{self.max_retries}, waiting {delay}s: {err_str[:100]}")
                    time.sleep(delay)
                    continue
                raise

        raise RuntimeError(f"LLM call failed after {self.max_retries + 1} attempts") from last_error


_client: Optional[LLMClient] = None
_lock = threading.Lock()

# Global token usage accumulator (thread-safe)
_usage_lock = threading.Lock()
_total_prompt_tokens: int = 0
_total_completion_tokens: int = 0


def accumulate_usage(prompt_tokens: int, completion_tokens: int):
    global _total_prompt_tokens, _total_completion_tokens
    with _usage_lock:
        _total_prompt_tokens += prompt_tokens
        _total_completion_tokens += completion_tokens


def get_total_usage() -> dict:
    global _total_prompt_tokens, _total_completion_tokens
    with _usage_lock:
        return {
            "total_prompt_tokens": _total_prompt_tokens,
            "total_completion_tokens": _total_completion_tokens,
            "total_tokens": _total_prompt_tokens + _total_completion_tokens,
        }


def init_client(model: str | None = None, fast_model: str | None = None, **kwargs):
    global _client
    with _lock:
        _client = LLMClient(
            model=model or os.environ.get("LLM_MODEL", "anthropic/claude-sonnet-4-6"),
            fast_model=fast_model or os.environ.get("LLM_MODEL_FAST", "anthropic/claude-sonnet-4-6"),
            **kwargs,
        )


def get_client() -> LLMClient:
    if _client is None:
        raise RuntimeError("LLMClient not initialized. Call init_client() first.")
    return _client
