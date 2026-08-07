"""Agent RAG 查询服务：langgraph ReAct 内核的主动检索问答。

对话期流程：
  用户消息 → langgraph `create_react_agent`（注册 kb_search / kb_list_documents
    两个工具，sqlite checkpointer 按 conversation_id 持久化会话状态）
    → LLM 自主决定是否浏览素材清单、何时检索、检索几次（意图识别内生于 Agent 循环）
    → kb_search 两段式取料：先检索索引摘要层（{kb_id}__agent_index）定位
      候选文档，再在候选文档的块级分片中精确检索
    → LLM 基于取料结果生成最终回答
  降级链：langgraph 内核 → 自研 FunctionCallAgentRunner → 标准 RAG 流式检索。

流式协议：保持 text/plain；Agent 事件以 ``AGENT_EVENT_PREFIX`` 开头的单行
JSON 帧混入流中，前端按行解析，其余内容为回答正文。
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from api.core.agent.entities import AgentConfig
from api.core.agent.fc_agent_runner import FunctionCallAgentRunner
from api.core.tools.tool_engine import ToolEngine
from api.services.agent_index_service import agent_index_service
from api.services.rag_service import RAGService, parse_pgvector_dsn
from api.services.resource_config_service import ResourceLevel

logger = logging.getLogger(__name__)

try:
    from openai import AsyncOpenAI
except ImportError:  # pragma: no cover - openai is a hard dependency in prod
    AsyncOpenAI = None  # type: ignore[assignment]

# Agent 事件行前缀：事件帧 = 前缀 + JSON + "\n"，正文 chunk 不带前缀。
AGENT_EVENT_PREFIX = "@@AGENT_EVENT@@"

_AGENT_CHECKPOINT_DB = "api/data/agent_checkpoints.sqlite"

_AGENT_INSTRUCTIONS = """你可以使用以下工具主动检索知识库「{kb_name}」中的素材：
- kb_list_documents：浏览库内素材清单（文档名、标题、关键词、摘要），适合先了解有哪些资料。
- kb_search：按查询检索素材片段，返回片段内容与来源文档名。

