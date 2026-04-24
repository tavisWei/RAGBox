from enum import Enum


class DatasourceType(str, Enum):
    FILE = "file"
    URL = "url"
    NOTION = "notion"
