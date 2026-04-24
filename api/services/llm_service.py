import os
import asyncio
import json
from typing import List, Optional, AsyncIterator, Union, Dict, Any
from dataclasses import dataclass
from enum import Enum
import httpx

# Optional OpenAI import
try:
    from openai import AsyncOpenAI

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


class LLMError(Exception):
    """Base exception for LLM errors."""

    pass


class RateLimitError(LLMError):
    """Raised when rate limit is exceeded."""

    pass


class ModelNotFoundError(LLMError):
    """Raised when model is not found."""

    pass


@dataclass
class ChatMessage:
    """Chat message."""

    role: str  # "system", "user", "assistant"
    content: str
    name: Optional[str] = None


@dataclass
class ChatCompletion:
    """Chat completion result."""

    content: str
    model: str
    tokens_used: Optional[int] = None
    finish_reason: Optional[str] = None


@dataclass
class ChatConfig:
    """Configuration for chat completion."""

    system_prompt: str = "You are a helpful AI assistant."
    max_tokens: int = 2048
    temperature: float = 0.7
    top_p: float = 1.0
    stream: bool = False


def build_model_identity_system_prompt(
    base_prompt: str,
    provider: str,
    model: str,
) -> str:
    provider_name = provider.strip() or "configured provider"
    model_name = model.strip() or "configured model"
    identity_prompt = (
        f"当前调用的模型提供商是 {provider_name}，模型是 {model_name}。"
        "如果用户询问你的身份、模型、厂商或开发者，只能按此配置回答；"
        "不要声称自己是其他厂商或其他模型。"
    )
    if base_prompt:
        return f"{base_prompt}\n\n{identity_prompt}"
    return identity_prompt


def with_model_identity_config(
    config: ChatConfig, provider: str, model: str
) -> ChatConfig:
    return ChatConfig(
        system_prompt=build_model_identity_system_prompt(
            config.system_prompt,
            provider,
            model,
        ),
        max_tokens=config.max_tokens,
        temperature=config.temperature,
        top_p=config.top_p,
        stream=config.stream,
    )


