"""Tool result data structures."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ToolResult:
    """Result from tool execution."""

    output: str
    error: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_success(self) -> bool:
        """Check if the tool execution was successful."""
        return self.error is None

    @property
    def has_metadata(self) -> bool:
        """Check if the result has metadata."""
        return len(self.metadata) > 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary format."""
        return {
            "output": self.output,
            "error": self.error,
            "metadata": self.metadata,
        }

    @classmethod
    def success(
        cls, output: str, metadata: Optional[dict[str, Any]] = None
    ) -> ToolResult:
        """Create a successful result."""
        return cls(output=output, metadata=metadata or {})

    @classmethod
    def failure(
        cls, error: str, metadata: Optional[dict[str, Any]] = None
    ) -> ToolResult:
        """Create a failed result."""
        return cls(output="", error=error, metadata=metadata or {})
