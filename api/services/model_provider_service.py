from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from .local_store import LocalStore


PROVIDER_CATALOG: Dict[str, Dict[str, Any]] = {
    "openai": {
        "label": "OpenAI",
        "models": [
            {"id": "gpt-4o-mini", "name": "gpt-4o-mini"},
            {"id": "gpt-4.1", "name": "gpt-4.1"},
            {"id": "gpt-3.5-turbo", "name": "gpt-3.5-turbo"},
        ],
        "fields": ["api_key", "base_url"],
        "supports_validate": True,
    },
    "anthropic": {
        "label": "Anthropic",
        "models": [
            {"id": "claude-3-5-sonnet", "name": "claude-3-5-sonnet"},
            {"id": "claude-3-7-sonnet", "name": "claude-3-7-sonnet"},
        ],
        "fields": ["api_key", "base_url"],
        "supports_validate": True,
    },
    "ollama": {
        "label": "Ollama",
        "models": [
            {"id": "llama3.1", "name": "llama3.1"},
            {"id": "qwen2.5", "name": "qwen2.5"},
            {"id": "mistral", "name": "mistral"},
        ],
        "fields": ["base_url"],
        "supports_validate": True,
    },
    "openrouter": {
        "label": "OpenRouter",
        "models": [
            {"id": "openai/gpt-4o-mini", "name": "openai/gpt-4o-mini"},
            {
                "id": "anthropic/claude-3.5-sonnet",
                "name": "anthropic/claude-3.5-sonnet",
            },
        ],
        "fields": ["api_key", "base_url"],
        "supports_validate": True,
    },
}


