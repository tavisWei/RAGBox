from __future__ import annotations

import logging
from typing import List

from api.core.rag.extractor.base_extractor import (
    BaseExtractor,
    Document,
    FileValidationError,
)
from api.core.rag.extractor.entities.extract_setting import ExtractSetting

logger = logging.getLogger(__name__)


class ExcelExtractor(BaseExtractor):
    def __init__(self, file_path: str):
        self._file_path = file_path

    def supported_formats(self) -> list[str]:
        return [".xlsx", ".xls"]

    def extract(self, extract_setting: ExtractSetting | None = None) -> List[Document]:
        self.validate_file(self._file_path)

        try:
            import pandas as pd
        except ImportError:
            raise FileValidationError(
                "pandas is required for Excel extraction. Install it with: pip install pandas"
            )

        documents: List[Document] = []
        try:
            xl = pd.ExcelFile(self._file_path)
        except Exception as e:
            raise FileValidationError(f"Failed to read Excel file: {e}")

        for sheet_name in xl.sheet_names:
            try:
                df = xl.parse(sheet_name)
            except Exception as e:
                logger.warning(f"Failed to parse sheet '{sheet_name}': {e}")
                continue

            for idx, row in df.iterrows():
                row_dict = row.to_dict()
                parts = []
                for col, val in row_dict.items():
                    if pd.isna(val):
                        val = ""
                    parts.append(f"{col}: {val}")
                page_content = "\n".join(parts)
                documents.append(
                    Document(
                        page_content=page_content,
                        metadata={
                            "source": self._file_path,
                            "sheet_name": sheet_name,
                            "row_index": int(idx),
                            "total_rows": len(df),
                            "columns": list(df.columns),
                        },
                    )
                )

        return documents
