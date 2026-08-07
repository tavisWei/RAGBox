from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Any, Dict

from api.services.component_config_service import component_config_service
from .deps import get_current_user

router = APIRouter()


class ComponentConfigUpdate(BaseModel):
    enabled: bool = False
    config: Dict[str, Any]


def _require_admin(user: dict) -> None:
    if user.get("role") not in {"owner", "admin"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin required"
        )


@router.get("/component-configs")
async def list_component_configs(user: dict = Depends(get_current_user)):
    _require_admin(user)
    return component_config_service.list_components()


@router.put("/component-configs/{component_id}")
async def update_component_config(
    component_id: str,
    payload: ComponentConfigUpdate,
    user: dict = Depends(get_current_user),
):
    _require_admin(user)
    try:
        return {
            "data": component_config_service.update_component(
                component_id, payload.config, payload.enabled
            )
        }
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/component-configs/{component_id}/test")
async def test_component_config(
    component_id: str, user: dict = Depends(get_current_user)
):
    _require_admin(user)
    try:
        return component_config_service.test_component(component_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Storage management: business store selection/migration + vector store switch
# ---------------------------------------------------------------------------


class BusinessStoreAction(BaseModel):
    type: str  # "local" | "mysql"
    config: Dict[str, Any] = {}


class VectorStoreSwitch(BaseModel):
    component_id: str  # a datastore component id, e.g. "pgvector"


@router.get("/system/storage")
async def get_storage_status(user: dict = Depends(get_current_user)):
    _require_admin(user)
    from api.services.business_store import manager

    selection = manager.current_selection()
    masked_selection = dict(selection)
    if isinstance(masked_selection.get("config"), dict):
        masked_config = dict(masked_selection["config"])
        if masked_config.get("password"):
            masked_config["password"] = "********"
        masked_selection["config"] = masked_config
    backend = manager.get_backend()
    return {
        "business_store": {
            "type": backend.backend_type(),
            "configured": masked_selection,
            "namespaces": backend.list_namespaces(),
        },
        "vector_store": component_config_service.get_active_datastore(),
        "business_options": ["local", "mysql"],
        "vector_options": list(component_config_service.DATASTORE_COMPONENT_IDS),
    }


@router.post("/system/storage/business/test")
async def test_business_store(
    payload: BusinessStoreAction, user: dict = Depends(get_current_user)
):
    _require_admin(user)
    from api.services.business_store import manager

    try:
        backend = manager.make_backend(payload.type, payload.config)
    except Exception as exc:
        raise HTTPException(400, f"Business store init failed: {exc}") from exc
    if not backend.health_check():
        raise HTTPException(400, "Business store health check failed")
    return {"status": "ok", "type": payload.type}


@router.post("/system/storage/business/migrate")
async def migrate_business_store(
    payload: BusinessStoreAction, user: dict = Depends(get_current_user)
):
    """Copy all business data to the target backend, verify, then switch."""
    _require_admin(user)
    from api.services.business_store import manager

    if payload.type == manager.get_backend().backend_type():
        raise HTTPException(400, f"Already using '{payload.type}'")
    try:
        return manager.migrate_and_switch(payload.type, payload.config)
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/system/storage/vector/switch")
async def switch_vector_store(
    payload: VectorStoreSwitch, user: dict = Depends(get_current_user)
):
    """Switch the vector backend via the components page mechanism.

    Vector data is NOT migrated between backends; knowledge bases must be
    re-imported/re-indexed after the switch.
    """
    _require_admin(user)
    check = component_config_service.test_component(payload.component_id)
    if check.get("result") != "success":
        raise HTTPException(400, check.get("message", "Datastore check failed"))

    # Enable the target backend; the resolver prefers a non-SQLite enabled
    # component, so enabling is sufficient to switch.
    data = component_config_service.store.read()
    record = data.get("components", {}).get(payload.component_id)
    if not record:
        raise HTTPException(404, "Component not found")
    component_config_service.update_component(
        payload.component_id, record.get("config", {}), True
    )

    # Every KB now points at a backend without its chunks: flag reindex.
    from api.services.local_store import LocalStore

    kb_store = LocalStore("knowledge_bases.json")
    kb_data = kb_store.read()
    for kb in kb_data.get("knowledge_bases", {}).values():
        if kb.get("document_count", 0) > 0:
            kb["reindex_required"] = True
    kb_store.write(kb_data)

    return {
        "switched": True,
        "active": component_config_service.get_active_datastore(),
        "reindex_required": True,
        "message": "向量存储已切换；训练素材（文档）需要重新导入以在新后端重建索引。",
    }
