from __future__ import annotations

from enum import Enum
from typing import List, Optional
from typing_extensions import Literal
from pydantic import BaseModel


class ParentMode(str, Enum):
    FULL_DOC = "full-doc"
    PARAGRAPH = "paragraph"


class PreProcessingRule(BaseModel):
    id: str
    enabled: bool


class Segmentation(BaseModel):
    separator: str = "\n"
    max_tokens: int
    chunk_overlap: int = 0


class Rule(BaseModel):
    pre_processing_rules: Optional[List[PreProcessingRule]] = None
    segmentation: Optional[Segmentation] = None
    parent_mode: Optional[Literal["full-doc", "paragraph"]] = None
    subchunk_segmentation: Optional[Segmentation] = None
