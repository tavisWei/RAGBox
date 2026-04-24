"""RAG Platform API - FastAPI Entry Point"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import time

# Import routers
from api.api import (
    auth,
    resource_configs,
    component_configs,
    knowledge_bases,
    retrieval,
    monitoring,
    apps,
    conversations,
    chat_roles,
    model_providers,
    workflows,
    workspace,
)

# Track startup time for uptime calculation
start_time = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    yield


# Create FastAPI app
app = FastAPI(
    title="RAG Platform API",
    version="1.0.0",
    description="RAG-based private knowledge Q&A platform",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers with /api/v1 prefix
app.include_router(auth.router, prefix="/api/v1", tags=["Authentication"])
app.include_router(resource_configs.router, prefix="/api/v1", tags=["Resource Configs"])
app.include_router(
    component_configs.router, prefix="/api/v1", tags=["Component Configs"]
)
app.include_router(knowledge_bases.router, prefix="/api/v1", tags=["Knowledge Bases"])
app.include_router(retrieval.router, prefix="/api/v1", tags=["Retrieval"])
app.include_router(monitoring.router, prefix="/api/v1", tags=["Monitoring"])
app.include_router(apps.router, prefix="/api/v1", tags=["Apps"])
app.include_router(conversations.router, prefix="/api/v1", tags=["Conversations"])
app.include_router(chat_roles.router, prefix="/api/v1", tags=["Chat Roles"])
app.include_router(model_providers.router, prefix="/api/v1", tags=["Model Providers"])
app.include_router(workflows.router, prefix="/api/v1", tags=["Workflows"])
app.include_router(workspace.router, prefix="/api/v1", tags=["Workspace"])


@app.get("/")
async def root():
    return {"message": "RAG Platform API", "version": "1.0.0"}


@app.get("/api/v1/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "uptime_seconds": int(time.time() - start_time),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
