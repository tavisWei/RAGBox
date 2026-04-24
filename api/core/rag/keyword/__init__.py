"""
Keyword extraction module for RAG systems.

This module provides Chinese keyword extraction using jieba with TF-IDF,
along with keyword table management for efficient document retrieval.

Components:
- JiebaKeywordExtractor: Extract keywords from Chinese text using TF-IDF
- KeywordTableHandler: Build and manage inverted keyword indices
- STOPWORDS: Chinese and English stopwords for filtering

Example:
    from api.core.rag.keyword import JiebaKeywordExtractor, KeywordTableHandler

    # Extract keywords
    extractor = JiebaKeywordExtractor(max_keywords_per_chunk=10)
    keywords = extractor.extract("人工智能技术在近年来取得了显著进展")

    # Build keyword table
    handler = KeywordTableHandler()
    handler.add_document("doc1", text="人工智能技术发展迅速")
    results = handler.search("人工智能")
"""

from api.core.rag.keyword.jieba_extractor import JiebaKeywordExtractor
from api.core.rag.keyword.keyword_table_handler import KeywordTableHandler
from api.core.rag.keyword.stopwords import (
    STOPWORDS,
    is_stopword,
    load_custom_stopwords,
    merge_stopwords,
)

__all__ = [
    "JiebaKeywordExtractor",
    "KeywordTableHandler",
    "STOPWORDS",
    "is_stopword",
    "load_custom_stopwords",
    "merge_stopwords",
]
