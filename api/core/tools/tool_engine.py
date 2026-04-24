from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from api.core.tools.base_tool import ToolResult
from api.core.tools.tool_types import ToolType

logger = logging.getLogger(__name__)


class ToolEngine:
    def __init__(self):
        self._tools: Dict[str, Dict[str, Any]] = {}
        self._handlers: Dict[str, Any] = {}

    def register(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        handler: Any,
        tool_type: ToolType = ToolType.BUILTIN,
    ) -> None:
        self._tools[name] = {
            "name": name,
            "description": description,
            "parameters": parameters,
            "type": tool_type,
        }
        self._handlers[name] = handler
        logger.info(f"Registered tool: {name} ({tool_type.value})")

    def unregister(self, name: str) -> None:
        self._tools.pop(name, None)
        self._handlers.pop(name, None)
        logger.info(f"Unregistered tool: {name}")

    def get_tool(self, name: str) -> Optional[Dict[str, Any]]:
        return self._tools.get(name)

    def list_tools(self) -> List[Dict[str, Any]]:
        return list(self._tools.values())

    def get_tools_description(self) -> str:
        lines = []
        for tool in self._tools.values():
            lines.append(f"- {tool['name']}: {tool['description']}")
        return "\n".join(lines) if lines else "No tools available."

    def get_openai_tools_schema(self) -> List[Dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["parameters"],
                },
            }
            for tool in self._tools.values()
        ]

    async def execute(self, name: str, arguments: Dict[str, Any]) -> ToolResult:
        handler = self._handlers.get(name)
        if not handler:
            return ToolResult.failure(f"Tool '{name}' not found")

        try:
            import inspect

            if inspect.iscoroutinefunction(handler):
                result = await handler(**arguments)
            else:
                result = handler(**arguments)

            if isinstance(result, ToolResult):
                return result
            return ToolResult.success(str(result))

        except Exception as e:
            logger.exception(f"Tool execution failed: {name}")
            return ToolResult.failure(str(e))

    def has_tool(self, name: str) -> bool:
        return name in self._tools

    def clear(self) -> None:
        self._tools.clear()
        self._handlers.clear()
