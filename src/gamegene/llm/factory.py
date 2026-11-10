"""Provider presets. Adding a provider = one line here; nothing else changes."""

from __future__ import annotations

from ..config import Settings
from ..contracts.errors import ConfigError
from ..contracts.protocols import LLMClient
from .fake import FakeLLM
from .openai_compat import OpenAICompatLLM

# provider -> (base_url, supports response_format json_object)
PROVIDERS: dict[str, tuple[str, bool]] = {
    "openrouter": ("https://openrouter.ai/api/v1", True),  # course key, approved open models
    "deepseek": ("https://api.deepseek.com", True),
    "glm": ("https://open.bigmodel.cn/api/paas/v4/", True),
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai/", True),
}


def make_llm(settings: Settings) -> LLMClient:
    provider = settings.llm_provider
    if provider == "fake":
        return FakeLLM()
    if provider == "custom":
        if not settings.llm_base_url:
            raise ConfigError("LLM_PROVIDER=custom needs LLM_BASE_URL")
        base_url, json_mode = settings.llm_base_url, True
    elif provider in PROVIDERS:
        base_url, json_mode = PROVIDERS[provider]
        base_url = settings.llm_base_url or base_url
    else:
        raise ConfigError(f"unknown LLM_PROVIDER {provider!r}; use one of {sorted(PROVIDERS)}")
    return OpenAICompatLLM(
        provider=provider,
        model=settings.llm_model,
        api_key=settings.llm_api_key,
        base_url=base_url,
        max_retries=settings.llm_max_retries,
        timeout_s=settings.llm_timeout_s,
        json_mode=json_mode,
    )
