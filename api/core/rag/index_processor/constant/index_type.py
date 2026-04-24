from enum import Enum


class IndexStructureType(str, Enum):
    PARAGRAPH_INDEX = "paragraph_index"
    PARENT_CHILD_INDEX = "parent_child_index"
    QA_INDEX = "qa_index"


class IndexTechniqueType(str, Enum):
    HIGH_QUALITY = "high_quality"
    ECONOMY = "economy"
