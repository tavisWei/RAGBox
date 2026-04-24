"""LLM response types and data classes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class LLMUsage:
    """Token usage information for LLM calls."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def __add__(self, other: LLMUsage) -> LLMUsage:
        """Add two usage objects together."""
        return LLMUsage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
        )


@dataclass
class LLMMessage:
    """A message in a conversation."""

    role: str  # "system", "user", "assistant", "function"
    content: str
    name: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary format for API calls."""
        result = {"role": self.role, "content": self.content}
        if self.name:
            result["name"] = self.name
        return result


@dataclass
class LLMResult:
    """Result from an LLM invocation."""

    content: str
    model: str
    usage: LLMUsage = field(default_factory=LLMUsage)
    finish_reason: Optional[str] = None
    system_fingerprint: Optional[str] = None

    @property
    def is_complete(self) -> bool:
        """Check if the response is complete (not truncated)."""
        return self.finish_reason == "stop" or self.finish_reason is None

    @property
    def is_truncated(self) -> bool:
        """Check if the response was truncated due to length limits."""
        return self.finish_reason == "length"
