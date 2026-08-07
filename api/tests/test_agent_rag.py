"""Agent RAG（主动检索）单元测试：索引服务、事件帧、KB 分流与两段式检索。"""

import json
from types import SimpleNamespace

import pytest

from api.services.agent_index_service import (
    AgentIndexService,
    _extract_json_object,
)
from api.services.agent_rag_service import (
    AGENT_EVENT_PREFIX,
    AgentRAGService,
    build_event_frame,
)


class FakeStore:
    """In-memory LocalStore replacement (read/write/update semantics)."""

    def __init__(self):
        self.data = {}

    def read(self):
        return json.loads(json.dumps(self.data))

    def write(self, data):
        self.data = data

    def update(self, updater):
        self.data = updater(self.read())
        return self.data


@pytest.fixture()
def index_service(monkeypatch) -> AgentIndexService:
    monkeypatch.setattr(
        "api.services.agent_index_service.LocalStore", lambda name: FakeStore()
    )
    return AgentIndexService()


# ----------------------------------------------------------------------
# JSON 提取容错
# ----------------------------------------------------------------------
def test_extract_json_object_plain():
    assert _extract_json_object('{"title": "t", "keywords": []}') == {
        "title": "t",
        "keywords": [],
    }


def test_extract_json_object_wrapped_in_prose():
    text = '好的，以下是结果：\n```json\n{"title": "t"}\n```\n希望有帮助'
    assert _extract_json_object(text)["title"] == "t"


def test_extract_json_object_invalid():
    with pytest.raises(ValueError):
        _extract_json_object("没有任何 JSON")


# ----------------------------------------------------------------------
# 索引条目存储
# ----------------------------------------------------------------------
def test_entry_lifecycle(index_service):
    index_service.upsert_entry("kb1", "doc1", name="a.pdf", status="pending")
    index_service.upsert_entry("kb1", "doc1", status="completed", title="标题")
    index_service.upsert_entry("kb2", "doc2", name="b.pdf", status="indexing")

    entries = index_service.list_entries("kb1")
    assert len(entries) == 1
    assert entries[0]["name"] == "a.pdf"
    assert entries[0]["status"] == "completed"
    assert entries[0]["title"] == "标题"
    assert entries[0]["updated_at"]

    index_service.remove_entry("kb1", "doc1")
    assert index_service.list_entries("kb1") == []
    assert len(index_service.list_entries("kb2")) == 1

    index_service.clear_kb("kb2")
    assert index_service.list_entries("kb2") == []


def test_index_collection_name(index_service):
    assert index_service.index_collection("kb1") == "kb1__agent_index"


# ----------------------------------------------------------------------
# 事件帧协议
# ----------------------------------------------------------------------
def test_event_frame_round_trip():
    frame = build_event_frame({"stage": "tool_call", "tool": "kb_search"})
    assert frame.startswith(AGENT_EVENT_PREFIX)
    assert frame.endswith("\n")
    payload = json.loads(frame[len(AGENT_EVENT_PREFIX):])
    assert payload["stage"] == "tool_call"


# ----------------------------------------------------------------------
# KB 分流（agent 模式 vs 标准）
# ----------------------------------------------------------------------
def test_partition_kbs(monkeypatch):
    from api.services import chat_service as chat_module

    fake_kbs = {
        "knowledge_bases": {
            "kb-agent": {"rag_mode": "agent", "name": "主动库"},
            "kb-std": {"rag_mode": "standard", "name": "普通库"},
        }
    }
    monkeypatch.setattr(
        chat_module.knowledge_base_store, "read_all", lambda: fake_kbs
    )
    agent, normal = chat_module.ChatService._partition_kbs(
        ["kb-agent", "kb-std", "kb-missing"], "openai"
    )
    assert [kb_id for kb_id, _ in agent] == ["kb-agent"]
    assert agent[0][1]["name"] == "主动库"
    assert normal == ["kb-std", "kb-missing"]

    # demo provider 不支持 function calling，全部走标准路径
    agent, normal = chat_module.ChatService._partition_kbs(["kb-agent"], "demo")
    assert agent == []
    assert normal == ["kb-agent"]


