from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class DatasourceType(str, Enum):
    FILE = "file"
    URL = "url"
    NOTION = "notion"


class ExtractSetting(BaseModel):
    model_config = ConfigDict(extra="forbid")

    datasource_type: DatasourceType
    file_path: Optional[str] = None
    url: Optional[str] = None
    notion_page_id: Optional[str] = None
    encoding: str = "utf-8"
    extract_images: bool = False
    max_file_size_mb: int = 100

    @field_validator("max_file_size_mb")
    @classmethod
    def validate_max_file_size(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("max_file_size_mb must be positive")
        return value

    def get_source_identifier(self) -> Optional[str]:
        if self.datasource_type == DatasourceType.FILE:
            return self.file_path
        elif self.datasource_type == DatasourceType.URL:
            return self.url
        elif self.datasource_type == DatasourceType.NOTION:
            return self.notion_page_id
        return None
