from __future__ import annotations

from pydantic import BaseModel, Field


class RerankingModelConfig(BaseModel):
    reranking_provider_name: str = Field(validation_alias="provider")
    reranking_model_name: str = Field(validation_alias="model")

    @property
    def provider(self) -> str:
        return self.reranking_provider_name

    @property
    def model(self) -> str:
        return self.reranking_model_name


class VectorSetting(BaseModel):
    vector_weight: float
    embedding_provider_name: str
    embedding_model_name: str


class KeywordSetting(BaseModel):
    keyword_weight: float


class WeightedScoreConfig(BaseModel):
    vector_setting: VectorSetting
    keyword_setting: KeywordSetting
