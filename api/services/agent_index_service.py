"""Agent RAG 索引服务：素材导入后为文档生成 LLM 索引摘要并维护索引集合。

索引条目持久化在 ``agent_rag_index`` namespace（LocalStore），结构为
``{"indexes": {kb_id: {document_id: entry}}}``；条目的向量化副本写入数据
存储的 ``{kb_id}__agent_index`` collection，供对话期语义路由检索。
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from api.services.document_processor import DocumentChunk
from api.services.local_store import LocalStore
from api.services.llm_service import ChatConfig, ChatMessage
from api.services.model_provider_service import model_provider_service
from api.services.rag_service import RAGService
from api.services.resource_config_service import ResourceLevel

logger = logging.getLogger(__name__)

AGENT_INDEX_COLLECTION_SUFFIX = "__agent_index"

_MAX_SOURCE_CHARS = 8000

_SUMMARY_PROMPT = """你是文档索引分析助手。请阅读下面的文档内容，生成用于检索路由的索引信息。

要求：
1. 只输出一个严格的 JSON 对象，不要输出任何其他文字或 markdown 代码块。
2. JSON 结构：{{"title": "文档标题", "summary": "200字以内的内容摘要", "keywords": ["关键词", ...至多8个], "questions": ["该文档能回答的典型问题", ...至多5个]}}

