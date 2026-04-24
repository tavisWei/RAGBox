from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import uuid4

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from api.models.resource_config import Base


class MessageStatus(str, Enum):
    """Message status enum"""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Conversation(Base):
    """Conversation model for managing chat sessions"""

    __tablename__ = "conversations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    app_id = Column(
        UUID(as_uuid=True),
        ForeignKey("apps.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    # Conversation metadata
    name = Column(String(255), nullable=True)
    summary = Column(Text, nullable=True)

    # Conversation state
    inputs = Column(JSON, default=dict)
    system_prompt = Column(Text, nullable=True)
    conversation_context = Column(JSON, default=dict)

    # Status
    status = Column(String(20), default="active")

    # Message count
    message_count = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    app = relationship("App", back_populates="conversations")
    messages = relationship(
        "Message", back_populates="conversation", cascade="all, delete-orphan"
    )


class Message(Base):
    """Message model for conversation messages"""

    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    conversation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Message content
    query = Column(Text, nullable=False)
    answer = Column(Text, nullable=True)

    # Message metadata
    message_metadata = Column(JSON, default=dict)

    # Token usage
    query_token_count = Column(Integer, default=0)
    answer_token_count = Column(Integer, default=0)
    total_token_count = Column(Integer, default=0)

    # Message status
    status = Column(String(20), default=MessageStatus.COMPLETED.value)
    error_message = Column(Text, nullable=True)

    # Message type (user/assistant/system)
    message_type = Column(String(20), default="user")

    # Parent message for threading
    parent_message_id = Column(UUID(as_uuid=True), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    conversation = relationship("Conversation", back_populates="messages")
    message_annotations = relationship(
        "MessageAnnotation", back_populates="message", cascade="all, delete-orphan"
    )


class MessageAnnotation(Base):
    """Message annotation for feedback and corrections"""

    __tablename__ = "message_annotations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    message_id = Column(
        UUID(as_uuid=True),
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Annotation content
    content = Column(Text, nullable=False)

    # Annotation type (feedback/correction/rating)
    annotation_type = Column(String(20), default="feedback")

    # Rating (for rating type)
    rating = Column(Integer, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    message = relationship("Message", back_populates="message_annotations")
