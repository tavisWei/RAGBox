"""Document segment model for RAG platform.

A segment is a chunk of text extracted from a document, used for
indexing and retrieval in the RAG pipeline.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import uuid4

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from api.models.resource_config import Base


class SegmentStatus(str, Enum):
    """Status of segment indexing."""

    WAITING = "waiting"
    INDEXING = "indexing"
    COMPLETED = "completed"
    ERROR = "error"


class DocumentSegment(Base):
    """Document segment model representing a chunk of a document.

    Segments are the atomic units for retrieval. Each segment contains
    a portion of the document's content and can be independently indexed
    and retrieved.
    """

    __tablename__ = "document_segments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    dataset_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    document_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    position = Column(Integer, nullable=False, default=0)
    content = Column(Text, nullable=False)
    word_count = Column(Integer, nullable=True)
    tokens = Column(Integer, nullable=True)

    keywords = Column(Text, nullable=True)
    index_node_id = Column(String(255), nullable=True)
    index_node_hash = Column(String(255), nullable=True)

    hit_count = Column(Integer, default=0)
    enabled = Column(Boolean, default=True)
    disabled_at = Column(DateTime, nullable=True)
    disabled_by = Column(UUID(as_uuid=True), nullable=True)

    status = Column(String(50), default=SegmentStatus.WAITING.value)
    indexing_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    error = Column(Text, nullable=True)
    stopped_at = Column(DateTime, nullable=True)

    created_by = Column(UUID(as_uuid=True), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_by = Column(UUID(as_uuid=True), nullable=True)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    document = relationship("Document", back_populates="segments")

    def __repr__(self) -> str:
        return f"<DocumentSegment(id={self.id}, position={self.position}, status={self.status})>"

    def to_dict(self) -> dict:
        """Convert segment to dictionary representation."""
        return {
            "id": str(self.id),
            "tenant_id": str(self.tenant_id),
            "dataset_id": str(self.dataset_id),
            "document_id": str(self.document_id),
            "position": self.position,
            "content": self.content,
            "word_count": self.word_count,
            "tokens": self.tokens,
            "hit_count": self.hit_count,
            "enabled": self.enabled,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
