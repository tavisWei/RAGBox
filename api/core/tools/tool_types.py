"""Tool type definitions for the agent system."""

from __future__ import annotations

from enum import Enum


class ToolType(str, Enum):
    """Enumeration of tool types supported by the system."""

    BUILTIN = "builtin"  # Built-in tools provided by the system
    CUSTOM = "custom"  # Custom tools defined by users
    API = "api"  # External API-based tools
