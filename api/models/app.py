from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import uuid4

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from api.models.resource_config import Base


class AppMode(str, Enum):
    """Application mode enum matching Dify's app types"""

    CHAT = "chat"
    COMPLETION = "completion"
    AGENT = "agent"
    WORKFLOW = "workflow"


class App(Base):
    """Application model for Dify-style app management"""

    __tablename__ = "apps"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    icon = Column(String(255), nullable=True)
    icon_background = Column(String(255), nullable=True)
    mode = Column(String(20), nullable=False, default=AppMode.CHAT.value)

    # Model configuration
    model_config = Column(JSON, default=dict)

    # Feature flags
    enable_site = Column(Boolean, default=False)
    enable_api = Column(Boolean, default=True)

    # Site configuration
    site_config = Column(JSON, default=dict)

    # API configuration
    api_config = Column(JSON, default=dict)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    conversations = relationship(
        "Conversation", back_populates="app", cascade="all, delete-orphan"
    )


class AppSiteConfig(Base):
    """Site-specific configuration for public apps"""

    __tablename__ = "app_site_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    app_id = Column(
        UUID(as_uuid=True),
        ForeignKey("apps.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    # Site settings
    title = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    copyright = Column(String(255), nullable=True)
    privacy_policy = Column(String(255), nullable=True)

    # Custom domain
    custom_domain = Column(String(255), nullable=True)

    # Theme settings
    theme = Column(JSON, default=dict)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    app = relationship("App", backref="site_config_detail")
