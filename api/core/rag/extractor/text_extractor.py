from typing import List
from api.core.rag.extractor.extractor_base import BaseExtractor
from api.core.rag.models.document import Document


class TextExtractor(BaseExtractor):
    def __init__(self, file_path: str):
        self._file_path = file_path

    def extract(self) -> List[Document]:
        with open(self._file_path, "r", encoding="utf-8") as f:
            text = f.read()
        return [Document(page_content=text)]
