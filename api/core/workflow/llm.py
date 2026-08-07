"""LangChain chat-model construction for workflow LLM nodes.

Provider credentials still come from model_provider_service (via
executor._resolve_model); this module only maps the resolved provider onto the
matching LangChain chat model class.
"""

from typing import Any, Dict, Optional

from fastapi import HTTPException
from langchain_core.language_models import BaseChatModel
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI


def build_chat_model(
    resolved: Dict[str, Any],
    *,
    max_tokens: int,
    temperature: float,
    timeout: float,
) -> BaseChatModel:
    """Build a LangChain chat model from a resolved provider config.

    Mirrors the provider coverage of the legacy LLMService: "openai" and any
    provider carrying a base_url go through ChatOpenAI (OpenAI-compatible
    API); "ollama" goes through ChatOllama. The "demo" provider never reaches
    this function (handled inside the executor).
    """
    provider = str(resolved.get("provider") or "").lower()
    model = resolved.get("model")
    api_key = resolved.get("api_key")
    base_url = resolved.get("base_url")

    if provider == "ollama":
        return ChatOllama(
            model=model,
            base_url=base_url or None,
            temperature=temperature,
            timeout=timeout,
        )
    if provider == "openai" or base_url:
        if not api_key:
            raise HTTPException(400, f"API key required for provider '{provider}'.")
        return ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url=base_url,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=timeout,
        )
    raise HTTPException(400, f"Unknown provider: {provider}")
