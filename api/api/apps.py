import asyncio

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uuid

from api.core.agent import FunctionCallAgentRunner
from api.core.memory import TokenBufferMemory
from api.core.prompt import PromptTemplateParser
from api.services.local_store import LocalStore
from api.services.model_provider_service import model_provider_service
from api.services.llm_service import LLMService, ChatMessage, ChatConfig
from .deps import get_current_user

router = APIRouter()


class AppCreate(BaseModel):
    name: str
    mode: str = "chat"
    description: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None


class AppOut(BaseModel):
    id: str
    name: str
    mode: str
    description: Optional[str]
    provider: Optional[str] = None
    model: Optional[str] = None


class AppUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None


class AgentRunRequest(BaseModel):
    query: str
    system_prompt: Optional[str] = None
    max_iterations: int = 5
    provider: Optional[str] = None
    model: Optional[str] = None


class AgentRunResponse(BaseModel):
    answer: str
    iterations: int


class MemoryAddRequest(BaseModel):
    role: str
    content: str


class MemoryGetResponse(BaseModel):
    messages: List[Dict[str, str]]
    history_text: str


class PromptFormatRequest(BaseModel):
    template: str
    inputs: Dict[str, str]


class PromptTemplateCreate(BaseModel):
    name: str
    description: Optional[str] = None
    template: str
    category: str = "general"


class PromptTemplateUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    template: Optional[str] = None
    category: Optional[str] = None


class PromptTemplateFormatRequest(BaseModel):
    inputs: Dict[str, str]


class PromptFormatResponse(BaseModel):
    result: str
    variables: List[str]


_app_store = LocalStore("apps.json")
_app_store_data = _app_store.read()
_apps: dict = _app_store_data.get("apps", {})
_memories: dict = {}
AGENT_RUN_TIMEOUT_SECONDS = 60
_prompt_store = LocalStore("prompt_templates.json")
_prompt_store_data = _prompt_store.read()
_prompt_templates: dict = _prompt_store_data.get("templates", {})


def _persist_apps() -> None:
    _app_store.write({"apps": _apps})


def _persist_prompt_templates() -> None:
    _prompt_store.write({"templates": _prompt_templates})


def _prompt_template_out(template: dict) -> dict:
    parser = PromptTemplateParser(template.get("template", ""))
    return {**template, "variables": parser.get_variables()}


@router.get("/apps", response_model=List[AppOut])
async def list_apps(user: dict = Depends(get_current_user)):
    return [AppOut(id=k, **v) for k, v in _apps.items()]


@router.post("/apps", response_model=AppOut)
async def create_app(payload: AppCreate, user: dict = Depends(get_current_user)):
    app_id = str(uuid.uuid4())
    _apps[app_id] = {
        "name": payload.name,
        "mode": payload.mode,
        "description": payload.description,
        "provider": payload.provider,
        "model": payload.model,
    }
    _persist_apps()
    return AppOut(id=app_id, **_apps[app_id])


@router.get("/apps/{app_id}", response_model=AppOut)
async def get_app(app_id: str, user: dict = Depends(get_current_user)):
    if app_id not in _apps:
        raise HTTPException(404, "App not found")
    return AppOut(id=app_id, **_apps[app_id])


@router.delete("/apps/{app_id}")
async def delete_app(app_id: str, user: dict = Depends(get_current_user)):
    if app_id in _apps:
        del _apps[app_id]
        _persist_apps()
    return {"message": "deleted"}


@router.put("/apps/{app_id}", response_model=AppOut)
async def update_app(
    app_id: str, payload: AppUpdate, user: dict = Depends(get_current_user)
):
    if app_id not in _apps:
        raise HTTPException(404, "App not found")
    app = _apps[app_id]
    if payload.name is not None:
        app["name"] = payload.name
    if payload.description is not None:
        app["description"] = payload.description
    if payload.provider is not None:
        app["provider"] = payload.provider
    if payload.model is not None:
        app["model"] = payload.model
    _persist_apps()
    return AppOut(id=app_id, **app)


