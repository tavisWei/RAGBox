"""Unit tests for SplitterFactory."""

import pytest

from api.core.rag.splitter.splitter_factory import SplitterFactory
from api.core.rag.splitter.splitter_types import SplitterType, SplitterConfig
from api.core.rag.splitter.base_splitter import BaseTextSplitter
from api.core.rag.splitter.chinese_text_splitter import ChineseTextSplitter
from api.core.rag.splitter.token_text_splitter import TokenTextSplitter
from api.core.rag.splitter.sentence_text_splitter import SentenceTextSplitter
from api.core.rag.splitter.markdown_text_splitter import MarkdownTextSplitter
from api.core.rag.splitter.code_text_splitter import CodeAwareTextSplitter
from api.core.rag.splitter.semantic_text_splitter import SemanticTextSplitter
from api.core.rag.splitter.parent_child_text_splitter import ParentChildTextSplitter


class TestSplitterFactory:
    """Test SplitterFactory functionality."""

    def test_registry_contains_all_types(self):
        """Should have all splitter types registered."""
        registry = SplitterFactory._registry

        assert SplitterType.CHINESE in registry
        assert SplitterType.TOKEN in registry
        assert SplitterType.SENTENCE in registry
        assert SplitterType.MARKDOWN in registry
        assert SplitterType.CODE in registry
        assert SplitterType.SEMANTIC in registry
        assert SplitterType.PARENT_CHILD in registry

    def test_create_chinese_splitter(self):
        """Should create ChineseTextSplitter."""
        splitter = SplitterFactory.create(SplitterType.CHINESE)

        assert isinstance(splitter, ChineseTextSplitter)

    def test_create_token_splitter(self):
        """Should create TokenTextSplitter."""
        splitter = SplitterFactory.create(SplitterType.TOKEN)

        assert isinstance(splitter, TokenTextSplitter)

    def test_create_sentence_splitter(self):
        """Should create SentenceTextSplitter."""
        splitter = SplitterFactory.create(SplitterType.SENTENCE)

        assert isinstance(splitter, SentenceTextSplitter)

    def test_create_markdown_splitter(self):
        """Should create MarkdownTextSplitter."""
        splitter = SplitterFactory.create(SplitterType.MARKDOWN)

        assert isinstance(splitter, MarkdownTextSplitter)

    def test_create_code_splitter(self):
        """Should create CodeAwareTextSplitter."""
        splitter = SplitterFactory.create(SplitterType.CODE)

        assert isinstance(splitter, CodeAwareTextSplitter)

    def test_create_semantic_splitter(self):
        """Should create SemanticTextSplitter."""
        splitter = SplitterFactory.create(SplitterType.SEMANTIC)

        assert isinstance(splitter, SemanticTextSplitter)

    def test_create_parent_child_splitter(self):
        """Should create ParentChildTextSplitter."""
        splitter = SplitterFactory.create(SplitterType.PARENT_CHILD)

        assert isinstance(splitter, ParentChildTextSplitter)

    def test_create_with_config(self):
        """Should create splitter with custom config."""
        config = SplitterConfig(chunk_size=256, chunk_overlap=32)
        splitter = SplitterFactory.create(SplitterType.CHINESE, config=config)

        assert splitter.config.chunk_size == 256
        assert splitter.config.chunk_overlap == 32

    def test_create_with_kwargs(self):
        """Should create splitter with kwargs."""
        splitter = SplitterFactory.create(
            SplitterType.CODE, chunk_size=128, language="python"
        )

        assert splitter.config.chunk_size == 128
        assert splitter._language == "python"

    def test_create_unknown_type_raises(self):
        """Should raise ValueError for unknown type."""
        with pytest.raises(ValueError, match="Unknown splitter type"):
            SplitterFactory.create("nonexistent")

    def test_create_from_dict(self):
        """Should create splitter from dict config."""
        config_dict = {
            "type": "chinese",
            "chunk_size": 256,
            "chunk_overlap": 32,
        }
        splitter = SplitterFactory.create_from_dict(config_dict)

        assert isinstance(splitter, ChineseTextSplitter)
        assert splitter.config.chunk_size == 256
        assert splitter.config.chunk_overlap == 32

    def test_create_from_dict_token(self):
        """Should create TokenTextSplitter from dict."""
        config_dict = {
            "type": "token",
            "chunk_size": 100,
            "model_name": "gpt-4",
        }
        splitter = SplitterFactory.create_from_dict(config_dict)

        assert isinstance(splitter, TokenTextSplitter)
        assert splitter.config.model_name == "gpt-4"

    def test_create_from_dict_code(self):
        """Should create CodeAwareTextSplitter from dict."""
        config_dict = {
            "type": "code",
            "chunk_size": 200,
            "language": "python",
        }
        splitter = SplitterFactory.create_from_dict(config_dict)

        assert isinstance(splitter, CodeAwareTextSplitter)
        assert splitter._language == "python"

    def test_register_new_splitter(self):
        """Should register custom splitter type."""

        class CustomSplitter(BaseTextSplitter):
            def split_text(self, text):
                return [text]

        SplitterFactory.register(SplitterType.RECURSIVE, CustomSplitter)
        splitter = SplitterFactory.create(SplitterType.RECURSIVE)

        assert isinstance(splitter, CustomSplitter)

    def test_list_available(self):
        """Should list all available splitter types."""
        available = SplitterFactory.list_available()

        assert SplitterType.CHINESE in available
        assert SplitterType.TOKEN in available
        assert SplitterType.SENTENCE in available
        assert SplitterType.MARKDOWN in available
        assert SplitterType.CODE in available
        assert SplitterType.SEMANTIC in available
        assert SplitterType.PARENT_CHILD in available

    def test_all_created_splitters_are_base_splitter(self):
        """Should ensure all created splitters extend BaseTextSplitter."""
        for st in SplitterType:
            if st in SplitterFactory._registry:
                splitter = SplitterFactory.create(st)
                assert isinstance(splitter, BaseTextSplitter)

    def test_create_from_dict_with_extra_keys(self):
        """Should handle extra keys in dict config."""
        config_dict = {
            "type": "sentence",
            "chunk_size": 100,
            "extra_key": "ignored",
        }
        with pytest.raises(TypeError):
            SplitterFactory.create_from_dict(config_dict)

    def test_create_markdown_with_headers(self):
        """Should create MarkdownTextSplitter with headers."""
        config = SplitterConfig(chunk_size=200, chunk_overlap=20)
        splitter = SplitterFactory.create(
            SplitterType.MARKDOWN,
            config=config,
            headers_to_split_on=[("#", "h1")],
        )

        assert isinstance(splitter, MarkdownTextSplitter)
        assert splitter._headers_to_split_on == [("#", "h1")]

    def test_create_semantic_with_embedding(self):
        """Should create SemanticTextSplitter with embedding function."""
        mock_embed = lambda x: [0.1, 0.2]
        config = SplitterConfig(chunk_size=200, chunk_overlap=20)
        splitter = SplitterFactory.create(
            SplitterType.SEMANTIC,
            config=config,
            embedding_function=mock_embed,
            breakpoint_threshold=0.7,
        )

        assert isinstance(splitter, SemanticTextSplitter)
        assert splitter._embedding_function == mock_embed
        assert splitter._breakpoint_threshold == 0.7

    def test_create_parent_child_with_sizes(self):
        """Should create ParentChildTextSplitter with sizes."""
        splitter = SplitterFactory.create(
            SplitterType.PARENT_CHILD,
            parent_chunk_size=1000,
            child_chunk_size=100,
        )

        assert isinstance(splitter, ParentChildTextSplitter)
        assert splitter._parent_chunk_size == 1000
        assert splitter._child_chunk_size == 100

    def test_factory_returns_new_instances(self):
        """Should return new instances on each create call."""
        s1 = SplitterFactory.create(SplitterType.CHINESE)
        s2 = SplitterFactory.create(SplitterType.CHINESE)

        assert s1 is not s2
