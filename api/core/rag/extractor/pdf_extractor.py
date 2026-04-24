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


class PdfExtractor(BaseExtractor):
    def __init__(self, file_path: str):
        self._file_path = file_path

    def supported_formats(self) -> list[str]:
        return [".pdf"]

    def extract(self, extract_setting: ExtractSetting | None = None) -> List[Document]:
        self.validate_file(self._file_path)

        try:
            import pypdfium2 as pdfium
        except ImportError:
            raise FileValidationError(
                "pypdfium2 is required for PDF extraction. Install it with: pip install pypdfium2"
            )

        documents: List[Document] = []
        try:
            pdf = pdfium.PdfDocument(self._file_path)
        except Exception as e:
            raise FileValidationError(f"Failed to open PDF file: {e}")

        try:
            for page_num in range(len(pdf)):
                page = pdf[page_num]
                textpage = page.get_textpage()
                text = textpage.get_text_bounded()
                textpage.close()
                page.close()
                documents.append(
                    Document(
                        page_content=text,
                        metadata={
                            "source": self._file_path,
                            "page": page_num + 1,
                            "total_pages": len(pdf),
                        },
                    )
                )
        finally:
            pdf.close()

        return documents
