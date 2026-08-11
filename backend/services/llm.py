"""LLM Service — shared OpenAI ChatOpenAI client with mock fallback.

Provides a single `call_llm()` function that nodes can use without
repeating configuration.  When OPENAI_API_KEY is absent, returns
a mock response so the graph remains testable.
"""

import json
import os
from typing import Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from config.settings import settings


_llm_instance: Optional[ChatOpenAI] = None


def _get_llm() -> Optional[ChatOpenAI]:
    """Lazy-init the ChatOpenAI client.  Returns None if no key."""
    global _llm_instance
    if _llm_instance is None and settings.openai_api_key:
        _llm_instance = ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=0.7,
            max_tokens=4096,
        )
    return _llm_instance


def _extract_json(content: str) -> str:
    """Strip markdown code fences from LLM output."""
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0]
    elif "```" in content:
        content = content.split("```")[1].split("```")[0]
    return content.strip()


def call_llm(system_prompt: str, user_prompt: str, mock_response: dict | None = None) -> dict:
    """Call the OpenAI LLM with system + user prompts.

    Args:
        system_prompt: System-level instructions for the LLM.
        user_prompt:  The user message / query.
        mock_response: Fallback dict returned when no API key is available
                       or the call fails.  If None, returns {"error": "..."}.

    Returns:
        A dict parsed from the LLM's JSON response, or the mock_response.
    """
    llm = _get_llm()

    if llm is None:
        return mock_response or {"error": "OPENAI_API_KEY not configured"}

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
