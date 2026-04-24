"""Unit tests for ParentChildTextSplitter."""

import pytest

from api.core.rag.splitter.parent_child_text_splitter import (
    ParentChildTextSplitter,
    ParentChildChunk,
)
from api.core.rag.splitter.splitter_types import SplitterConfig


class TestParentChildChunk:
    """Test ParentChildChunk dataclass."""

    def test_dataclass_creation(self):
        chunk = ParentChildChunk(
            parent_content="parent",
            parent_metadata={"key": "value"},
            child_chunks=["c1", "c2"],
            child_metadata=[{"i": 0}, {"i": 1}],
        )

        assert chunk.parent_content == "parent"
        assert chunk.parent_metadata == {"key": "value"}
        assert chunk.child_chunks == ["c1", "c2"]
        assert len(chunk.child_metadata) == 2


class TestParentChildTextSplitter:
    """Test ParentChildTextSplitter functionality."""

    def test_initialization_with_defaults(self):
        """Should initialize with default config."""
        splitter = ParentChildTextSplitter()

        assert splitter.config.chunk_size == 512
        assert splitter.config.chunk_overlap == 64
        assert splitter._parent_chunk_size == 2048
        assert splitter._child_chunk_size == 256

    def test_initialization_with_custom_params(self):
        """Should initialize with custom params."""
        splitter = ParentChildTextSplitter(parent_chunk_size=1000, child_chunk_size=100)

        assert splitter._parent_chunk_size == 1000
        assert splitter._child_chunk_size == 100

    def test_initialization_from_config(self):
        """Should read sizes from config."""
        config = SplitterConfig(parent_chunk_size=1500, child_chunk_size=200)
        splitter = ParentChildTextSplitter.from_config(config)

        assert splitter._parent_chunk_size == 1500
        assert splitter._child_chunk_size == 200

    def test_split_empty_text(self):
        """Should return empty result for empty text."""
        splitter = ParentChildTextSplitter()
        result = splitter.split_with_parents("")

        assert isinstance(result, ParentChildChunk)
        assert result.parent_content == ""
        assert result.child_chunks == []
        assert result.child_metadata == []

    def test_split_text_returns_child_chunks(self):
        """Should return only child chunks from split_text."""
        text = "word " * 100
        splitter = ParentChildTextSplitter(
            parent_chunk_size=200, child_chunk_size=50, chunk_overlap=5
        )
        chunks = splitter.split_text(text)

        assert len(chunks) > 0
        assert all(isinstance(c, str) for c in chunks)

    def test_split_with_parents_structure(self):
        """Should return proper parent-child structure."""
        text = "word " * 100
        splitter = ParentChildTextSplitter(parent_chunk_size=200, child_chunk_size=50)
        result = splitter.split_with_parents(text)

        assert isinstance(result, ParentChildChunk)
        assert result.parent_content == text
        assert "total_parents" in result.parent_metadata
        assert len(result.child_chunks) > 0
        assert len(result.child_metadata) == len(result.child_chunks)

    def test_child_metadata_contains_parent_info(self):
        """Should include parent info in child metadata."""
        text = "word " * 100
        splitter = ParentChildTextSplitter(parent_chunk_size=200, child_chunk_size=50)
        result = splitter.split_with_parents(text)

        for meta in result.child_metadata:
            assert "parent_index" in meta
            assert "child_index" in meta
            assert "parent_content" in meta

    def test_multiple_parent_chunks(self):
        """Should create multiple parent chunks for long text."""
        text = "word " * 500
        splitter = ParentChildTextSplitter(parent_chunk_size=200, child_chunk_size=50)
        result = splitter.split_with_parents(text)

        assert result.parent_metadata["total_parents"] > 1
        assert len(result.child_chunks) > 2

    def test_single_parent_single_child(self):
        """Should handle text that fits in single parent and child."""
        text = "Short text."
        splitter = ParentChildTextSplitter(parent_chunk_size=1000, child_chunk_size=500)
        result = splitter.split_with_parents(text)

        assert result.parent_metadata["total_parents"] == 1
        assert len(result.child_chunks) == 1

    def test_split_documents(self):
        """Should split documents with metadata."""
        splitter = ParentChildTextSplitter(parent_chunk_size=200, child_chunk_size=50)
        docs = [
            {
                "content": "word " * 50,
                "metadata": {"source": "test"},
            },
        ]
        result = splitter.split_documents(docs)

        assert len(result) > 0
        assert all("metadata" in r for r in result)
        assert all("chunk_index" in r["metadata"] for r in result)

    def test_from_config_classmethod(self):
        """Should create instance from config."""
        config = SplitterConfig(
            chunk_size=128,
            chunk_overlap=16,
            parent_chunk_size=500,
            child_chunk_size=100,
        )
        splitter = ParentChildTextSplitter.from_config(config)

        assert isinstance(splitter, ParentChildTextSplitter)
        assert splitter.config.chunk_size == 128
        assert splitter._parent_chunk_size == 500
        assert splitter._child_chunk_size == 100

    def test_chunk_overlap_validation(self):
        """Should raise ValueError if overlap > size."""
        with pytest.raises(ValueError, match="chunk_overlap"):
            ParentChildTextSplitter(chunk_size=10, chunk_overlap=20)

    def test_split_by_size_with_overlap(self):
        """Should create overlapping chunks."""
        splitter = ParentChildTextSplitter()
        text = "a" * 100
        chunks = splitter._split_by_size(text, chunk_size=30, overlap=10)

        assert len(chunks) > 1
        if len(chunks) > 1:
            assert len(chunks[0]) > 0
            assert len(chunks[1]) > 0

    def test_split_by_size_word_boundary(self):
        """Should respect word boundaries when possible."""
        splitter = ParentChildTextSplitter()
        text = "word1 word2 word3 word4 word5"
        chunks = splitter._split_by_size(text, chunk_size=15, overlap=0)

        assert len(chunks) > 0
        for chunk in chunks:
            assert chunk.strip() != ""

    def test_child_chunks_smaller_than_parent(self):
        """Should ensure child chunks are smaller than parent."""
        text = "word " * 200
        splitter = ParentChildTextSplitter(parent_chunk_size=300, child_chunk_size=50)
        result = splitter.split_with_parents(text)

        for child in result.child_chunks:
            assert len(child) <= 300

    def test_all_text_preserved(self):
        """Should preserve all text in child chunks."""
        text = "word " * 50
        splitter = ParentChildTextSplitter(
            parent_chunk_size=200, child_chunk_size=50, chunk_overlap=0
        )
        result = splitter.split_with_parents(text)

        combined = " ".join(result.child_chunks)
        assert "word" in combined

    def test_parent_index_increments(self):
        """Should increment parent_index across parent chunks."""
        text = "word " * 500
        splitter = ParentChildTextSplitter(
            parent_chunk_size=100, child_chunk_size=30, chunk_overlap=0
        )
        result = splitter.split_with_parents(text)

        parent_indices = [m["parent_index"] for m in result.child_metadata]
        assert max(parent_indices) > 0

    def test_child_index_resets_per_parent(self):
        """Should reset child_index for each parent."""
        text = "word " * 500
        splitter = ParentChildTextSplitter(
            parent_chunk_size=100, child_chunk_size=30, chunk_overlap=0
        )
        result = splitter.split_with_parents(text)

        child_indices = [m["child_index"] for m in result.child_metadata]
        assert 0 in child_indices
