import pytest
from unittest.mock import MagicMock, patch

from api.core.rag.splitter.token_text_splitter import TokenTextSplitter
from api.core.rag.splitter.splitter_types import SplitterConfig


class TestTokenTextSplitter:
    def test_initialization_with_defaults(self):
        splitter = TokenTextSplitter()
        assert splitter.config.chunk_size == 512
        assert splitter.config.chunk_overlap == 64
        assert splitter.config.model_name is None

    def test_initialization_with_custom_config(self):
        config = SplitterConfig(chunk_size=100, chunk_overlap=10, model_name="gpt-4")
        splitter = TokenTextSplitter(config=config)
        assert splitter.config.chunk_size == 100
        assert splitter.config.chunk_overlap == 10
        assert splitter.config.model_name == "gpt-4"

    def test_initialization_with_kwargs(self):
        splitter = TokenTextSplitter(chunk_size=200, chunk_overlap=20)
        assert splitter.config.chunk_size == 200
        assert splitter.config.chunk_overlap == 20

    def test_split_empty_text(self):
        splitter = TokenTextSplitter()
        chunks = splitter.split_text("")
        assert chunks == []

    def test_split_text_with_none_encoding_uses_fallback(self):
        splitter = TokenTextSplitter()
        splitter._encoding = None
        chunks = splitter.split_text("Hello world")
        assert len(chunks) >= 1
        assert "Hello" in chunks[0]

    def test_split_text_with_mock_encoding(self):
        mock_encoding = MagicMock()
        mock_encoding.encode.return_value = list(range(100))
        mock_encoding.decode.side_effect = lambda tokens: f"chunk_{len(tokens)}"

        splitter = TokenTextSplitter(chunk_size=30, chunk_overlap=5)
        splitter._encoding = mock_encoding
        chunks = splitter.split_text("Some text to split")

        assert len(chunks) > 0
        mock_encoding.encode.assert_called_once_with("Some text to split")

    def test_split_text_respects_chunk_size(self):
        mock_encoding = MagicMock()
        mock_encoding.encode.return_value = list(range(100))
        mock_encoding.decode.side_effect = lambda tokens: "x" * len(tokens)

        splitter = TokenTextSplitter(chunk_size=30, chunk_overlap=5)
        splitter._encoding = mock_encoding
        chunks = splitter.split_text("Long text")

        assert len(chunks) == 4
        mock_encoding.encode.assert_called_once()

    def test_split_text_overlap(self):
        mock_encoding = MagicMock()
        mock_encoding.encode.return_value = list(range(50))
        mock_encoding.decode.side_effect = lambda tokens: f"chunk_{len(tokens)}"

        splitter = TokenTextSplitter(chunk_size=20, chunk_overlap=5)
        splitter._encoding = mock_encoding
        chunks = splitter.split_text("Text")

        assert len(chunks) == 3

    def test_split_single_chunk(self):
        mock_encoding = MagicMock()
        mock_encoding.encode.return_value = list(range(10))
        mock_encoding.decode.return_value = "short text"

        splitter = TokenTextSplitter(chunk_size=100, chunk_overlap=10)
        splitter._encoding = mock_encoding
        chunks = splitter.split_text("Short text")

        assert len(chunks) == 1
        assert chunks[0] == "short text"

    def test_from_config_classmethod(self):
        config = SplitterConfig(chunk_size=128, chunk_overlap=16)
        splitter = TokenTextSplitter.from_config(config)
        assert isinstance(splitter, TokenTextSplitter)
        assert splitter.config.chunk_size == 128

    def test_chunk_overlap_validation(self):
        with pytest.raises(ValueError, match="chunk_overlap"):
            TokenTextSplitter(chunk_size=10, chunk_overlap=20)

    def test_split_documents(self):
        mock_encoding = MagicMock()
        mock_encoding.encode.return_value = list(range(20))
        mock_encoding.decode.return_value = "chunk"

        splitter = TokenTextSplitter(chunk_size=10, chunk_overlap=2)
        splitter._encoding = mock_encoding
        docs = [
            {"content": "Document one", "metadata": {"source": "test"}},
            {"content": "Document two", "metadata": {"source": "test2"}},
        ]
        result = splitter.split_documents(docs)

        assert len(result) > 0
        assert all("metadata" in r for r in result)
        assert all("chunk_index" in r["metadata"] for r in result)

    def test_split_chinese_text(self):
        mock_encoding = MagicMock()
        mock_encoding.encode.return_value = list(range(60))
        mock_encoding.decode.return_value = "中文文本"

        splitter = TokenTextSplitter(chunk_size=20, chunk_overlap=5)
        splitter._encoding = mock_encoding
        chunks = splitter.split_text("这是中文文本用于测试")

        assert len(chunks) > 0

    def test_split_very_long_text(self):
        mock_encoding = MagicMock()
        mock_encoding.encode.return_value = list(range(1000))
        mock_encoding.decode.side_effect = lambda tokens: "x" * len(tokens)

        splitter = TokenTextSplitter(chunk_size=100, chunk_overlap=10)
        splitter._encoding = mock_encoding
        chunks = splitter.split_text("x" * 1000)

        assert len(chunks) == 11

    def test_import_error_sets_none_encoding(self):
        mock_tiktoken = MagicMock()
        mock_tiktoken.encoding_for_model.side_effect = ImportError(
            "No module named tiktoken"
        )

        import api.core.rag.splitter.token_text_splitter as tts

        original_tiktoken = getattr(tts, "tiktoken", None)
        try:
            tts.tiktoken = mock_tiktoken
            splitter = TokenTextSplitter()
            assert splitter._encoding is None
            assert splitter._tiktoken is None
        finally:
            if original_tiktoken is not None:
                tts.tiktoken = original_tiktoken
            elif hasattr(tts, "tiktoken"):
                delattr(tts, "tiktoken")

    def test_fallback_split_method(self):
        splitter = TokenTextSplitter.__new__(TokenTextSplitter)
        splitter._encoding = None
        splitter.config = SplitterConfig(chunk_size=5, chunk_overlap=1)

        chunks = splitter.split_text("abcdefghij")
        assert len(chunks) == 3
        assert chunks[0] == "abcde"
        assert chunks[1] == "efghi"
        assert chunks[2] == "ij"

    def test_fallback_split_short_text(self):
        splitter = TokenTextSplitter.__new__(TokenTextSplitter)
        splitter._encoding = None
        splitter.config = SplitterConfig(chunk_size=100, chunk_overlap=10)

        chunks = splitter.split_text("short")
        assert len(chunks) == 1
        assert chunks[0] == "short"