class LLMService:
    def __init__(
        self,
        provider: str,
        model: str,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 60.0,
    ):
        if not provider or not provider.strip():
            raise ValueError("请选择模型提供商或先添加供应商。")
        if not model or not model.strip():
            raise ValueError("请选择要调用的模型。")
        self.provider = provider.lower()
        self.model = model
        self.timeout = timeout

        if self.provider == "demo":
            self.provider = "demo"
            self.client = None
        elif self.provider == "openai":
            if not OPENAI_AVAILABLE:
                raise ImportError(
                    "openai package not installed. Run: pip install openai"
                )
            api_key = api_key or os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError(
                    "OpenAI API key required. Please configure provider credentials."
                )
            else:
                self.client = AsyncOpenAI(
                    api_key=api_key,
                    base_url=base_url,
                    timeout=timeout,
                )
        elif base_url:
            if not OPENAI_AVAILABLE:
                raise ImportError(
                    "openai package not installed. Run: pip install openai"
                )
            if not api_key:
                raise ValueError(f"API key required for provider '{provider}'.")
            self.client = AsyncOpenAI(
                api_key=api_key,
                base_url=base_url,
                timeout=timeout,
            )
        elif self.provider == "ollama":
            base_url = base_url or os.getenv(
                "OLLAMA_BASE_URL", "http://localhost:11434"
            )
            self.client = httpx.AsyncClient(base_url=base_url, timeout=timeout)
        else:
            raise ValueError(f"Unknown provider: {provider}")

    async def chat(
        self,
        messages: List[ChatMessage],
        config: Optional[ChatConfig] = None,
    ) -> ChatCompletion:
        """
        Generate chat completion.

        Args:
            messages: List of chat messages
            config: Optional chat configuration

        Returns:
            ChatCompletion result
        """
        config = with_model_identity_config(
            config or ChatConfig(),
            self.provider,
            self.model,
        )

        if self.provider == "demo":
            return self._chat_demo(messages, config)
        elif self.provider == "openai" or isinstance(self.client, AsyncOpenAI):
            return await self._chat_openai(messages, config)
        elif self.provider == "ollama":
            return await self._chat_ollama(messages, config)
        else:
            raise ValueError(f"Unknown provider: {self.provider}")

    async def chat_stream(
        self,
        messages: List[ChatMessage],
        config: Optional[ChatConfig] = None,
    ) -> AsyncIterator[str]:
        """
        Generate streaming chat completion (SSE).

        Args:
            messages: List of chat messages
            config: Optional chat configuration

        Yields:
            String chunks of the response
        """
        config = with_model_identity_config(
            config or ChatConfig(),
            self.provider,
            self.model,
        )
        config.stream = True

        if self.provider == "demo":
            response = self._chat_demo(messages, config)
            for chunk in response.content.split():
                yield chunk + " "
        elif self.provider == "openai" or isinstance(self.client, AsyncOpenAI):
            async for chunk in self._chat_openai_stream(messages, config):
                yield chunk
        elif self.provider == "ollama":
            async for chunk in self._chat_ollama_stream(messages, config):
                yield chunk
        else:
            raise ValueError(f"Unknown provider: {self.provider}")

    async def _chat_openai(
        self,
        messages: List[ChatMessage],
        config: ChatConfig,
    ) -> ChatCompletion:
        """Non-streaming chat via OpenAI."""
        max_retries = 3
        last_error = None

        for attempt in range(max_retries):
            try:
                # Build message list with system prompt
                msg_list = []
                if config.system_prompt:
                    msg_list.append({"role": "system", "content": config.system_prompt})
                msg_list.extend(
                    [{"role": m.role, "content": m.content} for m in messages]
                )

                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=msg_list,
                    max_tokens=config.max_tokens,
                    temperature=config.temperature,
                    top_p=config.top_p,
                )

                choice = response.choices[0]
                return ChatCompletion(
                    content=choice.message.content or "",
                    model=self.model,
                    tokens_used=response.usage.total_tokens
                    if hasattr(response, "usage")
                    else None,
                    finish_reason=choice.finish_reason,
                )
            except Exception as e:
                last_error = e
                if "rate_limit" in str(e).lower():
                    raise RateLimitError(f"OpenAI rate limit exceeded: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2**attempt)
                continue

        raise LLMError(f"OpenAI chat failed after {max_retries} attempts: {last_error}")

    def _chat_demo(
        self,
        messages: List[ChatMessage],
        config: ChatConfig,
    ) -> ChatCompletion:
        user_message = messages[-1].content if messages else ""
        demo_responses = [
            f"这是一个演示响应。您的问题是：'{user_message[:50]}...'\n\n在演示模式下，我无法访问真实知识库。请配置 OPENAI_API_KEY 或 OLLAMA_BASE_URL 来启用真实的 RAG 功能。",
            f"Demo mode active. Your question about '{user_message[:30]}...' requires a configured LLM endpoint.",
            f"这是一个基于 RAG 的知识问答系统的演示模式响应。问题：{user_message[:50]}...",
        ]
        import random

        return ChatCompletion(
            content=random.choice(demo_responses),
            model="demo",
            tokens_used=50,
            finish_reason="stop",
        )

    async def _chat_openai_stream(
        self,
        messages: List[ChatMessage],
        config: ChatConfig,
    ) -> AsyncIterator[str]:
        """Streaming chat via OpenAI."""
        msg_list = []
        if config.system_prompt:
            msg_list.append({"role": "system", "content": config.system_prompt})
        msg_list.extend([{"role": m.role, "content": m.content} for m in messages])

        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=msg_list,
            max_tokens=config.max_tokens,
            temperature=config.temperature,
            top_p=config.top_p,
            stream=True,
        )

        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def _chat_ollama(
        self,
        messages: List[ChatMessage],
        config: ChatConfig,
    ) -> ChatCompletion:
        """Non-streaming chat via Ollama."""
        max_retries = 3
        last_error = None

        for attempt in range(max_retries):
            try:
                # Build message list with system prompt
                msg_list = []
                if config.system_prompt:
                    msg_list.append({"role": "system", "content": config.system_prompt})
                msg_list.extend(
                    [{"role": m.role, "content": m.content} for m in messages]
                )

                response = await self.client.post(
                    "/api/chat",
                    json={
                        "model": self.model,
                        "messages": msg_list,
                        "stream": False,
                        "options": {
                            "temperature": config.temperature,
                            "top_p": config.top_p,
                            "num_predict": config.max_tokens,
                        },
                    },
                )
                response.raise_for_status()
                data = response.json()

                return ChatCompletion(
                    content=data["message"]["content"],
                    model=self.model,
                    tokens_used=data.get("eval_count"),
                    finish_reason=data.get("done_reason"),
                )
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    raise ModelNotFoundError(
                        f"Ollama model '{self.model}' not found. Run: ollama pull {self.model}"
                    )
                last_error = e
                if attempt < max_retries - 1:
                    await asyncio.sleep(2**attempt)
                continue
            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    await asyncio.sleep(2**attempt)
                continue

        raise LLMError(f"Ollama chat failed after {max_retries} attempts: {last_error}")

    async def _chat_ollama_stream(
        self,
        messages: List[ChatMessage],
        config: ChatConfig,
    ) -> AsyncIterator[str]:
        """Streaming chat via Ollama."""
        msg_list = []
        if config.system_prompt:
            msg_list.append({"role": "system", "content": config.system_prompt})
        msg_list.extend([{"role": m.role, "content": m.content} for m in messages])

        async with self.client.stream(
            "POST",
            "/api/chat",
            json={
                "model": self.model,
                "messages": msg_list,
                "stream": True,
                "options": {
                    "temperature": config.temperature,
                    "top_p": config.top_p,
                    "num_predict": config.max_tokens,
                },
            },
        ) as stream:
            async for line in stream.aiter_lines():
                if line:
                    try:
                        data = json.loads(line)
                        if data.get("message"):
                            content = data["message"].get("content", "")
                            if content:
                                yield content
                    except json.JSONDecodeError:
                        continue


def create_llm_service(
    provider: str,
    model: str,
    **kwargs,
) -> "LLMService":
    return LLMService(provider=provider, model=model, **kwargs)
