from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.services.chat_role_service import chat_role_service
from .deps import get_current_user

router = APIRouter()


class ChatRoleCreate(BaseModel):
    request: str
    knowledge_base_id: Optional[str] = None
    knowledge_base_ids: Optional[List[str]] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    name: Optional[str] = None
    nickname: Optional[str] = None
    role: Optional[str] = None
    system_prompt: Optional[str] = None


class ChatRolePromptGenerate(BaseModel):
    role: str
    name: Optional[str] = None
    nickname: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None


@router.get("/chat-roles")
async def list_chat_roles(user: dict = Depends(get_current_user)):
    return {"data": chat_role_service.list_roles(user["id"])}


@router.post("/chat-roles")
async def create_chat_role(
    payload: ChatRoleCreate, user: dict = Depends(get_current_user)
):
    knowledge_base_ids = payload.knowledge_base_ids
    if knowledge_base_ids is None and payload.knowledge_base_id:
        knowledge_base_ids = [payload.knowledge_base_id]
    return {
        "data": await chat_role_service.create_role(
            user["id"],
            payload.request,
            knowledge_base_ids,
            payload.provider,
            payload.model,
            payload.name,
            payload.role,
            payload.nickname,
            payload.system_prompt,
        )
    }


@router.post("/chat-roles/generate-prompt")
async def generate_chat_role_prompt(
    payload: ChatRolePromptGenerate, user: dict = Depends(get_current_user)
):
    try:
        return {
            "data": await chat_role_service.complete_role(
                payload.role,
                payload.provider,
                payload.model,
                payload.nickname or payload.name,
            )
        }
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/chat-roles/{role_id}")
async def get_chat_role(role_id: str, user: dict = Depends(get_current_user)):
    role = chat_role_service.get_role(user["id"], role_id)
    if not role:
        raise HTTPException(404, "Role not found")
    return {"data": role}
