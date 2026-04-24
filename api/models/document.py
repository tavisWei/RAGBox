"""Document model for RAG platform.

A document belongs to a dataset and contains the source content
that will be split into segments for indexing and retrieval.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import uuid4

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from api.models.resource_config import Base


class DataSourceType(str, Enum):
    """Source type for document ingestion."""

    UPLOAD_FILE = "upload_file"
    NOTION_IMPORT = "notion_import"
    WEBSITE_CRAWL = "website_crawl"


class IndexingStatus(str, Enum):
    """Status of document indexing process."""

    WAITING = "waiting"
    PARSING = "parsing"
    CLEANING = "cleaning"
    SPLITTING = "splitting"
    INDEXING = "indexing"
    COMPLETED = "completed"
    ERROR = "error"


class Document(Base):
    """Document model representing a file or content in a dataset.

    A document goes through several processing stages:
    parsing -> cleaning -> splitting -> indexing -> completed
    """

    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    dataset_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    position = Column(Integer, nullable=False, default=0)
    name = Column(String(255), nullable=False)

    data_source_type = Column(String(50), nullable=False)
    data_source_info = Column(Text, nullable=True)

    batch = Column(String(255), nullable=False)

    processing_started_at = Column(DateTime, nullable=True)
    parsing_completed_at = Column(DateTime, nullable=True)
    cleaning_completed_at = Column(DateTime, nullable=True)
    splitting_completed_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    word_count = Column(Integer, nullable=True)
    tokens = Column(Integer, nullable=True)

    indexing_status = Column(String(50), default=IndexingStatus.WAITING.value)
    indexing_latency = Column(Integer, nullable=True)

    enabled = Column(Boolean, default=True)
    disabled_at = Column(DateTime, nullable=True)
    disabled_by = Column(UUID(as_uuid=True), nullable=True)

    archived = Column(Boolean, default=False)
    archived_at = Column(DateTime, nullable=True)
    archived_by = Column(UUID(as_uuid=True), nullable=True)

    is_paused = Column(Boolean, default=False)
    paused_at = Column(DateTime, nullable=True)
    paused_by = Column(UUID(as_uuid=True), nullable=True)

    error = Column(Text, nullable=True)
    stopped_at = Column(DateTime, nullable=True)

    created_by = Column(UUID(as_uuid=True), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    dataset = relationship("Dataset", back_populates="documents")
    segments = relationship(
        "DocumentSegment", back_populates="document", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"<Document(id={self.id}, name={self.name}, status={self.indexing_status})>"
        )

    @property
    def display_status(self) -> str:
        """Get human-readable status for display."""
        if self.indexing_status == IndexingStatus.WAITING.value:
            return "queuing"
        if self.indexing_status in {
            IndexingStatus.PARSING.value,
            IndexingStatus.CLEANING.value,
            IndexingStatus.SPLITTING.value,
            IndexingStatus.INDEXING.value,
        }:
            if self.is_paused:
                return "paused"
            return "indexing"
        if self.indexing_status == IndexingStatus.ERROR.value:
            return "error"
        if self.indexing_status == IndexingStatus.COMPLETED.value:
            if self.archived:
                return "archived"
            if not self.enabled:
                return "disabled"
            return "available"
        return self.indexing_status

    def to_dict(self) -> dict:
        """Convert document to dictionary representation."""
        return {
            "id": str(self.id),
            "tenant_id": str(self.tenant_id),
            "dataset_id": str(self.dataset_id),
            "name": self.name,
            "data_source_type": self.data_source_type,
            "word_count": self.word_count,
            "tokens": self.tokens,
            "indexing_status": self.indexing_status,
            "display_status": self.display_status,
            "enabled": self.enabled,
            "archived": self.archived,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
