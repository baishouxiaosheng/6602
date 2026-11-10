"""One client for every OpenAI-compatible endpoint (OpenRouter, DeepSeek, GLM, Gemini)."""

from __future__ import annotations

import logging
from typing import TypeVar

from pydantic import BaseModel

from ..contracts.errors import ConfigError, LLMOutputInvalid, RateLimited, UpstreamError
from ..retry import retry_call
from .base import schema_instruction, validate_json_text

log = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


class OpenAICompatLLM:
    """Implements contracts.LLMClient.

    Two independent bounded loops:
    * transport: UpstreamError / RateLimited are retried with backoff (retry_call);
    * validation: an answer that fails the schema is sent back with the error text,
      at most ``max_retries`` times, then LLMOutputInvalid is raised.
    Counters (calls / retries) are public so callers can store them in LLMUsage.
    """

    def __init__(
        self,
        *,
        provider: str,
        model: str,
        api_key: str,
        base_url: str,
        max_retries: int = 2,
        timeout_s: float = 60.0,
        json_mode: bool = True,
    ) -> None:
        if not api_key:
            raise ConfigError(f"LLM_API_KEY is empty for provider {provider!r}")
        if not model:
            raise ConfigError(f"LLM_MODEL is empty for provider {provider!r}")
        from openai import OpenAI  # imported lazily so tests never need the SDK

        self.provider = provider
        self.model = model
        self.max_retries = max_retries
        self.json_mode = json_mode
        self.calls = 0
        self.retries = 0
        self._client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout_s, max_retries=0)

    def _chat(self, messages: list[dict[str, str]], temperature: float) -> str:
        import openai

        kwargs: dict = {"model": self.model, "messages": messages, "temperature": temperature}
        if self.json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        self.calls += 1
        try:
            resp = self._client.chat.completions.create(**kwargs)
        except openai.RateLimitError as err:
            raise RateLimited(f"{self.provider} rate limit: {err}", model=self.model) from err
        except (
            openai.APIConnectionError,
            openai.APITimeoutError,
            openai.InternalServerError,
        ) as err:
            raise UpstreamError(f"{self.provider} unavailable: {err}", model=self.model) from err
        except openai.APIStatusError as err:  # 4xx: bad key, unknown model, bad request
            raise ConfigError(
                f"{self.provider} rejected the request ({err.status_code}): {err.message}",
                model=self.model,
            ) from err
        return (resp.choices[0].message.content or "") if resp.choices else ""

    def complete_json(
        self, *, system: str, user: str, schema: type[T], temperature: float = 0.2
    ) -> T:
        messages = [
            {"role": "system", "content": system + "\n\n" + schema_instruction(schema)},
            {"role": "user", "content": user},
        ]
        raw = ""
        for attempt in range(self.max_retries + 1):
            raw = retry_call(lambda: self._chat(messages, temperature), attempts=3)  # noqa: B023
            try:
                return validate_json_text(raw, schema)
            except ValueError as err:
                log.warning("llm answer invalid (attempt %d): %s", attempt + 1, err)
                if attempt == self.max_retries:
                    break
                self.retries += 1
                messages = messages[:2] + [
                    {"role": "assistant", "content": raw[:4000]},
                    {
                        "role": "user",
                        "content": f"Your answer was rejected: {err}. "
                        "Send the corrected json object only.",
                    },
                ]
        raise LLMOutputInvalid(
            "model output never matched the schema",
            provider=self.provider,
            model=self.model,
            raw_head=raw[:200],
        )
