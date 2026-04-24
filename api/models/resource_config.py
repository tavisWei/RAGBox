from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class ResourceLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ResourceConfig(Base):
    __tablename__ = "resource_configs"

    id = Column(UUID(as_uuid=True), primary_key=True)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    level = Column(String(20), nullable=False)
    data_store_type = Column(String(50), nullable=False)
    config_json = Column(JSON, default=dict)
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    dataset_bindings = relationship("DatasetResourceBinding", back_populates="resource_config")


class DatasetResourceBinding(Base):
    __tablename__ = "dataset_resource_bindings"

    id = Column(UUID(as_uuid=True), primary_key=True)
    dataset_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    resource_config_id = Column(UUID(as_uuid=True), ForeignKey("resource_configs.id"), nullable=False)
    status = Column(String(20), default="active")
    last_rebuild_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    resource_config = relationship("ResourceConfig", back_populates="dataset_bindings")


class RetrievalMetrics(Base):
    __tablename__ = "retrieval_metrics"

    id = Column(UUID(as_uuid=True), primary_key=True)
    dataset_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    query_latency_ms = Column(Integer, nullable=False)
    result_count = Column(Integer, nullable=False)
    retrieval_method = Column(String(50), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
