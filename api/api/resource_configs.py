from typing import List
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.services.local_store import LocalStore
from .deps import get_current_user

router = APIRouter()

_store = LocalStore("resource_configs.json")


class ResourceConfigCreate(BaseModel):
    name: str
    config_type: str
    settings: dict


class ResourceConfigOut(BaseModel):
    id: str
    name: str
    config_type: str
    settings: dict


class ResourceConfigUpdate(BaseModel):
    name: str
    config_type: str
    settings: dict


def _default_configs():
    return {
        "low-default": {
            "id": "low-default",
            "name": "轻量起步资源",
            "config_type": "low",
            "settings": {
                "data_store_type": "sqlite",
                "max_documents": 10000,
                "embedding_provider": "ollama",
                "embedding_model": "nomic-embed-text",
                "chunk_size": 400,
                "chunk_overlap": 50,
                "vector_enabled": True,
                "keyword_enabled": True,
                "fulltext_enabled": True,
                "rerank_enabled": False,
                "recommended_retrieval": {
                    "methods": ["fulltext", "keyword"],
                    "top_k": 5,
                    "fusion_mode": "simple",
                    "query_expansion": "none",
                    "rerank_mode": "none",
                },
            },
        },
        "medium-default": {
            "id": "medium-default",
            "name": "团队标准资源",
            "config_type": "medium",
            "settings": {
                "data_store_type": "pgvector",
                "max_documents": 1000000,
                "embedding_provider": "openai",
                "embedding_model": "text-embedding-3-small",
                "chunk_size": 500,
                "chunk_overlap": 100,
                "vector_enabled": True,
                "keyword_enabled": True,
                "fulltext_enabled": True,
                "rerank_enabled": True,
                "recommended_retrieval": {
                    "methods": ["hybrid"],
                    "top_k": 10,
                    "fusion_mode": "rrf",
                    "query_expansion": "multi_query",
                    "rerank_mode": "cross_encoder",
                },
            },
        },
        "high-default": {
            "id": "high-default",
            "name": "企业增强资源",
            "config_type": "high",
            "settings": {
                "data_store_type": "elasticsearch",
                "max_documents": 100000000,
                "embedding_provider": "openai",
                "embedding_model": "text-embedding-3-large",
                "chunk_size": 1200,
                "chunk_overlap": 120,
                "vector_enabled": True,
                "keyword_enabled": True,
                "fulltext_enabled": True,
                "rerank_enabled": True,
                "recommended_retrieval": {
                    "methods": ["hybrid", "semantic", "fulltext"],
                    "top_k": 20,
                    "fusion_mode": "weighted",
                    "query_expansion": "hyde",
                    "rerank_mode": "llm_listwise",
                },
            },
        },
    }


def _read_configs():
    data = _store.read()
    if not data.get("configs"):
        data = {"configs": _default_configs()}
        _store.write(data)
    return data


@router.get("/resource-configs", response_model=List[ResourceConfigOut])
async def list_resource_configs(user: dict = Depends(get_current_user)):
    data = _read_configs()
    return [ResourceConfigOut(**item) for item in data["configs"].values()]


@router.post("/resource-configs", response_model=ResourceConfigOut)
async def create_resource_config(
    payload: ResourceConfigCreate, user: dict = Depends(get_current_user)
):
    data = _read_configs()
    config_id = str(uuid4())
    record = {
        "id": config_id,
        "name": payload.name,
        "config_type": payload.config_type,
        "settings": payload.settings,
    }
    data["configs"][config_id] = record
    _store.write(data)
    return ResourceConfigOut(**record)


@router.get("/resource-configs/{config_id}", response_model=ResourceConfigOut)
async def get_resource_config(config_id: str, user: dict = Depends(get_current_user)):
    data = _read_configs()
    record = data["configs"].get(config_id)
    if not record:
        raise HTTPException(status_code=404, detail="Resource config not found")
    return ResourceConfigOut(**record)


@router.put("/resource-configs/{config_id}", response_model=ResourceConfigOut)
async def update_resource_config(
    config_id: str,
    payload: ResourceConfigUpdate,
    user: dict = Depends(get_current_user),
):
    data = _read_configs()
    record = data["configs"].get(config_id)
    if not record:
        raise HTTPException(status_code=404, detail="Resource config not found")

    updated = {
        "id": config_id,
        "name": payload.name,
        "config_type": payload.config_type,
        "settings": payload.settings,
    }
    data["configs"][config_id] = updated
    _store.write(data)
    return ResourceConfigOut(**updated)


@router.delete("/resource-configs/{config_id}")
async def delete_resource_config(
    config_id: str, user: dict = Depends(get_current_user)
):
    data = _read_configs()
    record = data["configs"].get(config_id)
    if not record:
        raise HTTPException(status_code=404, detail="Resource config not found")
    if config_id.endswith("-default"):
        raise HTTPException(
            status_code=400, detail="Default resource config cannot be deleted"
        )

    del data["configs"][config_id]
    _store.write(data)
    return {"success": True}
