from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from api.services.auth_service import auth_service
from .deps import get_current_user

router = APIRouter()


class WorkspaceOut(BaseModel):
    id: str
    name: str
    role: str


@router.get("/workspace/current", response_model=WorkspaceOut)
async def current_workspace(user: dict = Depends(get_current_user)):
    return WorkspaceOut(
        id="default", name="Default Workspace", role=user.get("role", "member")
    )


@router.get("/workspace/members")
async def list_members(user: dict = Depends(get_current_user)):
    if user.get("role") not in {"owner", "admin"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin required"
        )
    return {"data": auth_service.list_users()}
