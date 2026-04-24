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
