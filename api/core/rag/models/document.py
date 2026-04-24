from __future__ import annotations

from typing import Any, List, Optional, Dict
from pydantic import BaseModel, Field


class ChildDocument(BaseModel):
    page_content: str
    vector: Optional[List[float]] = None
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class AttachmentDocument(BaseModel):
    page_content: str
    provider: Optional[str] = "dify"
    vector: Optional[List[float]] = None
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class Document(BaseModel):
    page_content: str
    vector: Optional[List[float]] = None
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    provider: Optional[str] = "dify"
    children: Optional[List[ChildDocument]] = None
    attachments: Optional[List[AttachmentDocument]] = None