@router.post("/agent/run", response_model=AgentRunResponse)
async def run_agent(request: AgentRunRequest, user: dict = Depends(get_current_user)):
    if not request.provider:
        raise HTTPException(400, "请选择模型提供商或先添加供应商。")
    if not request.model:
        raise HTTPException(400, "请选择要调用的模型。")
    llm_provider = request.provider
    llm_model = request.model
    active = model_provider_service.get_active_provider_config(request.provider)
    if not active:
        raise HTTPException(400, f"Provider '{request.provider}' is not configured")
    credentials = active.get("credentials", {})
    api_key = credentials.get("api_key")
    base_url = credentials.get("base_url")
    try:
        llm = LLMService(
            provider=llm_provider, model=llm_model, api_key=api_key, base_url=base_url
        )
        completion = await asyncio.wait_for(
            llm.chat(
                messages=[ChatMessage(role="user", content=request.query)],
                config=ChatConfig(
                    system_prompt=request.system_prompt
                    or "You are a helpful AI agent.",
                    max_tokens=2048,
                    temperature=0.7,
                ),
            ),
            timeout=AGENT_RUN_TIMEOUT_SECONDS,
        )
        answer = completion.content
    except Exception as exc:
        raise HTTPException(500, str(exc)) from exc
    return AgentRunResponse(
        answer=answer,
        iterations=1,
    )


@router.post("/memory/{conversation_id}/add")
async def add_memory(
    conversation_id: str,
    request: MemoryAddRequest,
    user: dict = Depends(get_current_user),
):
    from api.core.agent.entities import AgentMessage

    if conversation_id not in _memories:
        _memories[conversation_id] = TokenBufferMemory()
    _memories[conversation_id].add_message(
        conversation_id=conversation_id,
        message=AgentMessage(role=request.role, content=request.content),
    )
    return {"status": "ok"}


@router.get("/memory/{conversation_id}", response_model=MemoryGetResponse)
async def get_memory(conversation_id: str, user: dict = Depends(get_current_user)):
    if conversation_id not in _memories:
        raise HTTPException(404, "Conversation not found")
    memory = _memories[conversation_id]
    messages = memory.get_messages(conversation_id)
    return MemoryGetResponse(
        messages=[{"role": m.role, "content": m.content} for m in messages],
        history_text="\n".join([f"{m.role}: {m.content}" for m in messages]),
    )


@router.post("/prompt/format", response_model=PromptFormatResponse)
async def format_prompt(
    request: PromptFormatRequest, user: dict = Depends(get_current_user)
):
    parser = PromptTemplateParser(request.template)
    result = parser.render(request.inputs)
    return PromptFormatResponse(
        result=result,
        variables=parser.get_variables(),
    )


@router.get("/prompt/templates")
async def list_prompt_templates(user: dict = Depends(get_current_user)):
    return {"data": [_prompt_template_out(item) for item in _prompt_templates.values()]}


@router.post("/prompt/templates")
async def create_prompt_template(
    request: PromptTemplateCreate, user: dict = Depends(get_current_user)
):
    template_id = str(uuid.uuid4())
    record = {
        "id": template_id,
        "name": request.name,
        "description": request.description,
        "template": request.template,
        "category": request.category,
    }
    _prompt_templates[template_id] = record
    _persist_prompt_templates()
    return {"data": _prompt_template_out(record)}


@router.put("/prompt/templates/{template_id}")
async def update_prompt_template(
    template_id: str,
    request: PromptTemplateUpdate,
    user: dict = Depends(get_current_user),
):
    record = _prompt_templates.get(template_id)
    if not record:
        raise HTTPException(404, "Prompt template not found")
    for key in ["name", "description", "template", "category"]:
        value = getattr(request, key)
        if value is not None:
            record[key] = value
    _persist_prompt_templates()
    return {"data": _prompt_template_out(record)}


@router.delete("/prompt/templates/{template_id}")
async def delete_prompt_template(
    template_id: str, user: dict = Depends(get_current_user)
):
    if template_id not in _prompt_templates:
        raise HTTPException(404, "Prompt template not found")
    _prompt_templates.pop(template_id)
    _persist_prompt_templates()
    return {"result": "success"}


@router.post(
    "/prompt/templates/{template_id}/format", response_model=PromptFormatResponse
)
async def format_saved_prompt_template(
    template_id: str,
    request: PromptTemplateFormatRequest,
    user: dict = Depends(get_current_user),
):
    record = _prompt_templates.get(template_id)
    if not record:
        raise HTTPException(404, "Prompt template not found")
    parser = PromptTemplateParser(record.get("template", ""))
    return PromptFormatResponse(
        result=parser.render(request.inputs), variables=parser.get_variables()
    )
