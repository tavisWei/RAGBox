from typing import Optional

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel

from api.services.auth_service import auth_service

router = APIRouter()


class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    email: str
    password: str
    username: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


class PasswordChangeRequest(BaseModel):
    old_password: str
    new_password: str


class UserUpdateRequest(BaseModel):
    role: Optional[str] = None
    status: Optional[str] = None
    name: Optional[str] = None


class PasswordResetRequest(BaseModel):
    new_password: str


class ChatContextRequest(BaseModel):
    app_id: Optional[str] = None
    role_id: Optional[str] = None
    conversation_id: Optional[str] = None


def _extract_bearer_token(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    prefix = "Bearer "
    if authorization.startswith(prefix):
        return authorization[len(prefix) :]
    return authorization


def _current_user_from_header(authorization: Optional[str]) -> dict:
    token = _extract_bearer_token(authorization)
    user = auth_service.get_user_by_token(token) if token else None
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )
    return user


def _require_admin(user: dict) -> None:
    if user.get("role") not in {"owner", "admin"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin required"
        )


@router.post("/auth/login", response_model=TokenResponse)
async def login(payload: LoginRequest):
    try:
        token, user = auth_service.login(payload.email, payload.password)
        return TokenResponse(access_token=token, user=user)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc


@router.post("/auth/register", response_model=TokenResponse)
async def register(payload: RegisterRequest):
    try:
        auth_service.register(payload.email, payload.password, payload.username)
        token, user = auth_service.login(payload.email, payload.password)
        return TokenResponse(access_token=token, user=user)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post("/auth/logout")
async def logout(authorization: Optional[str] = Header(None)):
    token = _extract_bearer_token(authorization)
    if token:
        auth_service.logout(token)
    return {"message": "Logged out"}


@router.get("/auth/me")
async def me(authorization: Optional[str] = Header(None)):
    return _current_user_from_header(authorization)


@router.post("/auth/chat-context")
async def update_chat_context(
    payload: ChatContextRequest, authorization: Optional[str] = Header(None)
):
    user = _current_user_from_header(authorization)
    try:
        return {
            "user": auth_service.update_chat_context(
                user["id"], payload.app_id, payload.role_id, payload.conversation_id
            )
        }
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc


@router.get("/auth/users")
async def list_users(authorization: Optional[str] = Header(None)):
    user = _current_user_from_header(authorization)
    _require_admin(user)
    return {"users": auth_service.list_users()}


@router.post("/auth/change-password")
async def change_password(
    payload: PasswordChangeRequest, authorization: Optional[str] = Header(None)
):
    user = _current_user_from_header(authorization)
    try:
        auth_service.change_password(
            user["id"], payload.old_password, payload.new_password
        )
        return {"result": "success"}
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc


@router.put("/auth/users/{user_id}")
async def update_user(
    user_id: str,
    payload: UserUpdateRequest,
    authorization: Optional[str] = Header(None),
):
    current_user = _current_user_from_header(authorization)
    _require_admin(current_user)
    if current_user["id"] == user_id and payload.status == "disabled":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot disable yourself"
        )
    try:
        return {
            "user": auth_service.update_user(
                user_id, payload.role, payload.status, payload.name
            )
        }
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc


@router.post("/auth/users/{user_id}/reset-password")
async def reset_user_password(
    user_id: str,
    payload: PasswordResetRequest,
    authorization: Optional[str] = Header(None),
):
    current_user = _current_user_from_header(authorization)
    _require_admin(current_user)
    try:
        return {"user": auth_service.reset_password(user_id, payload.new_password)}
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
