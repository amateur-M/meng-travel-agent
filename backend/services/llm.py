"""LLM Service — multi-provider ChatOpenAI wrapper with mock fallback.

Supported providers (all OpenAI-compatible API):
  - openai    (GPT-4o, default)
  - deepseek  (DeepSeek Chat)
  - qwen      (Tongyi Qianwen / 通义千问)
  - kimi      (Moonshot / 月之暗面)

Each provider is lazily initialised with its own ChatOpenAI client.
When the API key for the selected provider is absent, the service
returns the supplied mock_response so the graph remains testable.
"""

import json
from typing import Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from config.settings import settings

# ---------------------------------------------------------------------------
# Per-provider client cache
# ---------------------------------------------------------------------------

_llm_cache: dict[str, Optional[ChatOpenAI]] = {}

_PROVIDER_CONFIG = {
    "openai": {
        "api_key_attr": "openai_api_key",
        "model_attr": "openai_model",
        "display_name": "OpenAI GPT-4o",
    },
    "deepseek": {
        "api_key_attr": "deepseek_api_key",
        "model_attr": "deepseek_model",
        "base_url_attr": "deepseek_base_url",
        "display_name": "DeepSeek",
    },
    "qwen": {
        "api_key_attr": "qwen_api_key",
        "model_attr": "qwen_model",
        "base_url_attr": "qwen_base_url",
        "display_name": "Qwen (通义千问)",
    },
    "kimi": {
        "api_key_attr": "kimi_api_key",
        "model_attr": "kimi_model",
        "base_url_attr": "kimi_base_url",
        "display_name": "Kimi (月之暗面)",
    },
}


def _get_llm(provider: str = "openai") -> Optional[ChatOpenAI]:
    """Lazy-init the ChatOpenAI client for *provider*.

    Returns None when the provider's API key is not configured, so
    callers can fall back to their mock response.
    """
    if provider in _llm_cache:
        return _llm_cache[provider]

    cfg = _PROVIDER_CONFIG.get(provider)
    if cfg is None:
        _llm_cache[provider] = None
        return None

    api_key = getattr(settings, cfg["api_key_attr"], "")
    if not api_key:
        _llm_cache[provider] = None
        return None

    model = getattr(settings, cfg["model_attr"], "gpt-4o")
    kwargs: dict = {
        "model": model,
        "api_key": api_key,
        "temperature": 0.7,
        "max_tokens": 4096,
    }

    base_url_attr = cfg.get("base_url_attr")
    if base_url_attr:
        kwargs["base_url"] = getattr(settings, base_url_attr, "")

    client = ChatOpenAI(**kwargs)
    _llm_cache[provider] = client
    return client


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_json(content: str) -> str:
    """Strip markdown code fences from LLM output."""
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0]
    elif "```" in content:
        content = content.split("```")[1].split("```")[0]
    return content.strip()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def call_llm(
    system_prompt: str,
    user_prompt: str,
    mock_response: dict | None = None,
    provider: str | None = None,
) -> dict:
    """Call the LLM with system + user prompts.

    Args:
        system_prompt: System-level instructions for the LLM.
        user_prompt:   The user message / query.
        mock_response: Fallback dict returned when the provider's API key
                       is unavailable or the call fails.  When None,
                       returns {"error": "..."} on failure.
        provider:      One of ``"openai"``, ``"deepseek"``, ``"qwen"``,
                       ``"kimi"``.  Defaults to ``DEFAULT_LLM_PROVIDER``
                       from settings (which itself defaults to ``"openai"``).

    Returns:
        A dict parsed from the LLM's JSON response, or *mock_response*.
    """
    provider = provider or settings.default_llm_provider
    llm = _get_llm(provider)

    if llm is None:
        return mock_response or {"error": f"API key not configured for provider '{provider}'"}

    try:
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]
        response = llm.invoke(messages)
        content = response.content if hasattr(response, "content") else str(response)
        return json.loads(_extract_json(content))
    except Exception as e:
        if mock_response is not None:
            return mock_response
        raise