class ModelProviderService:
    def __init__(self) -> None:
        self.store = LocalStore("model_providers.json")
        self._ensure_defaults()

    def _ensure_defaults(self) -> None:
        data = self.store.read()
        if data:
            return
        self.store.write({"providers": {}, "active": {}, "default_model": {}})

    def list_providers(self) -> List[Dict[str, Any]]:
        data = self.store.read()
        catalog = self._provider_catalog(data)
        providers = data.get("providers", {})
        active = data.get("active", {})
        default_model = data.get("default_model", {})
        result = []
        for key, meta in catalog.items():
            credentials = [
                self._public_credential(item) for item in providers.get(key, [])
            ]
            result.append(
                {
                    "provider": key,
                    "label": meta["label"],
                    "models": self._normalize_models(meta["models"]),
                    "fields": meta["fields"],
                    "supports_validate": meta["supports_validate"],
                    "credentials": credentials,
                    "active_credential_id": active.get(key),
                    "default_model": default_model.get(key),
                    "editable": True,
                }
            )
        return result

    def create_provider(
        self,
        provider: str,
        label: str,
        models: List[Any],
        fields: List[str],
        supports_validate: bool = True,
        credentials: Optional[Dict[str, Any]] = None,
        credential_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        key = provider.strip().lower()
        if not key:
            raise ValueError("Provider key is required")
        data = self.store.read()
        custom = data.setdefault("custom_providers", {})
        deleted = data.setdefault("deleted_providers", [])
        if key in self._provider_catalog(data) and key not in deleted:
            raise ValueError("Provider already exists")
        if key in deleted:
            deleted.remove(key)
        custom[key] = {
            "label": label,
            "models": self._normalize_models(models),
            "fields": fields,
            "supports_validate": supports_validate,
            "editable": True,
        }
        data.setdefault("providers", {}).setdefault(key, [])
        self.store.write(data)
        if credentials:
            self.create_credential(
                key, credentials, credential_name or f"{label}-default"
            )
        return {"provider": key, **custom[key]}

    def update_provider(
        self,
        provider: str,
        label: str,
        models: List[Any],
        fields: List[str],
        supports_validate: bool = True,
    ) -> Dict[str, Any]:
        data = self.store.read()
        custom = data.setdefault("custom_providers", {})
        if provider not in self._provider_catalog(data):
            raise ValueError("Provider not found")
        if provider not in custom and provider in PROVIDER_CATALOG:
            custom[provider] = dict(PROVIDER_CATALOG[provider])
        custom[provider].update(
            {
                "label": label,
                "models": self._normalize_models(models),
                "fields": fields,
                "supports_validate": supports_validate,
                "editable": True,
            }
        )
        self.store.write(data)
        return {"provider": provider, **custom[provider]}

    def delete_provider(self, provider: str) -> None:
        data = self.store.read()
        custom = data.setdefault("custom_providers", {})
        if provider not in self._provider_catalog(data):
            raise ValueError("Provider not found")
        custom.pop(provider, None)
        if provider in PROVIDER_CATALOG:
            deleted = data.setdefault("deleted_providers", [])
            if provider not in deleted:
                deleted.append(provider)
        data.setdefault("providers", {}).pop(provider, None)
        data.setdefault("active", {}).pop(provider, None)
        data.setdefault("default_model", {}).pop(provider, None)
        self.store.write(data)

    def add_model(self, provider: str, model_id: str, name: str) -> None:
        data = self.store.read()
        catalog = data.setdefault("custom_providers", {})
        if provider in PROVIDER_CATALOG and provider not in catalog:
            catalog[provider] = dict(PROVIDER_CATALOG[provider])
            catalog[provider]["editable"] = True
        meta = catalog.get(provider)
        if not meta:
            raise ValueError("Provider not found")
        models = self._normalize_models(meta.setdefault("models", []))
        if not any(item["id"] == model_id for item in models):
            models.append({"id": model_id, "name": name})
        meta["models"] = models
        self.store.write(data)

    def update_model(
        self, provider: str, old_model: str, new_model: str, name: str
    ) -> None:
        data = self.store.read()
        catalog = data.setdefault("custom_providers", {})
        if provider in PROVIDER_CATALOG and provider not in catalog:
            catalog[provider] = dict(PROVIDER_CATALOG[provider])
            catalog[provider]["editable"] = True
        meta = catalog.get(provider)
        if not meta:
            raise ValueError("Provider not found")
        models = self._normalize_models(meta.setdefault("models", []))
        if not any(item["id"] == old_model for item in models):
            raise ValueError("Model not found")
        for item in models:
            if item["id"] == old_model:
                item["id"] = new_model
                item["name"] = name
                break
        meta["models"] = models
        if data.setdefault("default_model", {}).get(provider) == old_model:
            data["default_model"][provider] = new_model
        self.store.write(data)

    def delete_model(self, provider: str, model: str) -> None:
        data = self.store.read()
        catalog = data.setdefault("custom_providers", {})
        if provider in PROVIDER_CATALOG and provider not in catalog:
            catalog[provider] = dict(PROVIDER_CATALOG[provider])
            catalog[provider]["editable"] = True
        meta = catalog.get(provider)
        if not meta:
            raise ValueError("Provider not found")
        models = self._normalize_models(meta.setdefault("models", []))
        meta["models"] = [item for item in models if item["id"] != model]
        if data.setdefault("default_model", {}).get(provider) == model:
            data["default_model"].pop(provider, None)
        self.store.write(data)

    def create_credential(
        self, provider: str, credentials: Dict[str, Any], name: Optional[str] = None
    ) -> Dict[str, Any]:
        if provider not in self._provider_catalog(self.store.read()):
            raise ValueError("Provider not found")
        data = self.store.read()
        providers = data.setdefault("providers", {})
        credentials_list = providers.setdefault(provider, [])
        credential_id = str(uuid4())
        record = {
            "id": credential_id,
            "name": name or f"{provider}-credential",
            "credentials": credentials,
            "created_at": datetime.utcnow().isoformat(),
        }
        credentials_list.append(record)
        if provider not in data.setdefault("active", {}):
            data["active"][provider] = credential_id
        self.store.write(data)
        return record

    def update_credential(
        self,
        provider: str,
        credential_id: str,
        credentials: Dict[str, Any],
        name: Optional[str] = None,
    ) -> Dict[str, Any]:
        data = self.store.read()
        credentials_list = data.get("providers", {}).get(provider, [])
        for item in credentials_list:
            if item["id"] == credential_id:
                item["credentials"] = credentials
                if name is not None:
                    item["name"] = name
                self.store.write(data)
                return item
        raise ValueError("Credential not found")

    def delete_credential(self, provider: str, credential_id: str) -> None:
        data = self.store.read()
        credentials_list = data.get("providers", {}).get(provider, [])
        filtered = [item for item in credentials_list if item["id"] != credential_id]
        data.setdefault("providers", {})[provider] = filtered
        if data.setdefault("active", {}).get(provider) == credential_id:
            data["active"][provider] = filtered[0]["id"] if filtered else None
        self.store.write(data)

    def switch_active(self, provider: str, credential_id: str) -> None:
        data = self.store.read()
        credentials_list = data.get("providers", {}).get(provider, [])
        if not any(item["id"] == credential_id for item in credentials_list):
            raise ValueError("Credential not found")
        data.setdefault("active", {})[provider] = credential_id
        self.store.write(data)

    def set_default_model(self, provider: str, model: str) -> None:
        data = self.store.read()
        data.setdefault("default_model", {})[provider] = model
        self.store.write(data)

    def validate_credentials(
        self, provider: str, credentials: Dict[str, Any]
    ) -> Dict[str, Any]:
        required_fields = (
            self._provider_catalog(self.store.read())
            .get(provider, {})
            .get("fields", [])
        )
        missing = [field for field in required_fields if not credentials.get(field)]
        if missing:
            return {"result": "error", "error": f"Missing fields: {', '.join(missing)}"}
        return {"result": "success"}

    def get_active_provider_config(self, provider: str) -> Optional[Dict[str, Any]]:
        data = self.store.read()
        active_id = data.get("active", {}).get(provider)
        credentials_list = data.get("providers", {}).get(provider, [])
        for item in credentials_list:
            if item["id"] == active_id:
                return {
                    "provider": provider,
                    "credentials": item["credentials"],
                    "model": data.get("default_model", {}).get(provider),
                }
        return None

    def _public_credential(self, credential: Dict[str, Any]) -> Dict[str, Any]:
        public = dict(credential)
        masked = dict(public.get("credentials", {}))
        if masked.get("api_key"):
            masked["api_key"] = "********"
        public["credentials"] = masked
        return public

    def _provider_catalog(self, data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        catalog = {key: dict(value) for key, value in PROVIDER_CATALOG.items()}
        for key, value in data.get("custom_providers", {}).items():
            catalog[key] = dict(value)
        for key in data.get("deleted_providers", []):
            catalog.pop(key, None)
        return catalog

    def _normalize_models(self, models: List[Any]) -> List[Dict[str, str]]:
        normalized: List[Dict[str, str]] = []
        for item in models:
            if isinstance(item, dict):
                model_id = str(item.get("id") or item.get("model_id") or "").strip()
                name = str(item.get("name") or model_id).strip()
            else:
                model_id = str(item).strip()
                name = model_id
            if model_id:
                normalized.append({"id": model_id, "name": name or model_id})
        return normalized


model_provider_service = ModelProviderService()
