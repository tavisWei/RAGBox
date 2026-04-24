from typing import Dict, Generator, Optional

from fastapi import Header, HTTPException, status

from api.services.auth_service import auth_service


def get_current_user(authorization: Optional[str] = Header(None)) -> Dict:
    if authorization is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    token = authorization.replace("Bearer ", "")
    user = auth_service.get_user_by_token(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
        )
    return user


def get_db() -> Generator:
    yield None
