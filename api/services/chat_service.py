import asyncio
from datetime import datetime
from typing import Any, AsyncIterator, Dict, List, Optional
from uuid import uuid4

from api.services.local_store import LocalStore
from api.services.llm_service import ChatConfig, ChatMessage, LLMService
from api.services.model_provider_service import model_provider_service
from api.services.rag_service import RAGService


CHAT_TIMEOUT_SECONDS = 60


class ChatService:
    def __init__(self, llm_service: Optional[LLMService] = None):
        self._store = LocalStore("chat_state.json")
        state = self._store.read()
        self._conversations = state.get("conversations", {})
        self._messages = state.get("messages", {})
        self._llm_service = llm_service

    def _resolve_model_config(
        self, model_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        provider = (model_config or {}).get("provider")
        model = (model_config or {}).get("model")
        if not provider:
            raise ValueError("请选择模型提供商或先添加供应商。")
        if not model:
            raise ValueError("请选择要调用的模型。")
        active = model_provider_service.get_active_provider_config(provider)
        if not active:
            raise ValueError(f"Provider '{provider}' is not configured")
        credentials = active.get("credentials", {})
        return {
            "provider": provider,
            "model": model,
            "api_key": credentials.get("api_key"),
            "base_url": credentials.get("base_url"),
        }

    def _persist(self) -> None:
        self._store.write(
            {
                "conversations": self._conversations,
                "messages": self._messages,
            }
        )

    def create_conversation(
        self,
        app_id: str,
        user_id: str,
        name: Optional[str] = None,
        system_prompt: Optional[str] = None,
        inputs: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        conversation_id = str(uuid4())
        conversation = {
            "id": conversation_id,
            "app_id": app_id,
            "user_id": user_id,
            "name": name or "New Conversation",
            "system_prompt": system_prompt,
            "inputs": inputs or {},
            "conversation_context": {},
            "status": "active",
            "message_count": 0,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }
        self._conversations[conversation_id] = conversation
        self._messages[conversation_id] = []
        self._prune_recent_conversations(user_id, app_id, (inputs or {}).get("role_id"))
        self._persist()
        return conversation

    def _prune_recent_conversations(
        self, user_id: str, app_id: str, role_id: Optional[str], limit: int = 60
    ) -> None:
        normalized_role_id = role_id or None
        scoped = [
            item
            for item in self._conversations.values()
            if item.get("user_id") == user_id
            and item.get("app_id") == app_id
            and ((item.get("inputs") or {}).get("role_id") or None)
            == normalized_role_id
        ]
        scoped.sort(key=lambda item: item.get("updated_at") or "", reverse=True)
        for item in scoped[limit:]:
            conv_id = item.get("id")
            if conv_id:
                self._conversations.pop(conv_id, None)
                self._messages.pop(conv_id, None)

    def _trim_conversation_messages(
        self, conversation_id: str, limit: int = 60
    ) -> None:
        messages = self._messages.get(conversation_id, [])
        if len(messages) > limit:
            self._messages[conversation_id] = messages[-limit:]

    async def send_message(
        self,
        conversation_id: str,
        query: str,
        model_config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        conversation = self._conversations.get(conversation_id)
        if not conversation:
            raise ValueError("Conversation not found")

        message = {
            "id": str(uuid4()),
            "conversation_id": conversation_id,
            "query": query,
            "answer": None,
            "message_metadata": {},
            "status": "processing",
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }

        history = self._messages.get(conversation_id, [])
        chat_messages = self._build_chat_messages(history, query)

        resolved_model = self._resolve_model_config(model_config)
        llm_service = self._llm_service or LLMService(
            provider=resolved_model["provider"],
            model=resolved_model["model"],
            api_key=resolved_model["api_key"],
            base_url=resolved_model["base_url"],
        )

        try:
            kb_ids = (model_config or {}).get("knowledge_base_ids") or (
                conversation.get("inputs") or {}
            ).get("knowledge_base_ids")
            if not kb_ids:
                kb_id = (model_config or {}).get("knowledge_base_id") or (
                    conversation.get("inputs") or {}
                ).get("knowledge_base_id")
                kb_ids = [kb_id] if kb_id else []
            if kb_ids:
                rag_config: Dict[str, Any] = {
                    "data_store_type": "sqlite",
                    "llm_provider": resolved_model["provider"],
                    "llm_model": resolved_model["model"],
                    "api_key": resolved_model["api_key"],
                    "base_url": resolved_model["base_url"],
                }
                rag = RAGService(config=rag_config)
                answers = []
                for kb_id in kb_ids:
                    response = await asyncio.wait_for(
                        rag.query(
                            query=query,
                            knowledge_base_id=kb_id,
                            conversation_id=conversation_id,
                            system_prompt=conversation.get("system_prompt"),
                        ),
                        timeout=CHAT_TIMEOUT_SECONDS,
                    )
                    answers.append(response.answer)
                message["answer"] = "\n\n".join(answers)
            else:
                response = await asyncio.wait_for(
                    llm_service.chat(
                        messages=chat_messages,
                        config=ChatConfig(
                            system_prompt=conversation.get("system_prompt")
                            or "You are a helpful AI assistant.",
                            max_tokens=2048,
                            temperature=0.7,
                        ),
                    ),
                    timeout=CHAT_TIMEOUT_SECONDS,
                )
                message["answer"] = response.content
            message["status"] = "completed"
        except Exception as exc:
            message["answer"] = f"Error: {str(exc)}"
            message["status"] = "failed"

        message["updated_at"] = datetime.utcnow().isoformat()
        self._messages[conversation_id].append(message)
        self._trim_conversation_messages(conversation_id)
        conversation["message_count"] = len(self._messages[conversation_id])
        conversation["updated_at"] = datetime.utcnow().isoformat()
        self._prune_recent_conversations(
            conversation.get("user_id"),
            conversation.get("app_id"),
            (conversation.get("inputs") or {}).get("role_id"),
        )
        self._persist()
        return message

    async def stream_message(
        self,
        conversation_id: str,
        query: str,
        model_config: Optional[Dict[str, Any]] = None,
    ) -> AsyncIterator[str]:
        conversation = self._conversations.get(conversation_id)
        if not conversation:
            raise ValueError("Conversation not found")
        history = self._messages.get(conversation_id, [])
        chat_messages = self._build_chat_messages(history, query)
        resolved_model = self._resolve_model_config(model_config)
        message = {
            "id": str(uuid4()),
            "conversation_id": conversation_id,
            "query": query,
            "answer": "",
            "message_metadata": {},
            "status": "processing",
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }
        self._messages.setdefault(conversation_id, []).append(message)
        try:
            kb_ids = (model_config or {}).get("knowledge_base_ids") or (
                conversation.get("inputs") or {}
            ).get("knowledge_base_ids")
            if not kb_ids:
                kb_id = (model_config or {}).get("knowledge_base_id") or (
                    conversation.get("inputs") or {}
                ).get("knowledge_base_id")
                kb_ids = [kb_id] if kb_id else []
            if kb_ids:
                rag_config: Dict[str, Any] = {
                    "data_store_type": "sqlite",
                    "llm_provider": resolved_model["provider"],
                    "llm_model": resolved_model["model"],
                    "api_key": resolved_model["api_key"],
                    "base_url": resolved_model["base_url"],
                }
                rag = RAGService(config=rag_config)
                for kb_id in kb_ids:
                    async for chunk in rag.query_stream(
                        query=query,
                        knowledge_base_id=kb_id,
                        conversation_id=conversation_id,
                        system_prompt=conversation.get("system_prompt"),
                    ):
                        message["answer"] += chunk
                        yield chunk
                    if len(kb_ids) > 1 and kb_id != kb_ids[-1]:
                        message["answer"] += "\n\n"
                        yield "\n\n"
            else:
                llm = LLMService(
                    provider=resolved_model["provider"],
                    model=resolved_model["model"],
                    api_key=resolved_model["api_key"],
                    base_url=resolved_model["base_url"],
                )
                async for chunk in llm.chat_stream(
                    messages=chat_messages,
                    config=ChatConfig(
                        system_prompt=conversation.get("system_prompt")
                        or "You are a helpful AI assistant.",
                        max_tokens=2048,
                        temperature=0.7,
                        stream=True,
                    ),
                ):
                    message["answer"] += chunk
                    yield chunk
            message["status"] = "completed"
        except Exception as exc:
            error_message = f"Error: {str(exc)}"
            message["status"] = "failed"
            message["answer"] = error_message
            yield error_message
        message["updated_at"] = datetime.utcnow().isoformat()
        self._trim_conversation_messages(conversation_id)
        conversation["message_count"] = len(self._messages[conversation_id])
        conversation["updated_at"] = datetime.utcnow().isoformat()
        self._prune_recent_conversations(
            conversation.get("user_id"),
            conversation.get("app_id"),
            (conversation.get("inputs") or {}).get("role_id"),
        )
        self._persist()

    def _build_chat_messages(
        self, history: List[Dict[str, Any]], current_query: str
    ) -> List[ChatMessage]:
        messages: List[ChatMessage] = []
        for item in history[-10:]:
            if item.get("query"):
                messages.append(ChatMessage(role="user", content=item["query"]))
            if item.get("answer"):
                messages.append(ChatMessage(role="assistant", content=item["answer"]))
        messages.append(ChatMessage(role="user", content=current_query))
        return messages

    def get_conversation(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        return self._conversations.get(conversation_id)

    def get_conversation_history(
        self, conversation_id: str, limit: int = 60, offset: int = 0
    ) -> List[Dict[str, Any]]:
        messages = self._messages.get(conversation_id, [])
        return messages[offset : offset + limit]

    def list_conversations(
        self,
        app_id: Optional[str] = None,
        user_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        conversations = list(self._conversations.values())
        if app_id:
            conversations = [item for item in conversations if item["app_id"] == app_id]
        if user_id:
            conversations = [
                item for item in conversations if item["user_id"] == user_id
            ]
        if status:
            conversations = [item for item in conversations if item["status"] == status]
        conversations.sort(key=lambda item: item["updated_at"], reverse=True)
        return conversations[offset : offset + limit]


_chat_service: Optional[ChatService] = None


def get_chat_service(llm_service: Optional[LLMService] = None) -> ChatService:
    global _chat_service
    if _chat_service is None:
        _chat_service = ChatService(llm_service=llm_service)
    return _chat_service
