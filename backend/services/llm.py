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
import logging
from typing import Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from config.settings import settings

logger = logging.getLogger("coupletrip")

# L0 working memory: the caller decides how many turns to pass; each individual
# turn is truncated so one pasted itinerary cannot blow up the context window.
MAX_HISTORY_CONTENT_CHARS = 2000

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
        # Tidy/上线前: prevent upstream hangs from blocking the whole request
        "request_timeout": 60,
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


def _as_text(response) -> str:
    """Coerce a LangChain response into plain text (some providers return lists)."""
    content = response.content if hasattr(response, "content") else str(response)
    return content if isinstance(content, str) else str(content)


def _build_messages(
    system_prompt: str,
    user_prompt: str,
    history: Optional[list[dict]] = None,
) -> list:
    """Assemble system prompt + remembered turns + the new user turn (L0 memory).

    ``history`` is the transcript as ``[{"role": "user"|"assistant",
    "content": str}, ...]``, oldest first. Unknown roles and empty turns are
    skipped rather than raising, so a malformed row in the store cannot break
    the conversation.
    """
    messages: list = [SystemMessage(content=system_prompt)]

    for turn in history or []:
        if not isinstance(turn, dict):
            continue
        content = str(turn.get("content") or "").strip()
        if not content:
            continue
        content = content[:MAX_HISTORY_CONTENT_CHARS]
        role = turn.get("role")
        if role == "assistant":
            messages.append(AIMessage(content=content))
        elif role == "user":
            messages.append(HumanMessage(content=content))

    messages.append(HumanMessage(content=user_prompt))
    return messages


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def call_llm(
    system_prompt: str,
    user_prompt: str,
    mock_response: dict | None = None,
    provider: str | None = None,
    history: list[dict] | None = None,
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
        history:       Optional prior turns (L0 memory), oldest first.

    Returns:
        A dict parsed from the LLM's JSON response, or *mock_response*.
    """
    provider = provider or settings.default_llm_provider
    llm = _get_llm(provider)

    if llm is None:
        return mock_response or {"error": f"API key not configured for provider '{provider}'"}

    try:
        messages = _build_messages(system_prompt, user_prompt, history)
        response = llm.invoke(messages)
        content = response.content if hasattr(response, "content") else str(response)
        return json.loads(_extract_json(content))
    except Exception as e:
        # P10: log the failure before falling back to mock
        logger.warning(
            "LLM call failed (provider=%s): %s; using mock_response",
            provider, e,
            exc_info=True,
        )
        if mock_response is not None:
            return mock_response
        raise


# ---------------------------------------------------------------------------
# Async API (P0.2)
# ---------------------------------------------------------------------------

async def acall_llm(
    system_prompt: str,
    user_prompt: str,
    mock_response: dict | None = None,
    provider: str | None = None,
    history: list[dict] | None = None,
) -> dict:
    """Async counterpart of call_llm using llm.ainvoke().

    When the provider's API key is absent, returns mock_response
    synchronously (no I/O needed) so the event loop is not blocked.
    """
    provider = provider or settings.default_llm_provider
    llm = _get_llm(provider)

    if llm is None:
        return mock_response or {"error": f"API key not configured for provider '{provider}'"}

    try:
        messages = _build_messages(system_prompt, user_prompt, history)
        response = await llm.ainvoke(messages)
        content = response.content if hasattr(response, "content") else str(response)
        return json.loads(_extract_json(content))
    except Exception as e:
        logger.warning(
            "LLM async call failed (provider=%s): %s; using mock_response",
            provider, e,
            exc_info=True,
        )
        if mock_response is not None:
            return mock_response
        raise


async def acall_llm_text(
    system_prompt: str,
    user_prompt: str,
    history: list[dict] | None = None,
    provider: str | None = None,
    mock_response: str = "",
) -> str:
    """Free-form counterpart of :func:`acall_llm`: returns plain text.

    The structured call is right for intent/slot extraction, but forcing a
    JSON contract on a *knowledge question* is why the agent used to answer
    "好问题～不过我更擅长帮你规划行程" instead of actually answering. This
    entry point exists for the cases where the model must genuinely reply:
    travel questions, chit-chat, and summary compression (L1).

    Returns ``mock_response`` (empty string by default) when no API key is
    configured, so callers can fall back deterministically.
    """
    provider = provider or settings.default_llm_provider
    llm = _get_llm(provider)

    if llm is None:
        return mock_response

    try:
        messages = _build_messages(system_prompt, user_prompt, history)
        response = await llm.ainvoke(messages)
        return _as_text(response).strip()
    except Exception as e:
        logger.warning(
            "LLM text call failed (provider=%s): %s; using mock_response",
            provider, e,
            exc_info=True,
        )
        if mock_response:
            return mock_response
        raise
