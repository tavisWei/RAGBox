"""LangChain tools available to workflow tool nodes."""

from datetime import datetime
from typing import Dict

import httpx
from langchain_core.tools import BaseTool, tool

from .template import safe_eval_expression


@tool
async def calculator(expression: str) -> str:
    """Evaluate an arithmetic or string expression in a restricted sandbox.

    Supports len/str/int/float/bool/sum/min/max calls and
    get/upper/lower/strip/split/replace methods.
    """
    return str(safe_eval_expression(expression, {}))


@tool
async def http_get(url: str) -> str:
    """Fetch a URL with an HTTP GET request and return the response body text
    (truncated to 5000 characters)."""
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.text[:5000]


@tool
def current_time() -> str:
    """Return the current local time in ISO 8601 format."""
    return datetime.now().isoformat()


TOOL_REGISTRY: Dict[str, BaseTool] = {
    t.name: t for t in (calculator, http_get, current_time)
}
