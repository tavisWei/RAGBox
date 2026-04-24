import tempfile
from pathlib import Path
from typing import List, Union
from api.core.rag.extractor.entity.datasource_type import DatasourceType
from api.core.rag.extractor.entity.extract_setting import ExtractSetting
from api.core.rag.models.document import Document


class ExtractProcessor:
    @classmethod
    def extract(
        cls, extract_setting: ExtractSetting, is_automatic: bool = False
    ) -> List[Document]:
        if extract_setting.datasource_type == DatasourceType.FILE:
            return cls._extract_from_file(extract_setting, is_automatic)
        elif extract_setting.datasource_type == DatasourceType.URL:
            return cls._extract_from_url(extract_setting)
        return []

    @classmethod
    def _extract_from_file(
        cls, extract_setting: ExtractSetting, is_automatic: bool
    ) -> List[Document]:
        return []

    @classmethod
    def _extract_from_url(cls, extract_setting: ExtractSetting) -> List[Document]:
        return []