行为准则：
1. 当用户的问题可能涉及知识库中的资料时，主动使用工具检索，不要臆造内容；不确定有什么资料时先浏览清单。
2. 寒暄、常识性问题或与知识库资料无关的问题，直接回答，不要调用工具。
3. 一次检索结果不理想时，可以换用不同的查询词再次检索。
4. 基于检索到的素材回答时，在相关表述后标注来源（【来源: 文档名】）。
5. 检索不到相关内容时，如实告知用户。"""


class _KbSearchInput(BaseModel):
    query: str = Field(description="检索查询，应是精炼后的关键词或问题")
    top_k: int = Field(default=5, description="返回的素材片段数量，默认 5")


_agent_checkpointer: Any = None
_agent_checkpointer_failed = False


async def _get_agent_checkpointer() -> Any:
    """Process-wide sqlite checkpointer for langgraph agents (best effort).

    Returns None when unavailable so callers fall back to stateless runs.
    """
    global _agent_checkpointer, _agent_checkpointer_failed
    if _agent_checkpointer is not None or _agent_checkpointer_failed:
        return _agent_checkpointer
    try:
        import aiosqlite
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

        conn = await aiosqlite.connect(_AGENT_CHECKPOINT_DB)
        _agent_checkpointer = AsyncSqliteSaver(conn)
    except Exception:
        logger.exception("Agent checkpointer unavailable; running stateless")
        _agent_checkpointer_failed = True
        _agent_checkpointer = None
    return _agent_checkpointer


def build_event_frame(payload: Dict[str, Any]) -> str:
    """Serialize an agent event as a single stream line."""
    return f"{AGENT_EVENT_PREFIX}{json.dumps(payload, ensure_ascii=False)}\n"


class AgentRAGService:
    """Per-request agentic RAG pipeline bound to one knowledge base."""

    def __init__(
        self,
        kb_id: str,
        kb: Dict[str, Any],
        resolved_model: Dict[str, Any],
        system_prompt: Optional[str] = None,
        history: Optional[List[Dict[str, Any]]] = None,
        conversation_id: Optional[str] = None,
    ):
        self.kb_id = kb_id
        self.kb_name = kb.get("name") or kb_id
        self.resolved_model = resolved_model
        self.system_prompt = system_prompt
        self.history = history or []
        self.conversation_id = conversation_id
        self._sources: List[str] = []

        # 数据存储解析沿用 KB 自身配置（与 chat_service 的 sqlite 硬编码不同，
        # agent 路径需要定位 KB 真实的 collection）。
        datastore = kb.get("datastore") or {}
        store_type = (
            datastore.get("type") or os.getenv("DATA_STORE_TYPE") or "sqlite"
        )
        rag_config: Dict[str, Any] = {
            "data_store_type": store_type,
            "embedding_provider": kb.get("embedding_provider"),
            "embedding_model": kb.get("embedding_model"),
            "retrieval_config": kb.get("retrieval_config") or {},
            "llm_provider": resolved_model["provider"],
            "llm_model": resolved_model["model"],
            "api_key": resolved_model.get("api_key"),
            "base_url": resolved_model.get("base_url"),
        }
        if store_type == "pgvector" and datastore.get("dsn"):
            rag_config["datastore"] = parse_pgvector_dsn(datastore["dsn"])
        tier = (kb.get("hardware_tier") or "medium").lower()
        level = {
            "low": ResourceLevel.LOW,
            "high": ResourceLevel.HIGH,
        }.get(tier, ResourceLevel.MEDIUM)
        self.rag = RAGService(resource_level=level, config=rag_config)

    # ------------------------------------------------------------------
    # kb_search 工具：两段式检索（索引摘要层 → 文档块级）
    # ------------------------------------------------------------------
    async def kb_search(self, query: str, top_k: int = 5) -> str:
        try:
            top_k = max(1, min(int(top_k), 10))
        except (TypeError, ValueError):
            top_k = 5
        try:
            candidate_ids = await self._search_index(query)
            # 块级召回放宽到 top_k*4，再按命中文档过滤；过滤为空时退回全量。
            docs = await self.rag._retrieve_docs(
                query, self.kb_id, top_k=max(top_k * 4, 12), use_reranker=False
            )
            if candidate_ids:
                filtered = [
                    doc
                    for doc in docs
                    if (doc.get("metadata") or {}).get("document_id") in candidate_ids
                ]
                if filtered:
                    docs = filtered
            docs = docs[:top_k]
        except Exception as exc:
            logger.exception("kb_search failed for KB %s", self.kb_id)
            return f"检索失败: {exc}"
        if not docs:
            return "未在知识库中找到相关素材。"
        return self._format_tool_output(docs)

    async def _search_index(self, query: str) -> set:
        """Search the index-summary collection; returns candidate document_ids."""
        index_docs = await self.rag._retrieve_docs(
            query,
            agent_index_service.index_collection(self.kb_id),
            top_k=3,
            use_reranker=False,
        )
        candidate_ids = set()
        for doc in index_docs:
            metadata = doc.get("metadata") or {}
            if metadata.get("document_id"):
                candidate_ids.add(metadata["document_id"])
        return candidate_ids

    def _format_tool_output(self, docs: List[Dict[str, Any]]) -> str:
        parts = []
        sources: List[str] = []
        for index, doc in enumerate(docs, 1):
            metadata = doc.get("metadata") or {}
            name = (
                metadata.get("document_name") or metadata.get("name") or "未知文档"
            )
            if name not in sources:
                sources.append(name)
            content = str(doc.get("content", ""))[:600]
            parts.append(f"[片段{index} | 来源: {name}]\n{content}")
        self._sources = sources
        return "\n\n".join(parts)[:4000]

    async def kb_list_documents(self) -> str:
        """浏览知识库素材清单（来自 agent 索引条目）。"""
        entries = agent_index_service.list_entries(self.kb_id)
        if not entries:
            return "知识库暂无素材索引（可能仍在生成中）。"
        lines = []
        for entry in entries[:20]:
            if entry.get("status") != "completed":
                lines.append(f"- {entry.get('name')}（索引状态: {entry.get('status')}）")
                continue
            keywords = ", ".join(entry.get("keywords") or [])
            summary = (entry.get("summary") or "")[:120]
            lines.append(
                f"- {entry.get('name')}｜{entry.get('title', '')}"
                f"｜关键词: {keywords}｜摘要: {summary}"
            )
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Agent 循环
    # ------------------------------------------------------------------
    def _build_runner(self) -> FunctionCallAgentRunner:
        if AsyncOpenAI is None:
            raise RuntimeError("openai package not installed")
        provider = self.resolved_model["provider"]
        if provider == "ollama":
            base = (
                self.resolved_model.get("base_url")
                or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
            ).rstrip("/")
            client = AsyncOpenAI(
                api_key=self.resolved_model.get("api_key") or "ollama",
                base_url=f"{base}/v1",
            )
        else:
            client = AsyncOpenAI(
                api_key=self.resolved_model.get("api_key"),
                base_url=self.resolved_model.get("base_url") or None,
            )
        engine = ToolEngine()
        engine.register(
            "kb_search",
            f"检索知识库「{self.kb_name}」中的素材文档。当用户的问题可能涉及库内资料时调用；返回相关片段及其来源文档名。",
            {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "检索查询，应是精炼后的关键词或问题",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "返回的素材片段数量，默认 5",
                    },
                },
                "required": ["query"],
            },
            self.kb_search,
        )
        engine.register(
            "kb_list_documents",
            f"浏览知识库「{self.kb_name}」中的素材清单（文档名、标题、关键词、摘要），用于先了解有哪些资料再决定检索策略。",
            {"type": "object", "properties": {}},
            self.kb_list_documents,
        )
        config = AgentConfig(
            provider=provider,
            model=self.resolved_model["model"],
            temperature=0.3,
            max_iterations=4,
            max_tokens=2048,
            system_prompt=self._agent_system_prompt(),
        )
        return FunctionCallAgentRunner(client, engine, config=config)

    def _agent_system_prompt(self) -> str:
        instructions = _AGENT_INSTRUCTIONS.format(kb_name=self.kb_name)
        if self.system_prompt:
            return f"{self.system_prompt}\n\n{instructions}"
        return instructions

    def _extra_context(self) -> Dict[str, Any]:
        lines = []
        for item in self.history[-6:]:
            if item.get("query"):
                lines.append(f"用户: {item['query']}")
            if item.get("answer"):
                lines.append(f"助手: {str(item['answer'])[:500]}")
        return {"对话历史": "\n".join(lines) if lines else "（无）"}

    async def stream_chat(self, query: str) -> AsyncIterator[str]:
        """Stream agent events (prefixed JSON lines) then the answer text.

        降级链：langgraph ReAct 内核 → 自研 FunctionCallAgentRunner → 标准 RAG。
        """
        answered = False

        graph = await self._try_build_agent_graph()
        if graph is not None:
            async for frame in self._stream_graph(graph, query):
                answered = answered or frame["kind"] == "text"
                yield self._render_frame(frame)
        if answered:
            if self._sources:
                yield build_event_frame(
                    {"stage": "sources", "sources": self._sources}
                )
            return

        try:
            runner = self._build_runner()
        except Exception as exc:
            logger.exception("Agent runner init failed, falling back to standard RAG")
            yield build_event_frame(
                {"stage": "error", "detail": f"Agent 初始化失败，降级标准检索: {exc}"}
            )
        else:
            async for frame in self._stream_runner(runner, query):
                answered = answered or frame["kind"] == "text"
                yield self._render_frame(frame)
        if answered:
            if self._sources:
                yield build_event_frame(
                    {"stage": "sources", "sources": self._sources}
                )
            return

        # 最终降级：Agent 未产出回答（模型不支持 function calling、循环异常等）
        yield build_event_frame(
            {"stage": "fallback", "detail": "Agent 未产出回答，降级为标准检索"}
        )
        async for chunk in self.rag.query_stream(
            query, self.kb_id, system_prompt=self.system_prompt
        ):
            yield chunk

    @staticmethod
    def _render_frame(frame: Dict[str, Any]) -> str:
        if frame["kind"] == "event":
            return build_event_frame(frame["payload"])
        return frame["payload"]

    # ------------------------------------------------------------------
    # langgraph ReAct 内核（主路径）
    # ------------------------------------------------------------------
    async def _try_build_agent_graph(self) -> Optional[Any]:
        try:
            return await self._build_agent_graph()
        except Exception:
            logger.exception("langgraph agent kernel unavailable; will try fallback")
            return None

    async def _build_agent_graph(self) -> Any:
        from langchain_openai import ChatOpenAI
        from langchain_core.tools import StructuredTool
        from langgraph.prebuilt import create_react_agent

        provider = self.resolved_model["provider"]
        base_url = self.resolved_model.get("base_url")
        api_key = self.resolved_model.get("api_key")
        if provider == "ollama":
            base = (
                base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
            ).rstrip("/")
            base_url, api_key = f"{base}/v1", api_key or "ollama"
        if not api_key:
            raise ValueError(f"provider '{provider}' 缺少 API key，无法启动 Agent")
        model = ChatOpenAI(
            model=self.resolved_model["model"],
            api_key=api_key,
            base_url=base_url or None,
            temperature=0.3,
            max_tokens=2048,
        )
        tools = [
            StructuredTool.from_function(
                coroutine=self.kb_search,
                name="kb_search",
                description=(
                    f"检索知识库「{self.kb_name}」中的素材文档。当用户的问题可能涉及"
                    "库内资料时调用；返回相关片段及其来源文档名。"
                ),
                args_schema=_KbSearchInput,
            ),
            StructuredTool.from_function(
                coroutine=self.kb_list_documents,
                name="kb_list_documents",
                description=(
                    f"浏览知识库「{self.kb_name}」中的素材清单（文档名、标题、关键词、"
                    "摘要），用于先了解有哪些资料再决定检索策略。"
                ),
            ),
        ]
        checkpointer = await _get_agent_checkpointer()
        # 有 checkpointer 时历史由 thread state 自动接续；否则把近期历史拼进
        # system prompt 兜底。
        prompt = self._agent_system_prompt()
        if checkpointer is None:
            context = self._extra_context()
            prompt = f"{prompt}\n\n对话历史：\n{context['对话历史']}"
        return create_react_agent(
            model, tools, prompt=prompt, checkpointer=checkpointer
        )

    async def _stream_graph(
        self, graph: Any, query: str
    ) -> AsyncIterator[Dict[str, Any]]:
        config = {
            "configurable": {
                "thread_id": self.conversation_id or f"agent-rag-{self.kb_id}"
            }
        }
        try:
            async for update in graph.astream(
                {"messages": [{"role": "user", "content": query}]},
                config=config,
                stream_mode="updates",
            ):
                for _node, data in (update or {}).items():
                    for message in (data or {}).get("messages") or []:
                        async for frame in self._map_graph_message(message):
                            yield frame
        except Exception as exc:
            logger.exception("langgraph agent stream failed")
            yield {
                "kind": "event",
                "payload": {"stage": "error", "detail": str(exc)[:300]},
            }

    async def _map_graph_message(
        self, message: Any
    ) -> AsyncIterator[Dict[str, Any]]:
        msg_type = getattr(message, "type", "")
        content = message.content if isinstance(message.content, str) else ""
        tool_calls = getattr(message, "tool_calls", None) or []
        if msg_type == "tool":
            yield {
                "kind": "event",
                "payload": {
                    "stage": "tool_result",
                    "tool": getattr(message, "name", "tool"),
                    "sources": self._sources,
                },
            }
        elif tool_calls:
            if content.strip():
                yield {
                    "kind": "event",
                    "payload": {"stage": "think", "detail": content[:200]},
                }
            for tool_call in tool_calls:
                yield {
                    "kind": "event",
                    "payload": {
                        "stage": "tool_call",
                        "tool": tool_call.get("name"),
                        "input": json.dumps(
                            tool_call.get("args") or {}, ensure_ascii=False
                        ),
                    },
                }
        elif msg_type == "ai" and content.strip():
            # 与自研 runner 一致：整段回答切小片，保持前端流式观感。
            for i in range(0, len(content), 24):
                yield {"kind": "text", "payload": content[i : i + 24]}

    async def _stream_runner(
        self, runner: FunctionCallAgentRunner, query: str
    ) -> AsyncIterator[Dict[str, Any]]:
        async for event in runner.stream_run(
            query, extra_context=self._extra_context()
        ):
            event_type = event.get("type")
            data = event.get("data")
            if event_type == "thought":
                yield {
                    "kind": "event",
                    "payload": {"stage": "think", "detail": str(data)[:200]},
                }
            elif event_type == "tool_call":
                function = (data or {}).get("function", {})
                yield {
                    "kind": "event",
                    "payload": {
                        "stage": "tool_call",
                        "tool": function.get("name"),
                        "input": function.get("arguments"),
                    },
                }
            elif event_type == "tool_result":
                yield {
                    "kind": "event",
                    "payload": {
                        "stage": "tool_result",
                        "tool": "kb_search",
                        "sources": self._sources,
                    },
                }
            elif event_type == "answer":
                # Runner 的回答是一次性产出；切小片出让前端保持流式观感。
                answer = str(data or "")
                for i in range(0, len(answer), 24):
                    yield {"kind": "text", "payload": answer[i : i + 24]}
            elif event_type == "error":
                yield {
                    "kind": "event",
                    "payload": {"stage": "error", "detail": str(data)[:300]},
                }

    async def chat(self, query: str) -> Tuple[str, List[str]]:
        """Non-streaming variant used by the sync message endpoint.

        降级链与 stream_chat 一致：langgraph → 自研 runner → 标准 RAG。
        """
        graph = await self._try_build_agent_graph()
        if graph is not None:
            try:
                config = {
                    "configurable": {
                        "thread_id": self.conversation_id
                        or f"agent-rag-{self.kb_id}"
                    }
                }
                result = await graph.ainvoke(
                    {"messages": [{"role": "user", "content": query}]},
                    config=config,
                )
                answer = self._extract_final_answer(result)
                if answer:
                    return answer, self._sources
            except Exception:
                logger.exception("langgraph agent run failed; trying fallback runner")
        try:
            runner = self._build_runner()
            result = await runner.run(query, extra_context=self._extra_context())
            if result.answer:
                return result.answer, self._sources
        except Exception:
            logger.exception("Agent run failed, falling back to standard RAG")
        response = await self.rag.query(
            query, self.kb_id, system_prompt=self.system_prompt
        )
        return response.answer, self._sources

    @staticmethod
    def _extract_final_answer(result: Any) -> str:
        messages = (result or {}).get("messages") or []
        for message in reversed(messages):
            if getattr(message, "type", "") == "ai":
                content = message.content if isinstance(message.content, str) else ""
                if content.strip():
                    return content
        return ""
