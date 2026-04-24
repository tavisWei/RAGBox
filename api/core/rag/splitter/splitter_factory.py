from typing import Optional, Dict, Any
from .splitter_types import SplitterType, SplitterConfig
from .base_splitter import BaseTextSplitter
from .chinese_text_splitter import ChineseTextSplitter
from .token_text_splitter import TokenTextSplitter
from .sentence_text_splitter import SentenceTextSplitter
from .markdown_text_splitter import MarkdownTextSplitter
from .code_text_splitter import CodeAwareTextSplitter
from .semantic_text_splitter import SemanticTextSplitter
from .parent_child_text_splitter import ParentChildTextSplitter


class SplitterFactory:
    _registry: Dict[SplitterType, type] = {
        SplitterType.RECURSIVE: ChineseTextSplitter,
        SplitterType.CHINESE: ChineseTextSplitter,
        SplitterType.TOKEN: TokenTextSplitter,
        SplitterType.SENTENCE: SentenceTextSplitter,
        SplitterType.MARKDOWN: MarkdownTextSplitter,
        SplitterType.CODE: CodeAwareTextSplitter,
        SplitterType.SEMANTIC: SemanticTextSplitter,
        SplitterType.PARENT_CHILD: ParentChildTextSplitter,
    }

    @classmethod
    def create(
        cls,
        splitter_type: SplitterType,
        config: Optional[SplitterConfig] = None,
        **kwargs: Any,
    ) -> BaseTextSplitter:
        if splitter_type not in cls._registry:
            raise ValueError(f"Unknown splitter type: {splitter_type}")
        splitter_class = cls._registry[splitter_type]
        if config is None:
            config = SplitterConfig(**kwargs)
        return splitter_class(config=config, **kwargs)

    @classmethod
    def create_from_dict(cls, config_dict: Dict[str, Any]) -> BaseTextSplitter:
        config_copy = config_dict.copy()
        splitter_type = SplitterType(config_copy.pop("type"))
        config = SplitterConfig(**config_copy)
        return cls.create(splitter_type, config)

    @classmethod
    def register(cls, splitter_type: SplitterType, splitter_class: type) -> None:
        cls._registry[splitter_type] = splitter_class

    @classmethod
    def list_available(cls) -> list:
        return list(cls._registry.keys())