# ----------------------------------------------------------------------
# kb_search 两段式检索（索引摘要层 → 块级过滤 → 降级全量）
# ----------------------------------------------------------------------
class _FakeRag:
    def __init__(self, index_hits):
        self.index_hits = index_hits

    async def _retrieve_docs(self, query, collection_name, top_k, use_reranker):
        if collection_name.endswith("__agent_index"):
            return self.index_hits
        return [
            {
                "content": "块A",
                "score": 0.9,
                "metadata": {"document_id": "doc-1", "document_name": "文档A"},
            },
            {
                "content": "块B",
                "score": 0.8,
                "metadata": {"document_id": "doc-2", "document_name": "文档B"},
            },
        ]


def _make_service(rag) -> AgentRAGService:
    service = object.__new__(AgentRAGService)  # 跳过 __init__（需真实 embedding 配置）
    service.rag = rag
    service.kb_id = "kb1"
    service._sources = []
    return service


async def test_kb_search_filters_by_index_hits():
    rag = _FakeRag(
        index_hits=[{"content": "索引", "score": 1.0, "metadata": {"document_id": "doc-1"}}]
    )
    service = _make_service(rag)
    output = await service.kb_search("查询", top_k=5)
    assert "块A" in output
    assert "块B" not in output
    assert "来源: 文档A" in output
    assert service._sources == ["文档A"]


async def test_kb_search_falls_back_to_unfiltered_when_index_empty():
    rag = _FakeRag(index_hits=[])
    service = _make_service(rag)
    output = await service.kb_search("查询", top_k=5)
    assert "块A" in output and "块B" in output
    assert set(service._sources) == {"文档A", "文档B"}


async def test_kb_search_empty_result_message():
    class _EmptyRag(_FakeRag):
        async def _retrieve_docs(self, *args, **kwargs):
            return []

    service = _make_service(_EmptyRag(index_hits=[]))
    assert "未在知识库中找到相关素材" in await service.kb_search("查询")


# ----------------------------------------------------------------------
# RAG 方案 preset
# ----------------------------------------------------------------------
def test_agent_preset_applies_rag_mode():
    from api.api.knowledge_bases import RAG_PLAN_PRESETS, _apply_rag_plan

    assert "agent" in RAG_PLAN_PRESETS
    kb = {}
    _apply_rag_plan(kb, "agent")
    assert kb["rag_mode"] == "agent"
    assert kb["rag_plan"] == "agent"

    kb2 = {}
    _apply_rag_plan(kb2, "medium")
    assert kb2["rag_mode"] == "standard"


# ----------------------------------------------------------------------
# kb_list_documents 浏览工具
# ----------------------------------------------------------------------
async def test_kb_list_documents_formats_entries(monkeypatch):
    entries = [
        {
            "document_id": "d1",
            "name": "产品手册.pdf",
            "title": "产品手册",
            "summary": "介绍产品功能",
            "keywords": ["产品", "功能"],
            "status": "completed",
        },
        {"document_id": "d2", "name": "待生成.docx", "status": "indexing"},
    ]
    monkeypatch.setattr(
        "api.services.agent_rag_service.agent_index_service.list_entries",
        lambda kb_id: entries,
    )
    service = _make_service(_FakeRag(index_hits=[]))
    output = await service.kb_list_documents()
    assert "产品手册.pdf" in output
    assert "关键词: 产品, 功能" in output
    assert "索引状态: indexing" in output


async def test_kb_list_documents_empty(monkeypatch):
    monkeypatch.setattr(
        "api.services.agent_rag_service.agent_index_service.list_entries",
        lambda kb_id: [],
    )
    service = _make_service(_FakeRag(index_hits=[]))
    assert "暂无素材索引" in await service.kb_list_documents()


# ----------------------------------------------------------------------
# langgraph 消息 → 事件帧映射
# ----------------------------------------------------------------------
def _ai_message(content="", tool_calls=None):
    return SimpleNamespace(type="ai", content=content, tool_calls=tool_calls or [])


async def _collect(service, message):
    return [frame async for frame in service._map_graph_message(message)]


