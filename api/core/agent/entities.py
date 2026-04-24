"""Agent data models and entities."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AgentMessage(BaseModel):
    """A single message in an agent conversation."""

    role: str = Field(..., description="Message role: system, user, assistant, or tool")
    content: str = Field(..., description="Message content text")
    tool_calls: Optional[List[Dict[str, Any]]] = Field(
        default=None, description="Tool calls requested by the assistant"
    )
    tool_call_id: Optional[str] = Field(
        default=None, description="ID of the tool call this message responds to"
    )
    name: Optional[str] = Field(
        default=None, description="Name of the tool that produced this message"
    )


class AgentThought(BaseModel):
    """Represents a single step in the agent's reasoning chain (ReAct pattern)."""

    thought: str = Field(..., description="The agent's internal reasoning")
    action: Optional[str] = Field(
        default=None, description="The tool/action chosen by the agent"
    )
    action_input: Optional[Dict[str, Any]] = Field(
        default=None, description="Parameters passed to the action"
    )
    observation: Optional[str] = Field(
        default=None, description="Result returned from the action"
    )
    final_answer: Optional[str] = Field(
        default=None, description="The final answer if this is the last step"
    )

    @property
    def is_final(self) -> bool:
        """Check if this thought represents the final answer."""
        return self.final_answer is not None


class AgentRunResult(BaseModel):
    """Result of an agent run."""

    answer: str = Field(..., description="The final answer from the agent")
    thoughts: List[AgentThought] = Field(
        default_factory=list, description="Chain of thoughts during execution"
    )
    tool_calls: int = Field(default=0, description="Number of tool calls made")
    tokens_used: int = Field(default=0, description="Total tokens consumed")
    finish_reason: str = Field(default="stop", description="Reason for finishing")


class AgentConfig(BaseModel):
    """Configuration for an agent run."""

    provider: str = Field(..., description="LLM provider to use")
    model: str = Field(..., description="LLM model to use")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_iterations: int = Field(default=10, ge=1, le=50)
    max_tokens: int = Field(default=4000, ge=1)
    system_prompt: Optional[str] = Field(
        default=None, description="System prompt override"
    )
    verbose: bool = Field(default=False, description="Enable verbose logging")
