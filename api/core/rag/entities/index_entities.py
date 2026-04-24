from __future__ import annotations

from typing_extensions import Literal
from pydantic import BaseModel


class EmbeddingSetting(BaseModel):
    embedding_provider_name: str
    embedding_model_name: str


class EconomySetting(BaseModel):
    keyword_number: int


class IndexMethod(BaseModel):
    indexing_technique: Literal["high_quality", "economy"]
    embedding_setting: EmbeddingSetting
    economy_setting: EconomySetting
