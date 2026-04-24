from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from api.services.llm_service import ChatConfig, ChatMessage, LLMService
from api.services.model_provider_service import model_provider_service
from .local_store import LocalStore


ROLE_PROMPT_TIMEOUT_SECONDS = 60


class ChatRoleService:
    def __init__(self) -> None:
        self.store = LocalStore("chat_roles.json")

    def list_roles(self, user_id: str) -> List[Dict[str, Any]]:
        roles = self.store.read().get("roles", {})
        return [role for role in roles.values() if role.get("user_id") == user_id]

    async def create_role(
        self,
        user_id: str,
        request: str,
        knowledge_base_ids: Optional[List[str]] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        name: Optional[str] = None,
        role: Optional[str] = None,
        nickname: Optional[str] = None,
        system_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        role_id = str(uuid4())
        role_request = role or request
        role_name = nickname or name
        if system_prompt:
            completion = {
                "name": role_name or role_request.strip()[:24] or "私人角色",
                "system_prompt": system_prompt,
            }
        else:
            completion = await self.complete_role(
                role_request, provider, model, role_name
            )
        role_name = role_name or completion["name"]
        prompt = completion["system_prompt"]
        data = self.store.read()
        roles = data.setdefault("roles", {})
        roles[role_id] = {
            "id": role_id,
            "user_id": user_id,
            "name": role_name,
            "nickname": role_name,
            "role": role_request,
            "request": request,
            "system_prompt": prompt,
            "knowledge_base_id": knowledge_base_ids[0] if knowledge_base_ids else None,
            "knowledge_base_ids": knowledge_base_ids or [],
            "provider": provider,
            "model": model,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }
        self.store.write(data)
        return roles[role_id]

    def get_role(self, user_id: str, role_id: str) -> Optional[Dict[str, Any]]:
        role = self.store.read().get("roles", {}).get(role_id)
        if not role or role.get("user_id") != user_id:
            return None
        return role

    def build_system_prompt(self, request: str, nickname: Optional[str] = None) -> str:
        role_request = request.strip() or "一个专业、友好、可靠的 AI 助手"
        name_line = (
            f"你的昵称是：{nickname.strip()}。\n"
            if nickname and nickname.strip()
            else ""
        )
        return (
            name_line + f"你现在扮演：{role_request}\n"
            "请保持角色一致，主动补全该角色应具备的语气、背景知识和回答边界。"
            "如果选择了一个或多个知识库，请优先依据知识库内容回答；没有依据时要说明不确定。"
        )

    async def complete_role(
        self,
        request: str,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        nickname: Optional[str] = None,
    ) -> Dict[str, str]:
        fallback_name = nickname or request.strip()[:24] or "私人角色"
        fallback_prompt = self.build_system_prompt(request, nickname)
        if not provider:
            raise ValueError("请选择模型提供商或先添加供应商。")
        if not model:
            raise ValueError("请选择要调用的模型。")
        llm_provider = provider
        llm_model = model
        api_key = None
        base_url = None
        active = model_provider_service.get_active_provider_config(provider)
        if not active:
            raise ValueError(f"Provider '{provider}' is not configured")
        credentials = active.get("credentials", {})
        api_key = credentials.get("api_key")
        base_url = credentials.get("base_url")
        llm = self._create_llm_service(llm_provider, llm_model, api_key, base_url)
        user_content = f"昵称：{nickname or ''}\n角色：{request}"
        response = await asyncio.wait_for(
            llm.chat(
                messages=[ChatMessage(role="user", content=user_content)],
                config=ChatConfig(
                    system_prompt=(
                        "你是角色设定生成器。根据用户想聊天的对象，生成两行：\n"
                        "NAME: 简短角色名，不超过12个中文字符\n"
                        "PROMPT: 完整系统提示词，包含角色身份、语气、能力边界、如何使用私人知识库。"
                    ),
                    max_tokens=512,
                    temperature=0.4,
                ),
            ),
            timeout=ROLE_PROMPT_TIMEOUT_SECONDS,
        )
        name, prompt = self._parse_completion(
            response.content, fallback_name, fallback_prompt
        )
        return {"name": name, "system_prompt": prompt}

    def _create_llm_service(
        self,
        provider: str,
        model: str,
        api_key: Optional[str],
        base_url: Optional[str],
    ) -> LLMService:
        return LLMService(
            provider=provider,
            model=model,
            api_key=api_key,
            base_url=base_url,
        )

    def _parse_completion(
        self, text: str, fallback_name: str, fallback_prompt: str
    ) -> tuple[str, str]:
        name = fallback_name
        prompt = fallback_prompt
        content = self._strip_thinking(text)
        for line in content.splitlines():
            if line.startswith("NAME:"):
                name = line.replace("NAME:", "", 1).strip()[:24] or fallback_name
        if "PROMPT:" in content:
            prompt = content.split("PROMPT:", 1)[1].strip() or fallback_prompt
        if len(prompt.strip()) < 20:
            prompt = fallback_prompt
        return name, prompt

    def _strip_thinking(self, text: str) -> str:
        if "</think>" in text:
            return text.split("</think>", 1)[1].strip()
        return text.strip()


chat_role_service = ChatRoleService()
