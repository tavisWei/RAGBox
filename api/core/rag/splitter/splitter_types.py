from enum import Enum
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field


class SplitterType(str, Enum):
    RECURSIVE = "recursive"
    TOKEN = "token"
    SENTENCE = "sentence"
    MARKDOWN = "markdown"
    CODE = "code"
    SEMANTIC = "semantic"
    PARENT_CHILD = "parent_child"
    CHINESE = "chinese"


@dataclass
class SplitterConfig:
    chunk_size: int = 512
    chunk_overlap: int = 64
    separators: Optional[List[str]] = None
    keep_separator: bool = True
    length_function: Callable[[str], int] = len
    model_name: Optional[str] = None
    embedding_model: Optional[str] = None
    parent_chunk_size: int = 2048
    child_chunk_size: int = 256
    language: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
