from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator, Dict, List, Optional

from api.core.agent.entities import (
    AgentConfig,
    AgentMessage,
    AgentRunResult,
    AgentThought,
)
from api.services.llm_service import build_model_identity_system_prompt
from api.core.tools.tool_engine import ToolEngine
from api.core.memory.token_buffer_memory import TokenBufferMemory

logger = logging.getLogger(__name__)


class FunctionCallAgentRunner:
    def __init__(
        self,
        llm_client: Any,
        tool_engine: ToolEngine,
        memory: Optional[TokenBufferMemory] = None,
        config: Optional[AgentConfig] = None,
    ):
        self.llm_client = llm_client
        self.tool_engine = tool_engine
        self.memory = memory or TokenBufferMemory(max_tokens=8000)
        if config is None:
            raise ValueError("请选择模型提供商和模型后再运行智能体。")
        self.config = config
        self._thoughts: List[AgentThought] = []

    async def run(
        self,
        query: str,
        conversation_id: Optional[str] = None,
        extra_context: Optional[Dict[str, Any]] = None,
    ) -> AgentRunResult:
        self._thoughts = []
        tool_calls_count = 0
        total_tokens = 0

        system_prompt = self._build_system_prompt(extra_context)
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query},
        ]

        if conversation_id and self.memory:
            history = self.memory.get_messages(conversation_id)
            if history:
                messages = [{"role": "system", "content": system_prompt}]
                for msg in history:
                    messages.append(
                        {
                            "role": msg.role,
                            "content": msg.content,
                            **(
                                {"tool_calls": msg.tool_calls} if msg.tool_calls else {}
                            ),
                            **(
                                {"tool_call_id": msg.tool_call_id}
                                if msg.tool_call_id
                                else {}
                            ),
                            **({"name": msg.name} if msg.name else {}),
                        }
                    )
                messages.append({"role": "user", "content": query})

        for iteration in range(self.config.max_iterations):
            if self.config.verbose:
                logger.info(
                    f"Agent iteration {iteration + 1}/{self.config.max_iterations}"
                )

            response = await self._call_llm(messages)
            total_tokens += response.get("usage", {}).get("total_tokens", 0)

            assistant_message = response["choices"][0]["message"]
            content = assistant_message.get("content", "")
            tool_calls = assistant_message.get("tool_calls", [])

            thought = AgentThought(thought=content or "Deciding next action...")
            self._thoughts.append(thought)

            if not tool_calls:
                thought.final_answer = content
                result = AgentRunResult(
                    answer=content,
                    thoughts=self._thoughts,
                    tool_calls=tool_calls_count,
                    tokens_used=total_tokens,
                    finish_reason="stop",
                )
                await self._save_to_memory(conversation_id, messages, result)
                return result

            tool_calls_count += len(tool_calls)
            messages.append(
                {
                    "role": "assistant",
                    "content": content,
                    "tool_calls": tool_calls,
                }
            )

            for tool_call in tool_calls:
                tool_result = await self._execute_tool_call(tool_call)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "name": tool_call["function"]["name"],
                        "content": tool_result,
                    }
                )

                thought.action = tool_call["function"]["name"]
                try:
                    thought.action_input = json.loads(
                        tool_call["function"]["arguments"]
                    )
                except json.JSONDecodeError:
                    thought.action_input = {"raw": tool_call["function"]["arguments"]}
                thought.observation = tool_result

        result = AgentRunResult(
            answer="I reached the maximum number of iterations without finding a complete answer. "
            "Please try rephrasing your question or breaking it into smaller steps.",
            thoughts=self._thoughts,
            tool_calls=tool_calls_count,
            tokens_used=total_tokens,
            finish_reason="max_iterations",
        )
        await self._save_to_memory(conversation_id, messages, result)
        return result

    async def stream_run(
        self,
        query: str,
        conversation_id: Optional[str] = None,
        extra_context: Optional[Dict[str, Any]] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        try:
            system_prompt = self._build_system_prompt(extra_context)
            messages: List[Dict[str, Any]] = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query},
            ]

            for iteration in range(self.config.max_iterations):
                response = await self._call_llm(messages)
                assistant_message = response["choices"][0]["message"]
                content = assistant_message.get("content", "")
                tool_calls = assistant_message.get("tool_calls", [])

                if content:
                    yield {"type": "thought", "data": content}

                if not tool_calls:
                    yield {"type": "answer", "data": content}
                    return

                for tool_call in tool_calls:
                    yield {"type": "tool_call", "data": tool_call}
                    tool_result = await self._execute_tool_call(tool_call)
                    yield {
                        "type": "tool_result",
                        "data": {"call": tool_call, "result": tool_result},
                    }

                    messages.append(
                        {
                            "role": "assistant",
                            "content": content,
                            "tool_calls": [tool_call],
                        }
                    )
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call["id"],
                            "name": tool_call["function"]["name"],
                            "content": tool_result,
                        }
                    )

            yield {
                "type": "answer",
                "data": "Maximum iterations reached. Please try a more specific query.",
            }

        except Exception as e:
            logger.exception("Agent stream run failed")
            yield {"type": "error", "data": str(e)}

    def _build_system_prompt(
        self, extra_context: Optional[Dict[str, Any]] = None
    ) -> str:
        tools_description = self.tool_engine.get_tools_description()
        base_prompt = (
            "You are a helpful research assistant. You have access to the following tools:\n\n"
            f"{tools_description}\n\n"
            "When you need to use a tool, respond with a function call. "
            "When you have the final answer, respond directly without calling any tools."
        )
        if extra_context:
            context_str = "\n".join(f"{k}: {v}" for k, v in extra_context.items())
            base_prompt += f"\n\nAdditional context:\n{context_str}"
        if self.config.system_prompt:
            base_prompt += f"\n\n{self.config.system_prompt}"
        return build_model_identity_system_prompt(
            base_prompt,
            self.config.provider,
            self.config.model,
        )

    async def _call_llm(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        tools = self.tool_engine.get_openai_tools_schema()
        return await self.llm_client.chat.completions.create(
            model=self.config.model,
            messages=messages,
            tools=tools if tools else None,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )

    async def _execute_tool_call(self, tool_call: Dict[str, Any]) -> str:
        function_name = tool_call["function"]["name"]
        try:
            arguments = json.loads(tool_call["function"]["arguments"])
        except json.JSONDecodeError:
            arguments = {}

        result = await self.tool_engine.execute(function_name, arguments)
        if result.is_success:
            return result.output
        return f"Error: {result.error}"

    async def _save_to_memory(
        self,
        conversation_id: Optional[str],
        messages: List[Dict[str, Any]],
        result: AgentRunResult,
    ) -> None:
        if not conversation_id or not self.memory:
            return

        for msg in messages:
            if msg["role"] in ("user", "assistant", "tool"):
                self.memory.add_message(
                    conversation_id=conversation_id,
                    message=AgentMessage(
                        role=msg["role"],
                        content=msg.get("content", ""),
                        tool_calls=msg.get("tool_calls"),
                        tool_call_id=msg.get("tool_call_id"),
                        name=msg.get("name"),
                    ),
                )