文档名：{name}
文档内容：
{text}"""


def resolve_default_llm_config() -> Optional[Dict[str, Any]]:
    """Pick the first provider with an active credential and a default model.

    Returns a dict in RAGService config key form (llm_provider/llm_model/
    api_key/base_url), or None when no provider is fully configured.
    """
    for provider in model_provider_service.list_providers():
        if not (provider.get("active_credential_id") and provider.get("default_model")):
            continue
        active = model_provider_service.get_active_provider_config(
            provider["provider"]
        )
        if not active:
            continue
        credentials = active.get("credentials", {})
        return {
            "llm_provider": provider["provider"],
            "llm_model": active.get("model") or provider["default_model"],
            "api_key": credentials.get("api_key"),
            "base_url": credentials.get("base_url"),
        }
    return None


def _extract_json_object(text: str) -> Dict[str, Any]:
    """Extract the first JSON object from an LLM response (tolerates prose)."""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("LLM 响应中未找到 JSON 对象")
    return json.loads(text[start : end + 1])


class AgentIndexService:
    def __init__(self) -> None:
        self._store = LocalStore("agent_rag_index.json")

    @staticmethod
    def index_collection(kb_id: str) -> str:
        return f"{kb_id}{AGENT_INDEX_COLLECTION_SUFFIX}"

    def _get_entry(self, kb_id: str, document_id: str) -> Optional[Dict[str, Any]]:
        data = self._store.read()
        return (data.get("indexes", {}).get(kb_id, {}) or {}).get(document_id)

    def list_entries(self, kb_id: str) -> List[Dict[str, Any]]:
        data = self._store.read()
        entries = (data.get("indexes", {}).get(kb_id, {}) or {}).values()
        result = list(entries)
        result.sort(key=lambda item: item.get("updated_at") or "", reverse=True)
        return result

    def upsert_entry(self, kb_id: str, document_id: str, **fields: Any) -> None:
        def _update(data: Dict[str, Any]) -> Dict[str, Any]:
            kb_entries = data.setdefault("indexes", {}).setdefault(kb_id, {})
            entry = kb_entries.get(document_id) or {"document_id": document_id}
            entry.update(fields)
            entry["updated_at"] = datetime.utcnow().isoformat()
            kb_entries[document_id] = entry
            return data

        self._store.update(_update)

    def remove_entry(self, kb_id: str, document_id: str) -> None:
        def _update(data: Dict[str, Any]) -> Dict[str, Any]:
            kb_entries = data.setdefault("indexes", {}).setdefault(kb_id, {})
            kb_entries.pop(document_id, None)
            return data

        self._store.update(_update)

    def clear_kb(self, kb_id: str) -> None:
        def _update(data: Dict[str, Any]) -> Dict[str, Any]:
            data.setdefault("indexes", {}).pop(kb_id, None)
            return data

        self._store.update(_update)

    async def schedule_index(
        self,
        kb_id: str,
        document_id: str,
        name: str,
        text: str,
        rag_config: Dict[str, Any],
        resource_level: ResourceLevel = ResourceLevel.MEDIUM,
    ) -> None:
        """Generate the index entry for one document and embed it.

        Designed to run as a FastAPI background task after ingestion; never
        raises — failures are recorded on the entry as status=error.
        """
        self.upsert_entry(kb_id, document_id, name=name, status="indexing", error=None)
        try:
            rag = RAGService(resource_level=resource_level, config=rag_config)
            generated = await self._generate_entry(rag, name, text)
            self.upsert_entry(kb_id, document_id, status="completed", **generated)
            entry = self._get_entry(kb_id, document_id)
            if entry:
                await self._embed_entry(rag, kb_id, entry)
        except Exception as exc:
            logger.exception("Agent index generation failed for %s/%s", kb_id, document_id)
            self.upsert_entry(kb_id, document_id, status="error", error=str(exc)[:300])

    async def rebuild_kb(
        self,
        kb_id: str,
        documents: List[Dict[str, Any]],
        rag_config: Dict[str, Any],
        resource_level: ResourceLevel = ResourceLevel.MEDIUM,
    ) -> None:
        """Regenerate every index entry of a KB from its stored chunks."""
        rag = RAGService(resource_level=resource_level, config=rag_config)
        texts = await asyncio.to_thread(self._collect_document_texts, rag, kb_id)
        await self._drop_collection(rag, kb_id)
        for doc in documents:
            document_id = doc.get("id")
            name = doc.get("name") or document_id
            if not document_id:
                continue
            text = texts.get(document_id)
            if not text:
                self.upsert_entry(
                    kb_id,
                    document_id,
                    name=name,
                    status="error",
                    error="未找到原文分块（可能为旧数据），请重新导入该文档",
                )
                continue
            self.upsert_entry(kb_id, document_id, name=name, status="indexing", error=None)
            try:
                generated = await self._generate_entry(rag, name, text)
                self.upsert_entry(kb_id, document_id, status="completed", **generated)
                entry = self._get_entry(kb_id, document_id)
                if entry:
                    await self._embed_entry(rag, kb_id, entry)
            except Exception as exc:
                logger.exception("Agent index rebuild failed for %s/%s", kb_id, document_id)
                self.upsert_entry(kb_id, document_id, status="error", error=str(exc)[:300])

    async def resync_collection(
        self,
        kb_id: str,
        rag_config: Dict[str, Any],
        resource_level: ResourceLevel = ResourceLevel.MEDIUM,
    ) -> None:
        """Rebuild the index collection from the completed entries.

        Used after entries are removed so stale summaries stop surfacing in
        index search. Re-embeds only short summary texts, so it is cheap.
        """
        rag = RAGService(resource_level=resource_level, config=rag_config)
        await self._drop_collection(rag, kb_id)
        for entry in self.list_entries(kb_id):
            if entry.get("status") == "completed":
                await self._embed_entry(rag, kb_id, entry)

    def delete_index_collection(self, kb_id: str, rag_config: Dict[str, Any]) -> None:
        """Drop the index collection directly via the data store (sync)."""
        from api.core.rag.datasource.unified.data_store_factory import DataStoreFactory

        store_type = rag_config.get("data_store_type") or "sqlite"
        config: Dict[str, Any] = {
            "db_path": "api/data/rag.sqlite",
            "vector_enabled": rag_config.get("vector_enabled", True),
        }
        config.update(rag_config.get("datastore") or {})
        try:
            store = DataStoreFactory.create(store_type=store_type, config=config)
            store.delete_collection(self.index_collection(kb_id))
        except Exception:
            logger.exception("Failed to delete agent index collection for %s", kb_id)

    async def _generate_entry(
        self, rag: RAGService, name: str, text: str
    ) -> Dict[str, Any]:
        prompt = _SUMMARY_PROMPT.format(name=name, text=text[:_MAX_SOURCE_CHARS])
        response = await rag.llm_service.chat(
            messages=[ChatMessage(role="user", content=prompt)],
            config=ChatConfig(max_tokens=1024, temperature=0.3),
        )
        payload = _extract_json_object(response.content)
        return {
            "title": str(payload.get("title") or name)[:200],
            "summary": str(payload.get("summary") or "")[:1000],
            "keywords": [str(item)[:50] for item in payload.get("keywords") or []][:8],
            "questions": [str(item)[:200] for item in payload.get("questions") or []][:5],
        }

    async def _embed_entry(
        self, rag: RAGService, kb_id: str, entry: Dict[str, Any]
    ) -> None:
        content = (
            f"{entry.get('title', '')}\n"
            f"{entry.get('summary', '')}\n"
            f"关键词: {', '.join(entry.get('keywords') or [])}\n"
            f"典型问题: {'；'.join(entry.get('questions') or [])}"
        )
        chunk = DocumentChunk(
            content=content,
            chunk_index=0,
            start_char=0,
            end_char=len(content),
            metadata={
                "type": "agent_index",
                "document_id": entry["document_id"],
                "document_name": entry.get("name") or entry.get("title") or "",
            },
        )
        await rag.add_documents(
            knowledge_base_id=self.index_collection(kb_id),
            documents=[chunk],
        )

    async def _drop_collection(self, rag: RAGService, kb_id: str) -> None:
        try:
            await asyncio.to_thread(
                rag.data_store.delete_collection, self.index_collection(kb_id)
            )
        except Exception:
            # Collection may not exist yet; recreate happens on next add.
            pass

    @staticmethod
    def _collect_document_texts(rag: RAGService, kb_id: str) -> Dict[str, str]:
        """Reconstruct per-document text from stored chunks (grouped by the
        document_id metadata injected at ingestion time)."""
        texts: Dict[str, List[str]] = {}
        for item in rag.data_store.list_documents(kb_id):
            metadata = item.get("metadata") or {}
            document_id = metadata.get("document_id")
            if not document_id:
                continue
            texts.setdefault(document_id, []).append(item.get("content") or "")
        return {doc_id: "\n".join(parts) for doc_id, parts in texts.items()}


agent_index_service = AgentIndexService()