async def test_map_graph_message_tool_result():
    service = _make_service(_FakeRag(index_hits=[]))
    service._sources = ["文档A"]
    message = SimpleNamespace(type="tool", name="kb_search", content="...")
    frames = await _collect(service, message)
    assert frames == [
        {
            "kind": "event",
            "payload": {
                "stage": "tool_result",
                "tool": "kb_search",
                "sources": ["文档A"],
            },
        }
    ]


async def test_map_graph_message_tool_call():
    service = _make_service(_FakeRag(index_hits=[]))
    message = _ai_message(
        content="先检索看看",
        tool_calls=[{"name": "kb_search", "args": {"query": "产品"}}],
    )
    frames = await _collect(service, message)
    stages = [f["payload"]["stage"] for f in frames]
    assert stages == ["think", "tool_call"]
    assert frames[1]["payload"]["tool"] == "kb_search"
    assert json.loads(frames[1]["payload"]["input"]) == {"query": "产品"}


async def test_map_graph_message_final_answer_sliced():
    service = _make_service(_FakeRag(index_hits=[]))
    frames = await _collect(service, _ai_message(content="x" * 50))
    assert all(f["kind"] == "text" for f in frames)
    assert "".join(f["payload"] for f in frames) == "x" * 50


# ----------------------------------------------------------------------
# 降级链：graph/runner 均不可用时退回标准 RAG
# ----------------------------------------------------------------------
async def test_stream_chat_full_fallback_chain(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    class _FallbackRag:
        async def query_stream(self, query, knowledge_base_id, system_prompt=None):
            yield "标准检索回答"

    service = object.__new__(AgentRAGService)
    service.rag = _FallbackRag()
    service.kb_id = "kb1"
    service.kb_name = "kb"
    service.resolved_model = {"provider": "openai", "model": "m"}  # 无 api_key
    service.system_prompt = None
    service.history = []
    service.conversation_id = "conv-1"
    service._sources = []

    chunks = [chunk async for chunk in service.stream_chat("你好")]
    text = "".join(chunks)
    assert "标准检索回答" in text
    assert any(
        chunk.startswith(AGENT_EVENT_PREFIX) and "fallback" in chunk
        for chunk in chunks
    )


def test_extract_final_answer():
    messages = [
        _ai_message(content="", tool_calls=[{"name": "kb_search", "args": {}}]),
        SimpleNamespace(type="tool", name="kb_search", content="..."),
        _ai_message(content="最终答案"),
    ]
    assert AgentRAGService._extract_final_answer({"messages": messages}) == "最终答案"
    assert AgentRAGService._extract_final_answer({"messages": []}) == ""


# ----------------------------------------------------------------------
# 数据存储解析优先级（与摄入路径一致）
# ----------------------------------------------------------------------
def test_resolve_kb_store_config_precedence(monkeypatch):
    from api.services.agent_rag_service import resolve_kb_store_config
    from api.services.component_config_service import component_config_service

    monkeypatch.delenv("DATA_STORE_TYPE", raising=False)
    monkeypatch.setattr(
        component_config_service,
        "get_active_datastore",
        lambda: {"data_store_type": "pgvector", "datastore": {"host": "pg"}},
    )

    # KB 级配置优先于组件配置与环境变量
    store_type, store_config = resolve_kb_store_config(
        {
            "datastore": {
                "type": "pgvector",
                "dsn": "postgresql://u:p@dbhost:5433/kb",
            }
        }
    )
    assert store_type == "pgvector"
    assert store_config["host"] == "dbhost"
    assert store_config["port"] == 5433

    # 环境变量优先于组件配置
    monkeypatch.setenv("DATA_STORE_TYPE", "elasticsearch")
    assert resolve_kb_store_config({})[0] == "elasticsearch"
    monkeypatch.delenv("DATA_STORE_TYPE")

    # 组件配置优先于方案推荐后端
    store_type, store_config = resolve_kb_store_config(
        {"recommended_backend": "sqlite"}
    )
    assert store_type == "pgvector"
    assert store_config == {"host": "pg"}

    # 方案推荐后端优先于 sqlite 兜底
    monkeypatch.setattr(
        component_config_service, "get_active_datastore", lambda: None
    )
    assert resolve_kb_store_config({"recommended_backend": "qdrant"})[0] == "qdrant"
    assert resolve_kb_store_config({})[0] == "sqlite"
