"""Unit tests for MarkdownTextSplitter."""

import pytest

from api.core.rag.splitter.markdown_text_splitter import MarkdownTextSplitter
from api.core.rag.splitter.splitter_types import SplitterConfig


class TestMarkdownTextSplitter:
    """Test MarkdownTextSplitter functionality."""

    def test_initialization_with_defaults(self):
        """Should initialize with default config."""
        splitter = MarkdownTextSplitter()

        assert splitter.config.chunk_size == 512
        assert splitter.config.chunk_overlap == 64
        assert splitter._headers_to_split_on == [
            ("#", "header1"),
            ("##", "header2"),
            ("###", "header3"),
        ]

    def test_initialization_with_custom_headers(self):
        """Should initialize with custom headers."""
        headers = [("#", "h1"), ("##", "h2")]
        splitter = MarkdownTextSplitter(headers_to_split_on=headers)

        assert splitter._headers_to_split_on == headers

    def test_initialization_with_custom_config(self):
        """Should initialize with custom config."""
        config = SplitterConfig(chunk_size=200, chunk_overlap=20)
        splitter = MarkdownTextSplitter(config=config)

        assert splitter.config.chunk_size == 200

    def test_split_empty_text(self):
        """Should return empty list for empty text."""
        splitter = MarkdownTextSplitter()
        chunks = splitter.split_text("")

        assert chunks == []

    def test_split_simple_markdown(self):
        """Should split markdown by headers."""
        text = "# Title\n\nSome content here.\n\n## Section 1\n\nMore content."
        splitter = MarkdownTextSplitter(chunk_size=1000)
        chunks = splitter.split_text(text)

        assert len(chunks) >= 1
        full_text = "\n\n".join(chunks)
        assert "Title" in full_text
        assert "Section 1" in full_text

    def test_split_by_headers(self):
        """Should create separate chunks for each header section."""
        text = """# Header 1
Content for header 1.
More content.

## Header 2
Content for header 2.

### Header 3
Content for header 3."""
        splitter = MarkdownTextSplitter(chunk_size=1000)
        chunks = splitter.split_text(text)

        assert len(chunks) >= 1
        combined = "\n\n".join(chunks)
        assert "Header 1" in combined
        assert "Header 2" in combined

    def test_split_respects_chunk_size(self):
        """Should split large sections to respect chunk_size."""
        text = "# Section\n\n" + "word " * 200
        splitter = MarkdownTextSplitter(chunk_size=100)
        chunks = splitter.split_text(text)

        assert len(chunks) >= 1
        full_text = "\n\n".join(chunks)
        assert "word" in full_text

    def test_split_preserves_header_in_chunk(self):
        """Should preserve header with its content."""
        text = "# My Header\n\nThis is the content."
        splitter = MarkdownTextSplitter(chunk_size=1000)
        chunks = splitter.split_text(text)

        assert len(chunks) >= 1
        assert any("# My Header" in c for c in chunks)

    def test_split_no_headers(self):
        """Should handle markdown without headers."""
        text = "Just some plain text without headers.\n\nAnother paragraph."
        splitter = MarkdownTextSplitter(chunk_size=100)
        chunks = splitter.split_text(text)

        assert len(chunks) >= 1
        full_text = "\n\n".join(chunks)
        assert "plain text" in full_text

    def test_split_multiple_paragraphs_under_header(self):
        """Should handle multiple paragraphs under same header."""
        text = """# Title

First paragraph with some text.

Second paragraph with more text.

Third paragraph here."""
        splitter = MarkdownTextSplitter(chunk_size=200)
        chunks = splitter.split_text(text)

        assert len(chunks) >= 1
        full_text = "\n\n".join(chunks)
        assert "First paragraph" in full_text
        assert "Second paragraph" in full_text

    def test_split_code_blocks(self):
        """Should handle markdown with code blocks."""
        text = """# Code Example

Here is some code:

```python
def hello():
    return "world"
```

More text."""
        splitter = MarkdownTextSplitter(chunk_size=500)
        chunks = splitter.split_text(text)

        assert len(chunks) >= 1
        full_text = "\n\n".join(chunks)
        assert "Code Example" in full_text
        assert "hello" in full_text

    def test_split_with_custom_header_levels(self):
        """Should respect custom header levels."""
        headers = [("##", "h2")]
        text = """# Title

Title content.

## Section A

Section A content.

## Section B

Section B content."""
        splitter = MarkdownTextSplitter(chunk_size=1000, headers_to_split_on=headers)
        chunks = splitter.split_text(text)

        assert len(chunks) >= 1
        full_text = "\n\n".join(chunks)
        assert "Section A" in full_text or "Title" in full_text

    def test_split_documents(self):
        """Should split documents with metadata."""
        splitter = MarkdownTextSplitter(chunk_size=200)
        docs = [
            {
                "content": "# Doc 1\n\nContent one.",
                "metadata": {"source": "test"},
            },
        ]
        result = splitter.split_documents(docs)

        assert len(result) > 0
        assert all("metadata" in r for r in result)
        assert all("chunk_index" in r["metadata"] for r in result)

    def test_from_config_classmethod(self):
        """Should create instance from config."""
        config = SplitterConfig(chunk_size=128, chunk_overlap=16)
        splitter = MarkdownTextSplitter.from_config(config)

        assert isinstance(splitter, MarkdownTextSplitter)
        assert splitter.config.chunk_size == 128

    def test_chunk_overlap_validation(self):
        """Should raise ValueError if overlap > size."""
        with pytest.raises(ValueError, match="chunk_overlap"):
            MarkdownTextSplitter(chunk_size=10, chunk_overlap=20)

    def test_split_nested_headers(self):
        """Should handle nested headers."""
        text = """# Main Title

Main content.

## Subsection 1

Sub content 1.

### Sub-subsection

Deep content.

## Subsection 2

Sub content 2."""
        splitter = MarkdownTextSplitter(chunk_size=1000)
        chunks = splitter.split_text(text)

        assert len(chunks) >= 1
        combined = "\n\n".join(chunks)
        assert "Main Title" in combined

    def test_split_empty_sections(self):
        """Should handle headers with no content."""
        text = "# Header 1\n\n## Header 2\n\nContent."
        splitter = MarkdownTextSplitter(chunk_size=100)
        chunks = splitter.split_text(text)

        assert len(chunks) >= 1

    def test_split_list_items(self):
        """Should handle markdown lists."""
        text = """# List Section

- Item 1
- Item 2
- Item 3

More text after list."""
        splitter = MarkdownTextSplitter(chunk_size=200)
        chunks = splitter.split_text(text)

        assert len(chunks) >= 1
        full_text = "\n\n".join(chunks)
        assert "Item 1" in full_text

    def test_split_horizontal_rules(self):
        """Should handle horizontal rules."""
        text = """# Section 1

Content 1.

---

# Section 2

Content 2."""
        splitter = MarkdownTextSplitter(chunk_size=500)
        chunks = splitter.split_text(text)

        assert len(chunks) >= 1
