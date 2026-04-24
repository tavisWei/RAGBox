from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from .local_store import LocalStore


class AuthService:
    def __init__(self) -> None:
        self.user_store = LocalStore("users.json")
        self.session_store = LocalStore("sessions.json")
        self._ensure_seed_admin()

    def _ensure_seed_admin(self) -> None:
        users = self.user_store.read()
        if users:
            return
        user_id = str(uuid4())
        users[user_id] = {
            "id": user_id,
            "email": "admin@example.com",
            "username": "admin",
            "password_hash": self._hash_password("admin"),
            "role": "owner",
            "name": "Administrator",
            "created_at": datetime.utcnow().isoformat(),
        }
        self.user_store.write(users)

    def register(
        self, email: str, password: str, username: Optional[str] = None
    ) -> Dict[str, Any]:
        users = self.user_store.read()
        normalized_email = email.strip().lower()
        for user in users.values():
            if user["email"] == normalized_email:
                raise ValueError("Email already registered")

        user_id = str(uuid4())
        user = {
            "id": user_id,
            "email": normalized_email,
            "username": username or normalized_email.split("@")[0],
            "password_hash": self._hash_password(password),
            "role": "member",
            "name": username or normalized_email.split("@")[0],
            "chat_context": {},
            "created_at": datetime.utcnow().isoformat(),
        }
        users[user_id] = user
        self.user_store.write(users)
        return self._public_user(user)

    def login(self, identifier: str, password: str) -> Tuple[str, Dict[str, Any]]:
        users = self.user_store.read()
        lookup = identifier.strip().lower()
        matched = None
        for user in users.values():
            if user["email"] == lookup or user["username"] == identifier:
                matched = user
                break

        if (
            not matched
            or matched.get("status", "active") != "active"
            or matched["password_hash"] != self._hash_password(password)
        ):
            raise ValueError("Invalid credentials")

        token = secrets.token_urlsafe(32)
        sessions = self.session_store.read()
        sessions[token] = {
            "token": token,
            "user_id": matched["id"],
            "created_at": datetime.utcnow().isoformat(),
            "expires_at": (datetime.utcnow() + timedelta(days=7)).isoformat(),
        }
        self.session_store.write(sessions)
        return token, self._public_user(matched)

    def logout(self, token: str) -> None:
        sessions = self.session_store.read()
        if token in sessions:
            del sessions[token]
            self.session_store.write(sessions)

    def get_user_by_token(self, token: str) -> Optional[Dict[str, Any]]:
        sessions = self.session_store.read()
        session = sessions.get(token)
        if not session:
            return None
        expires_at = datetime.fromisoformat(session["expires_at"])
        if expires_at < datetime.utcnow():
            del sessions[token]
            self.session_store.write(sessions)
            return None
        users = self.user_store.read()
        user = users.get(session["user_id"])
        if not user:
            return None
        return self._public_user(user)

    def list_users(self) -> List[Dict[str, Any]]:
        users = self.user_store.read()
        return [self._public_user(user) for user in users.values()]

    def change_password(
        self, user_id: str, old_password: str, new_password: str
    ) -> None:
        users = self.user_store.read()
        user = users.get(user_id)
        if not user:
            raise ValueError("User not found")
        if user["password_hash"] != self._hash_password(old_password):
            raise ValueError("Old password is incorrect")
        user["password_hash"] = self._hash_password(new_password)
        self.user_store.write(users)

    def reset_password(self, user_id: str, new_password: str) -> Dict[str, Any]:
        users = self.user_store.read()
        user = users.get(user_id)
        if not user:
            raise ValueError("User not found")
        user["password_hash"] = self._hash_password(new_password)
        self.user_store.write(users)
        return self._public_user(user)

    def update_user(
        self,
        user_id: str,
        role: Optional[str] = None,
        status: Optional[str] = None,
        name: Optional[str] = None,
    ) -> Dict[str, Any]:
        users = self.user_store.read()
        user = users.get(user_id)
        if not user:
            raise ValueError("User not found")
        if role is not None:
            if role not in {"owner", "admin", "member"}:
                raise ValueError("Invalid role")
            user["role"] = role
        if status is not None:
            if status not in {"active", "disabled"}:
                raise ValueError("Invalid status")
            user["status"] = status
        if name is not None:
            user["name"] = name
        self.user_store.write(users)
        return self._public_user(user)

    def update_chat_context(
        self,
        user_id: str,
        app_id: Optional[str] = None,
        role_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        users = self.user_store.read()
        user = users.get(user_id)
        if not user:
            raise ValueError("User not found")
        user["chat_context"] = {
            "app_id": app_id or None,
            "role_id": role_id or None,
            "conversation_id": conversation_id or None,
            "updated_at": datetime.utcnow().isoformat(),
        }
        self.user_store.write(users)
        return self._public_user(user)

    def _hash_password(self, password: str) -> str:
        return hashlib.sha256(password.encode("utf-8")).hexdigest()

    def _public_user(self, user: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": user["id"],
            "email": user["email"],
            "username": user["username"],
            "name": user.get("name") or user["username"],
            "role": user.get("role", "member"),
            "status": user.get("status", "active"),
            "chat_context": user.get("chat_context") or {},
        }


auth_service = AuthService()
