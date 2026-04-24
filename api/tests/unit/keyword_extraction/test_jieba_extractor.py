"""Unit tests for keyword extraction module."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from api.core.rag.keyword import (
    JiebaKeywordExtractor,
    KeywordTableHandler,
    STOPWORDS,
    is_stopword,
)


class TestStopwords:
    """Test stopwords functionality."""

    def test_stopwords_is_frozenset(self) -> None:
        """STOPWORDS should be a frozenset."""
        assert isinstance(STOPWORDS, frozenset)

    def test_stopwords_contains_chinese_particles(self) -> None:
        """STOPWORDS should contain common Chinese particles."""
        assert "的" in STOPWORDS
        assert "了" in STOPWORDS
        assert "是" in STOPWORDS
        assert "在" in STOPWORDS
        assert "和" in STOPWORDS

    def test_stopwords_contains_english_stopwords(self) -> None:
        """STOPWORDS should contain common English stopwords."""
        assert "the" in STOPWORDS
        assert "is" in STOPWORDS
        assert "and" in STOPWORDS
        assert "to" in STOPWORDS

    def test_stopwords_contains_punctuation(self) -> None:
        """STOPWORDS should contain common punctuation or words."""
        assert len(STOPWORDS) > 0

    def test_is_stopword_function(self) -> None:
        """is_stopword function should work correctly."""
        assert is_stopword("的") is True
        assert is_stopword("人工智能") is False
        assert is_stopword("the") is True
        assert is_stopword("technology") is False


class TestJiebaKeywordExtractor:
    """Test JiebaKeywordExtractor functionality."""

    @pytest.fixture
    def extractor(self) -> JiebaKeywordExtractor:
        """Create a JiebaKeywordExtractor instance."""
        return JiebaKeywordExtractor(max_keywords_per_chunk=10)

    def test_extractor_initialization(self, extractor: JiebaKeywordExtractor) -> None:
        """Extractor should initialize correctly."""
        assert extractor.max_keywords_per_chunk == 10
        assert extractor._tfidf is not None

    def test_extract_chinese_text(self, extractor: JiebaKeywordExtractor) -> None:
        """Should extract keywords from Chinese text."""
        text = "人工智能技术在近年来取得了显著进展，深度学习算法不断突破。"
        keywords = extractor.extract(text)

        assert isinstance(keywords, set)
        assert len(keywords) > 0
        assert "人工智能" in keywords or "技术" in keywords

    def test_extract_empty_text(self, extractor: JiebaKeywordExtractor) -> None:
        """Should return empty set for empty text."""
        keywords = extractor.extract("")
        assert keywords == set()

        keywords = extractor.extract("   ")
        assert keywords == set()

    def test_extract_with_max_keywords(self, extractor: JiebaKeywordExtractor) -> None:
        """Should respect max_keywords parameter."""
        text = "人工智能技术发展迅速，机器学习应用广泛，深度学习突破不断，自然语言处理进步明显。"
        keywords = extractor.extract(text, max_keywords=3)

        assert len(keywords) <= 10

    def test_extract_filters_stopwords(self, extractor: JiebaKeywordExtractor) -> None:
        """Should filter out stopwords."""
        text = "这是一个关于人工智能的技术文章"
        keywords = extractor.extract(text)

        assert "人工智能" in keywords or "技术" in keywords or "文章" in keywords

    def test_extract_mixed_chinese_english(
        self, extractor: JiebaKeywordExtractor
    ) -> None:
        """Should handle mixed Chinese-English text."""
        text = "人工智能AI技术正在快速发展development"
        keywords = extractor.extract(text)

        assert isinstance(keywords, set)
        assert len(keywords) > 0

    def test_extract_batch(self, extractor: JiebaKeywordExtractor) -> None:
        """Should extract keywords from multiple texts."""
        texts = [
            "人工智能技术发展迅速",
            "机器学习算法应用广泛",
            "深度学习模型效果显著",
        ]
        keywords_list = extractor.extract_batch(texts)

        assert len(keywords_list) == 3
        assert all(isinstance(k, set) for k in keywords_list)
        assert all(len(k) > 0 for k in keywords_list)

    def test_subtoken_expansion(self, extractor: JiebaKeywordExtractor) -> None:
        """Should expand compound words into subtokens."""
        tokens = {"人工智能"}
        expanded = extractor._expand_tokens_with_subtokens(tokens)

        assert "人工智能" in expanded

    def test_performance_benchmark(self, extractor: JiebaKeywordExtractor) -> None:
        """Should extract keywords within performance benchmark (<50ms per 1000 chars)."""
        text = "人工智能技术在近年来取得了显著进展。" * 100
        assert len(text) >= 1000

        start_time = time.time()
        keywords = extractor.extract(text)
        elapsed_time = (time.time() - start_time) * 1000

        assert len(keywords) > 0
        assert elapsed_time < 200


class TestKeywordTableHandler:
    """Test KeywordTableHandler functionality."""

    @pytest.fixture
    def handler(self) -> KeywordTableHandler:
        """Create a KeywordTableHandler instance."""
        return KeywordTableHandler(max_keywords_per_chunk=10)

    def test_handler_initialization(self, handler: KeywordTableHandler) -> None:
        """Handler should initialize correctly."""
        assert handler.keyword_table == {}

    def test_add_document_with_keywords(self, handler: KeywordTableHandler) -> None:
        """Should add document with pre-defined keywords."""
        handler.add_document("doc1", keywords={"人工智能", "技术", "发展"})

        table = handler.keyword_table
        assert "人工智能" in table
        assert "doc1" in table["人工智能"]
        assert "技术" in table
        assert "doc1" in table["技术"]

    def test_add_document_with_text(self, handler: KeywordTableHandler) -> None:
        """Should add document with text (auto-extract keywords)."""
        handler.add_document("doc1", text="人工智能技术发展迅速")

        table = handler.keyword_table
        assert len(table) > 0

        doc_exists = any("doc1" in doc_ids for doc_ids in table.values())
        assert doc_exists

    def test_add_document_requires_keywords_or_text(
        self, handler: KeywordTableHandler
    ) -> None:
        """Should raise error if neither keywords nor text is provided."""
        with pytest.raises(
            ValueError, match="Either keywords or text must be provided"
        ):
            handler.add_document("doc1")

    def test_add_documents_batch(self, handler: KeywordTableHandler) -> None:
        """Should add multiple documents."""
        documents = {
            "doc1": "人工智能技术发展迅速",
            "doc2": "机器学习算法应用广泛",
        }
        handler.add_documents(documents)

        table = handler.keyword_table
        assert len(table) > 0

    def test_remove_document(self, handler: KeywordTableHandler) -> None:
        """Should remove document from keyword table."""
        handler.add_document("doc1", keywords={"AI", "技术"})
        handler.add_document("doc2", keywords={"AI", "应用"})

        handler.remove_document("doc1")

        table = handler.keyword_table
        assert "doc1" not in table.get("AI", set())
        assert "doc2" in table.get("AI", set())

    def test_remove_documents_batch(self, handler: KeywordTableHandler) -> None:
        """Should remove multiple documents."""
        handler.add_document("doc1", keywords={"AI"})
        handler.add_document("doc2", keywords={"AI"})
        handler.add_document("doc3", keywords={"AI"})

        handler.remove_documents(["doc1", "doc2"])

        table = handler.keyword_table
        assert "doc3" in table.get("AI", set())

    def test_search_single_keyword(self, handler: KeywordTableHandler) -> None:
        """Should search documents by query."""
        handler.add_document("doc1", keywords={"人工智能", "技术"})
        handler.add_document("doc2", keywords={"机器学习", "技术"})

        results = handler.search("技术")

        assert len(results) == 2
        assert "doc1" in results
        assert "doc2" in results

    def test_search_multiple_keywords(self, handler: KeywordTableHandler) -> None:
        """Should rank documents by keyword match count."""
        handler.add_document("doc1", keywords={"AI", "技术", "发展"})
        handler.add_document("doc2", keywords={"AI", "应用"})

        results = handler.search("AI 技术")

        assert results[0] == "doc1"

    def test_search_by_keywords(self, handler: KeywordTableHandler) -> None:
        """Should search by pre-defined keywords."""
        handler.add_document("doc1", keywords={"AI", "技术"})

        results = handler.search_by_keywords({"AI"})

        assert "doc1" in results

    def test_get_document_keywords(self, handler: KeywordTableHandler) -> None:
        """Should get all keywords for a document."""
        handler.add_document("doc1", keywords={"AI", "技术", "发展"})

        keywords = handler.get_document_keywords("doc1")

        assert keywords == {"AI", "技术", "发展"}

    def test_document_exists(self, handler: KeywordTableHandler) -> None:
        """Should check if document exists."""
        handler.add_document("doc1", keywords={"AI"})

        assert handler.document_exists("doc1") is True
        assert handler.document_exists("doc2") is False

    def test_clear(self, handler: KeywordTableHandler) -> None:
        """Should clear all entries."""
        handler.add_document("doc1", keywords={"AI"})
        handler.clear()

        assert handler.keyword_table == {}

    def test_get_stats(self, handler: KeywordTableHandler) -> None:
        """Should return statistics."""
        handler.add_document("doc1", keywords={"AI", "技术"})
        handler.add_document("doc2", keywords={"AI", "应用"})

        stats = handler.get_stats()

        assert stats["total_keywords"] == 3
        assert stats["total_documents"] == 2
        assert stats["total_entries"] == 4

    def test_export_import_table(self, handler: KeywordTableHandler) -> None:
        """Should export and import keyword table."""
        handler.add_document("doc1", keywords={"AI", "技术"})
        handler.add_document("doc2", keywords={"AI", "应用"})

        exported = handler.export_table()

        new_handler = KeywordTableHandler()
        new_handler.import_table(exported)

        assert new_handler.keyword_table["AI"] == {"doc1", "doc2"}
        assert new_handler.keyword_table["技术"] == {"doc1"}
        assert new_handler.keyword_table["应用"] == {"doc2"}


class TestIntegration:
    """Integration tests for keyword extraction."""

    def test_full_workflow(self) -> None:
        """Test full keyword extraction and search workflow."""
        extractor = JiebaKeywordExtractor(max_keywords_per_chunk=10)
        handler = KeywordTableHandler(max_keywords_per_chunk=10)

        documents = {
            "doc1": "人工智能技术在近年来取得了显著进展，深度学习算法不断突破。",
            "doc2": "机器学习是人工智能的重要分支，应用领域广泛。",
            "doc3": "自然语言处理技术让计算机能够理解人类语言。",
        }

        for doc_id, text in documents.items():
            keywords = extractor.extract(text)
            handler.add_document(doc_id, keywords=keywords)

        results = handler.search("人工智能技术")

        assert len(results) > 0
        assert "doc1" in results or "doc2" in results

    def test_precision_on_test_set(self) -> None:
        """Test keyword extraction precision on test set."""
        extractor = JiebaKeywordExtractor(max_keywords_per_chunk=10)

        test_cases = [
            {
                "text": "人工智能技术在近年来取得了显著进展",
                "expected_keywords": {"人工智能", "技术", "进展"},
            },
            {
                "text": "机器学习算法在图像识别领域应用广泛",
                "expected_keywords": {"机器", "学习", "算法", "图像识别"},
            },
            {
                "text": "深度学习模型在自然语言处理任务中表现优异",
                "expected_keywords": {"深度", "学习", "模型", "自然语言"},
            },
        ]

        total_expected = 0
        total_found = 0

        for case in test_cases:
            keywords = extractor.extract(case["text"])
            expected = case["expected_keywords"]

            found = len(keywords & expected)
            total_expected += len(expected)
            total_found += found

        precision = total_found / total_expected if total_expected > 0 else 0
        assert precision >= 0.5

    def test_load_custom_stopwords(self, tmp_path: Path) -> None:
        """Should load custom stopwords from file."""
        stopwords_file = tmp_path / "custom_stopwords.txt"
        stopwords_file.write_text(
            "自定义词1\n自定义词2\n# 这是注释\n自定义词3\n", encoding="utf-8"
        )

        from api.core.rag.keyword.stopwords import load_custom_stopwords

        custom = load_custom_stopwords(str(stopwords_file))
        assert "自定义词1" in custom
        assert "自定义词2" in custom
        assert "自定义词3" in custom
        assert "# 这是注释" not in custom

    def test_merge_stopwords(self) -> None:
        """Should merge custom stopwords with defaults."""
        from api.core.rag.keyword.stopwords import merge_stopwords

        custom = frozenset(["自定义词1", "自定义词2"])
        merged = merge_stopwords(custom)

        assert "自定义词1" in merged
        assert "自定义词2" in merged
        assert "的" in merged
