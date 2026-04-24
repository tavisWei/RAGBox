import pytest
import numpy as np
from unittest.mock import MagicMock

from api.core.rag.splitter.semantic_text_splitter import SemanticTextSplitter
from api.core.rag.splitter.splitter_types import SplitterConfig


class TestSemanticTextSplitter:
    def test_initialization_with_defaults(self):
        splitter = SemanticTextSplitter()
        assert splitter.config.chunk_size == 512
        assert splitter.config.chunk_overlap == 64
        assert splitter._embedding_function is None
        assert splitter._breakpoint_threshold == 0.5

    def test_initialization_with_custom_params(self):
        mock_embed = MagicMock(return_value=[0.1, 0.2, 0.3])
        splitter = SemanticTextSplitter(
            embedding_function=mock_embed,
            breakpoint_threshold=0.7,
            chunk_size=200,
        )
        assert splitter._embedding_function == mock_embed
        assert splitter._breakpoint_threshold == 0.7
        assert splitter.config.chunk_size == 200

    def test_split_empty_text(self):
        splitter = SemanticTextSplitter()
        chunks = splitter.split_text("")
        assert chunks == []

    def test_split_without_embedding_function(self):
        text = "First sentence. Second sentence. Third sentence."
        splitter = SemanticTextSplitter(chunk_size=1000, chunk_overlap=10)
        from api.core.rag.splitter.sentence_text_splitter import SentenceTextSplitter

        mock_fallback = MagicMock()
        mock_fallback.split_text.return_value = [
            "First sentence.",
            "Second sentence.",
            "Third sentence.",
        ]

        original_init = SentenceTextSplitter.__init__

        def mock_init(self, *args, **kwargs):
            self.config = SplitterConfig(chunk_size=1000, chunk_overlap=10)
            self._nltk = MagicMock()
            self._nltk.sent_tokenize = MagicMock(
                return_value=["First sentence.", "Second sentence.", "Third sentence."]
            )

        SentenceTextSplitter.__init__ = mock_init
        try:
            chunks = splitter.split_text(text)
            assert len(chunks) >= 1
            full_text = " ".join(chunks)
            assert "First sentence" in full_text
        finally:
            SentenceTextSplitter.__init__ = original_init

    def test_split_single_sentence(self):
        text = "Only one sentence."
        mock_embed = MagicMock(return_value=[0.1, 0.2])
        splitter = SemanticTextSplitter(embedding_function=mock_embed, chunk_size=1000)
        chunks = splitter.split_text(text)

        assert len(chunks) == 1
        assert chunks[0] == "Only one sentence."

    def test_split_with_embedding_function(self):
        text = "The cat sat on the mat. Dogs are great pets. Python is a programming language."

        def mock_embed(text):
            if "cat" in text or "dog" in text:
                return [1.0, 0.0]
            return [0.0, 1.0]

        splitter = SemanticTextSplitter(
            embedding_function=mock_embed,
            breakpoint_threshold=0.5,
            chunk_size=1000,
        )
        chunks = splitter.split_text(text)

        assert len(chunks) >= 1

    def test_split_with_high_threshold(self):
        text = "Sentence one here. Sentence two here. Sentence three here."

        def mock_embed(text):
            return [1.0, 0.0]

        splitter = SemanticTextSplitter(
            embedding_function=mock_embed,
            breakpoint_threshold=0.99,
            chunk_size=1000,
        )
        chunks = splitter.split_text(text)

        assert len(chunks) >= 1

    def test_split_with_low_threshold(self):
        text = "Sentence one here. Sentence two here. Sentence three here."

        def mock_embed(text):
            return [1.0, 0.0]

        splitter = SemanticTextSplitter(
            embedding_function=mock_embed,
            breakpoint_threshold=0.01,
            chunk_size=1000,
        )
        chunks = splitter.split_text(text)

        assert len(chunks) >= 1

    def test_cosine_similarity_identical_vectors(self):
        splitter = SemanticTextSplitter()
        vec = [1.0, 2.0, 3.0]
        sim = splitter._cosine_similarity(vec, vec)

        assert sim == pytest.approx(1.0, abs=1e-6)

    def test_cosine_similarity_orthogonal_vectors(self):
        splitter = SemanticTextSplitter()
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]
        sim = splitter._cosine_similarity(vec1, vec2)

        assert sim == pytest.approx(0.0, abs=1e-6)

    def test_cosine_similarity_opposite_vectors(self):
        splitter = SemanticTextSplitter()
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [-1.0, 0.0, 0.0]
        sim = splitter._cosine_similarity(vec1, vec2)

        assert sim == pytest.approx(-1.0, abs=1e-6)

    def test_split_by_size(self):
        splitter = SemanticTextSplitter(chunk_size=10, chunk_overlap=2)
        chunks = splitter._split_by_size("abcdefghijklmnopqrstuvwxyz")

        assert len(chunks) >= 1
        assert chunks[0] == "abcdefghij"

    def test_split_by_size_exact_fit(self):
        splitter = SemanticTextSplitter(chunk_size=10, chunk_overlap=2)
        chunks = splitter._split_by_size("abcdefghij")

        assert len(chunks) == 1
        assert chunks[0] == "abcdefghij"

    def test_split_sentences(self):
        splitter = SemanticTextSplitter()
        sentences = splitter._split_sentences("First. Second! Third?")

        assert len(sentences) == 3
        assert "First" in sentences[0]
        assert "Second" in sentences[1]
        assert "Third" in sentences[2]

    def test_split_sentences_with_whitespace(self):
        splitter = SemanticTextSplitter()
        sentences = splitter._split_sentences("  First.   Second.  ")

        assert len(sentences) == 2

    def test_split_documents(self):
        mock_embed = MagicMock(return_value=[0.1, 0.2])
        splitter = SemanticTextSplitter(
            embedding_function=mock_embed,
            chunk_size=200,
            chunk_overlap=10,
        )
        docs = [
            {
                "content": "First sentence. Second sentence.",
                "metadata": {"source": "test"},
            },
        ]
        result = splitter.split_documents(docs)

        assert len(result) > 0
        assert all("metadata" in r for r in result)
        assert all("chunk_index" in r["metadata"] for r in result)

    def test_from_config_classmethod(self):
        config = SplitterConfig(chunk_size=128, chunk_overlap=16)
        splitter = SemanticTextSplitter.from_config(config)
        assert isinstance(splitter, SemanticTextSplitter)
        assert splitter.config.chunk_size == 128

    def test_chunk_overlap_validation(self):
        with pytest.raises(ValueError, match="chunk_overlap"):
            SemanticTextSplitter(chunk_size=10, chunk_overlap=20)

    def test_split_large_chunk_by_size(self):
        text = "A. B. C. D. E. F. G. H. I. J."

        def mock_embed(text):
            return [1.0, 0.0]

        splitter = SemanticTextSplitter(
            embedding_function=mock_embed,
            breakpoint_threshold=0.99,
            chunk_size=100,
            chunk_overlap=10,
        )
        chunks = splitter.split_text(text)

        assert len(chunks) >= 1
        for chunk in chunks:
            assert len(chunk) <= 100

    def test_split_with_numpy_arrays(self):
        text = "One. Two. Three."

        def mock_embed(text):
            return np.array([0.5, 0.5])

        splitter = SemanticTextSplitter(
            embedding_function=mock_embed,
            breakpoint_threshold=0.5,
            chunk_size=1000,
        )
        chunks = splitter.split_text(text)

        assert len(chunks) >= 1

    def test_split_empty_sentences_filtered(self):
        splitter = SemanticTextSplitter()
        sentences = splitter._split_sentences(". . .")

        assert len(sentences) <= 3

    def test_split_with_multiple_breakpoints(self):
        text = "A1. A2. B1. B2. C1. C2."

        call_count = [0]

        def mock_embed(text):
            call_count[0] += 1
            idx = call_count[0] % 3
            return [[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]][idx]

        splitter = SemanticTextSplitter(
            embedding_function=mock_embed,
            breakpoint_threshold=0.5,
            chunk_size=1000,
        )
        chunks = splitter.split_text(text)

        assert len(chunks) >= 1
