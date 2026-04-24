from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.services.model_provider_service import model_provider_service
from .deps import get_current_user

router = APIRouter()


def _require_admin(user: dict) -> None:
    if user.get("role") not in {"owner", "admin"}:
        raise HTTPException(status_code=403, detail="Admin required")


class CredentialCreate(BaseModel):
    credentials: dict
    name: Optional[str] = None


class ProviderCreate(BaseModel):
    provider: str
    label: str
    models: List[dict]
    fields: List[str]
    supports_validate: bool = True
    credential_name: Optional[str] = None
    credentials: Optional[dict] = None


class ProviderUpdate(BaseModel):
    label: str
    models: List[dict]
    fields: List[str]
    supports_validate: bool = True


class ModelCreate(BaseModel):
    model_id: str
    name: str


class ModelUpdate(BaseModel):
    old_model_id: str
    model_id: str
    name: str


class CredentialUpdate(BaseModel):
    credential_id: str
    credentials: dict
    name: Optional[str] = None


class CredentialDelete(BaseModel):
    credential_id: str


class CredentialSwitch(BaseModel):
    credential_id: str


class CredentialValidate(BaseModel):
    credentials: dict


class DefaultModelUpdate(BaseModel):
    model: str


@router.get("/model-providers")
async def list_model_providers(user: dict = Depends(get_current_user)):
    return {"data": model_provider_service.list_providers()}


@router.post("/model-providers")
async def create_model_provider(
    payload: ProviderCreate, user: dict = Depends(get_current_user)
):
    _require_admin(user)
    try:
        record = model_provider_service.create_provider(
            payload.provider,
            payload.label,
            payload.models,
            payload.fields,
            payload.supports_validate,
            payload.credentials,
            payload.credential_name,
        )
        return {"result": "success", "data": record}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/model-providers/{provider}")
async def update_model_provider(
    provider: str, payload: ProviderUpdate, user: dict = Depends(get_current_user)
):
    _require_admin(user)
    try:
        record = model_provider_service.update_provider(
            provider,
            payload.label,
            payload.models,
            payload.fields,
            payload.supports_validate,
        )
        return {"result": "success", "data": record}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/model-providers/{provider}")
async def delete_model_provider(provider: str, user: dict = Depends(get_current_user)):
    _require_admin(user)
    try:
        model_provider_service.delete_provider(provider)
        return {"result": "success"}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/model-providers/{provider}/models")
async def create_provider_model(
    provider: str, payload: ModelCreate, user: dict = Depends(get_current_user)
):
    _require_admin(user)
    try:
        model_provider_service.add_model(provider, payload.model_id, payload.name)
        return {"result": "success"}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/model-providers/{provider}/models")
async def update_provider_model(
    provider: str, payload: ModelUpdate, user: dict = Depends(get_current_user)
):
    _require_admin(user)
    try:
        model_provider_service.update_model(
            provider, payload.old_model_id, payload.model_id, payload.name
        )
        return {"result": "success"}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/model-providers/{provider}/models")
async def delete_provider_model(
    provider: str, payload: ModelCreate, user: dict = Depends(get_current_user)
):
    _require_admin(user)
    try:
        model_provider_service.delete_model(provider, payload.model_id)
        return {"result": "success"}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/model-providers/{provider}/credentials")
async def create_credential(
    provider: str, payload: CredentialCreate, user: dict = Depends(get_current_user)
):
    _require_admin(user)
    try:
        record = model_provider_service.create_credential(
            provider, payload.credentials, payload.name
        )
        return {"result": "success", "data": record}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/model-providers/{provider}/credentials")
async def update_credential(
    provider: str, payload: CredentialUpdate, user: dict = Depends(get_current_user)
):
    _require_admin(user)
    try:
        record = model_provider_service.update_credential(
            provider,
            payload.credential_id,
            payload.credentials,
            payload.name,
        )
        return {"result": "success", "data": record}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/model-providers/{provider}/credentials")
async def delete_credential(
    provider: str, payload: CredentialDelete, user: dict = Depends(get_current_user)
):
    _require_admin(user)
    try:
        model_provider_service.delete_credential(provider, payload.credential_id)
        return {"result": "success"}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/model-providers/{provider}/credentials/switch")
async def switch_credential(
    provider: str, payload: CredentialSwitch, user: dict = Depends(get_current_user)
):
    _require_admin(user)
    try:
        model_provider_service.switch_active(provider, payload.credential_id)
        return {"result": "success"}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/model-providers/{provider}/credentials/validate")
async def validate_credential(
    provider: str, payload: CredentialValidate, user: dict = Depends(get_current_user)
):
    _require_admin(user)
    return model_provider_service.validate_credentials(provider, payload.credentials)


@router.post("/model-providers/{provider}/default-model")
async def set_default_model(
    provider: str, payload: DefaultModelUpdate, user: dict = Depends(get_current_user)
):
    _require_admin(user)
    model_provider_service.set_default_model(provider, payload.model)
    return {"result": "success"}
