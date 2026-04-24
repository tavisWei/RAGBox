import pytest
from unittest.mock import patch, MagicMock

from api.core.rag.splitter.sentence_text_splitter import SentenceTextSplitter
from api.core.rag.splitter.splitter_types import SplitterConfig


class TestSentenceTextSplitter:
    def test_initialization_with_defaults(self):
        splitter = SentenceTextSplitter()
        assert splitter.config.chunk_size == 512
        assert splitter.config.chunk_overlap == 64

    def test_initialization_with_custom_config(self):
        config = SplitterConfig(chunk_size=200, chunk_overlap=20)
        splitter = SentenceTextSplitter(config=config)
        assert splitter.config.chunk_size == 200
        assert splitter.config.chunk_overlap == 20

    def test_initialization_with_kwargs(self):
        splitter = SentenceTextSplitter(chunk_size=300, chunk_overlap=30)
        assert splitter.config.chunk_size == 300
        assert splitter.config.chunk_overlap == 30

    def test_split_empty_text(self):
        splitter = SentenceTextSplitter()
        chunks = splitter.split_text("")
        assert chunks == []

    @patch("nltk.data.find")
    @patch("nltk.sent_tokenize")
    def test_split_multiple_chunks(self, mock_tokenize, mock_find):
        """Should create multiple chunks when sentences exceed chunk_size."""
        mock_find.return_value = True
        mock_tokenize.return_value = [
            "This is a very long first sentence that exceeds chunk size.",
            "This is another very long second sentence.",
        ]

        splitter = SentenceTextSplitter(chunk_size=50, chunk_overlap=5)
        chunks = splitter.split_text("Long text")

        assert len(chunks) == 2

    @patch("nltk.data.find")
    @patch("nltk.sent_tokenize")
    def test_many_small_sentences(self, mock_tokenize, mock_find):
        """Should group many small sentences into chunks."""
        mock_find.return_value = True
        mock_tokenize.return_value = [f"S{i}." for i in range(20)]

        splitter = SentenceTextSplitter(chunk_size=50, chunk_overlap=5)
        chunks = splitter.split_text("Text")

        assert len(chunks) >= 1
        total_sentences = sum(c.count(".") for c in chunks)
        assert total_sentences == 20

    @patch("nltk.data.find")
    @patch("nltk.sent_tokenize")
    def test_whitespace_only_text(self, mock_tokenize, mock_find):
        mock_find.return_value = True
        mock_tokenize.return_value = []

        splitter = SentenceTextSplitter(chunk_size=100)
        chunks = splitter.split_text("   ")

        assert chunks == []
