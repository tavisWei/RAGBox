from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from api.services.chat_service import get_chat_service
from .deps import get_current_user

router = APIRouter()


class ConversationCreate(BaseModel):
    app_id: str
    name: Optional[str] = None
    system_prompt: Optional[str] = None
    knowledge_base_id: Optional[str] = None
    knowledge_base_ids: Optional[List[str]] = None
    role_id: Optional[str] = None


class MessageCreate(BaseModel):
    query: str
    provider: Optional[str] = None
    model: Optional[str] = None
    knowledge_base_id: Optional[str] = None
    knowledge_base_ids: Optional[List[str]] = None


class MessageOut(BaseModel):
    id: str
    conversation_id: str
    query: str
    answer: Optional[str]
    status: str


class ConversationOut(BaseModel):
    id: str
    app_id: str
    name: Optional[str]
    message_count: int = 0
    status: str = "active"
    role_id: Optional[str] = None
    knowledge_base_id: Optional[str] = None
    knowledge_base_ids: List[str] = Field(default_factory=list)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


def _normalize_knowledge_base_ids(
    knowledge_base_id: Optional[str], knowledge_base_ids: Optional[List[str]]
) -> List[str]:
    if knowledge_base_ids is not None:
        return [item for item in knowledge_base_ids if item]
    return [knowledge_base_id] if knowledge_base_id else []


def _conversation_out(conversation: dict) -> ConversationOut:
    inputs = conversation.get("inputs") or {}
    kb_ids = _normalize_knowledge_base_ids(
        inputs.get("knowledge_base_id"), inputs.get("knowledge_base_ids")
    )
    return ConversationOut(
        id=conversation["id"],
        app_id=conversation["app_id"],
        name=conversation["name"],
        message_count=conversation["message_count"],
        status=conversation["status"],
        role_id=inputs.get("role_id"),
        knowledge_base_id=kb_ids[0] if kb_ids else None,
        knowledge_base_ids=kb_ids,
        created_at=conversation.get("created_at"),
        updated_at=conversation.get("updated_at"),
    )


@router.post("/conversations", response_model=ConversationOut)
async def create_conversation(
    payload: ConversationCreate, user: dict = Depends(get_current_user)
):
    service = get_chat_service()
    conversation = service.create_conversation(
        app_id=payload.app_id,
        user_id=user["id"],
        name=payload.name,
        system_prompt=payload.system_prompt,
        inputs={
            "knowledge_base_id": payload.knowledge_base_id,
            "knowledge_base_ids": _normalize_knowledge_base_ids(
                payload.knowledge_base_id, payload.knowledge_base_ids
            ),
            "role_id": payload.role_id,
        },
    )
    return _conversation_out(conversation)


@router.get("/conversations/{conv_id}", response_model=ConversationOut)
async def get_conversation(conv_id: str, user: dict = Depends(get_current_user)):
    service = get_chat_service()
    conversation = service.get_conversation(conv_id)
    if not conversation:
        raise HTTPException(404, "Conversation not found")
    return _conversation_out(conversation)


@router.get("/conversations", response_model=List[ConversationOut])
async def list_conversations(
    app_id: Optional[str] = None, user: dict = Depends(get_current_user)
):
    service = get_chat_service()
    conversations = service.list_conversations(app_id=app_id, user_id=user["id"])
    return [_conversation_out(conversation) for conversation in conversations]


@router.post("/conversations/{conv_id}/messages", response_model=MessageOut)
async def send_message(
    conv_id: str, payload: MessageCreate, user: dict = Depends(get_current_user)
):
    service = get_chat_service()
    try:
        message = await service.send_message(
            conv_id,
            payload.query,
            model_config={
                "provider": payload.provider,
                "model": payload.model,
                "knowledge_base_id": payload.knowledge_base_id,
                "knowledge_base_ids": _normalize_knowledge_base_ids(
                    payload.knowledge_base_id, payload.knowledge_base_ids
                ),
            },
        )
    except ValueError as exc:
        status_code = 404 if str(exc) == "Conversation not found" else 400
        raise HTTPException(status_code, str(exc)) from exc

    return MessageOut(
        id=message["id"],
        conversation_id=message["conversation_id"],
        query=message["query"],
        answer=message["answer"],
        status=message["status"],
    )


@router.post("/conversations/{conv_id}/messages/stream")
async def stream_message(
    conv_id: str, payload: MessageCreate, user: dict = Depends(get_current_user)
):
    service = get_chat_service()

    async def event_stream():
        try:
            async for chunk in service.stream_message(
                conv_id,
                payload.query,
                model_config={
                    "provider": payload.provider,
                    "model": payload.model,
                    "knowledge_base_id": payload.knowledge_base_id,
                    "knowledge_base_ids": _normalize_knowledge_base_ids(
                        payload.knowledge_base_id, payload.knowledge_base_ids
                    ),
                },
            ):
                yield chunk
        except ValueError as exc:
            yield f"Error: {str(exc)}"

    return StreamingResponse(event_stream(), media_type="text/plain")


@router.get("/conversations/{conv_id}/messages", response_model=List[MessageOut])
async def get_messages(conv_id: str, user: dict = Depends(get_current_user)):
    service = get_chat_service()
    conversation = service.get_conversation(conv_id)
    if not conversation:
        raise HTTPException(404, "Conversation not found")
    messages = service.get_conversation_history(conv_id)
    return [
        MessageOut(
            id=message["id"],
            conversation_id=message["conversation_id"],
            query=message["query"],
            answer=message["answer"],
            status=message["status"],
        )
        for message in messages
    ]
