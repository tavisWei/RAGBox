from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List

from pydantic import BaseModel, ConfigDict, Field

from api.core.rag.extractor.entities.extract_setting import ExtractSetting

logger = logging.getLogger(__name__)


class Document(BaseModel):
    model_config = ConfigDict(extra="allow")

    page_content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ExtractionError(Exception):
    pass


class UnsupportedFormatError(ExtractionError):
    pass


class FileValidationError(ExtractionError):
    pass


class BaseExtractor(ABC):
    @abstractmethod
    def extract(self, extract_setting: ExtractSetting) -> List[Document]:
        pass

    def supported_formats(self) -> List[str]:
        return []

    def validate_file(self, file_path: str, max_size_mb: int = 100) -> bool:
        path = Path(file_path)

        if not path.exists():
            raise FileValidationError(f"File not found: {file_path}")

        if not path.is_file():
            raise FileValidationError(f"Not a file: {file_path}")

        file_size_bytes = path.stat().st_size
        max_size_bytes = max_size_mb * 1024 * 1024
        if file_size_bytes > max_size_bytes:
            raise FileValidationError(
                f"File size ({file_size_bytes / 1024 / 1024:.1f}MB) "
                f"exceeds limit ({max_size_mb}MB): {file_path}"
            )

        if not os.access(file_path, os.R_OK):
            raise FileValidationError(f"File not readable: {file_path}")

        return True
