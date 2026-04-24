"""Dataset (Knowledge Base) model for RAG platform.

This model represents a knowledge base/dataset that contains documents
and their segments for retrieval-augmented generation.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import uuid4

from sqlalchemy import Boolean, Column, DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from api.models.resource_config import Base


class DatasetPermission(str, Enum):
    """Permission level for dataset access."""

    ONLY_ME = "only_me"
    ALL_TEAM = "all_team_members"
    PARTIAL_TEAM = "partial_members"


class IndexingTechnique(str, Enum):
    """Indexing technique for the dataset."""

    HIGH_QUALITY = "high_quality"
    ECONOMY = "economy"


class Dataset(Base):
    """Dataset model representing a knowledge base.

    A dataset contains documents that can be indexed and searched.
    Each dataset belongs to a tenant and has configurable retrieval settings.
    """

    __tablename__ = "datasets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Provider and permission
    provider = Column(String(255), default="vendor")
    permission = Column(String(50), default=DatasetPermission.ONLY_ME.value)

    # Indexing configuration
    indexing_technique = Column(String(50), nullable=True)
    index_struct = Column(Text, nullable=True)

    # Embedding configuration
    embedding_model = Column(String(255), nullable=True)
    embedding_model_provider = Column(String(255), nullable=True)

    # Retrieval configuration
    retrieval_model = Column(Text, nullable=True)  # JSON stored as text

    # Creator info
    created_by = Column(UUID(as_uuid=True), nullable=False)
    updated_by = Column(UUID(as_uuid=True), nullable=True)

    # Feature flags
    enabled = Column(Boolean, default=True)
    enable_api = Column(Boolean, default=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    documents = relationship(
        "Document", back_populates="dataset", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Dataset(id={self.id}, name={self.name})>"

    def to_dict(self) -> dict:
        """Convert dataset to dictionary representation."""
        return {
            "id": str(self.id),
            "tenant_id": str(self.tenant_id),
            "name": self.name,
            "description": self.description,
            "provider": self.provider,
            "permission": self.permission,
            "indexing_technique": self.indexing_technique,
            "embedding_model": self.embedding_model,
            "embedding_model_provider": self.embedding_model_provider,
            "enabled": self.enabled,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
