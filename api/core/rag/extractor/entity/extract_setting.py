from typing import Optional
from pydantic import BaseModel
from api.core.rag.extractor.entity.datasource_type import DatasourceType


class ExtractSetting(BaseModel):
    datasource_type: DatasourceType
    upload_file: Optional[dict] = None
    document_model: Optional[str] = "text_model"
