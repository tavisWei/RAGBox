"""
Keyword table handler for building and managing inverted keyword indices.

This module provides functionality to build and maintain keyword tables (inverted indices)
that map keywords to document IDs. This is essential for keyword-based retrieval in RAG
systems, enabling fast lookup of documents containing specific keywords.

The keyword table is an inverted index structure:
    keyword -> set[document_id]

Key Features:
- Build keyword tables from documents
- Add/remove documents from the index
- Search documents by keywords
- Support for multiple keyword matching with ranking

Usage:
    handler = KeywordTableHandler()
    handler.add_document("doc1", {"人工智能", "技术", "发展"})
    handler.add_document("doc2", {"机器学习", "技术", "应用"})

    # Search for documents containing "技术"
    doc_ids = handler.search("技术")
    # Returns: ["doc1", "doc2"]

    # Search with multiple keywords
    doc_ids = handler.search("人工智能 技术")
    # Returns ranked by keyword match count
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import TYPE_CHECKING

from api.core.rag.keyword.jieba_extractor import JiebaKeywordExtractor

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class KeywordTableHandler:
    """
    Manage keyword table (inverted index) for document retrieval.

    This class builds and maintains an inverted index mapping keywords
    to document IDs, enabling efficient keyword-based document retrieval.

    Attributes:
        _keyword_table: The inverted index (keyword -> set of doc_ids).
        _extractor: The keyword extractor instance.

    Example:
        >>> handler = KeywordTableHandler()
        >>> handler.add_document("doc1", {"人工智能", "技术"})
        >>> handler.search("人工智能")
        ['doc1']
    """

    _keyword_table: dict[str, set[str]]
    _extractor: JiebaKeywordExtractor

    def __init__(self, max_keywords_per_chunk: int = 10) -> None:
        """
        Initialize the keyword table handler.

        Args:
            max_keywords_per_chunk: Maximum keywords to extract per document.
        """
        self._keyword_table = {}
        self._extractor = JiebaKeywordExtractor(max_keywords_per_chunk)

    @property
    def keyword_table(self) -> dict[str, set[str]]:
        """Get the current keyword table (read-only view)."""
        return dict(self._keyword_table)

    def add_document(
        self, doc_id: str, keywords: set[str] | None = None, text: str | None = None
    ) -> None:
        """
        Add a document to the keyword table.

        Either keywords or text must be provided. If text is provided,
        keywords will be extracted automatically.

        Args:
            doc_id: Unique identifier for the document.
            keywords: Pre-extracted keywords (optional).
            text: Text to extract keywords from (optional).

        Raises:
            ValueError: If neither keywords nor text is provided.

        Example:
            >>> handler = KeywordTableHandler()
            >>> handler.add_document("doc1", keywords={"AI", "技术"})
            >>> handler.add_document("doc2", text="人工智能发展迅速")
        """
        if keywords is None and text is None:
            raise ValueError("Either keywords or text must be provided")

        if keywords is None:
            keywords = self._extractor.extract(text)  # type: ignore[arg-type]

        for keyword in keywords:
            if keyword not in self._keyword_table:
                self._keyword_table[keyword] = set()
            self._keyword_table[keyword].add(doc_id)

    def add_documents(self, documents: dict[str, str]) -> None:
        """
        Add multiple documents to the keyword table.

        Args:
            documents: Dictionary mapping doc_id to text content.

        Example:
            >>> handler = KeywordTableHandler()
            >>> docs = {"doc1": "人工智能技术", "doc2": "机器学习算法"}
            >>> handler.add_documents(docs)
        """
        for doc_id, text in documents.items():
            self.add_document(doc_id, text=text)

    def remove_document(self, doc_id: str) -> None:
        """
        Remove a document from the keyword table.

        Args:
            doc_id: The document ID to remove.

        Example:
            >>> handler = KeywordTableHandler()
            >>> handler.add_document("doc1", keywords={"AI"})
            >>> handler.remove_document("doc1")
        """
        keywords_to_delete: set[str] = set()

        for keyword, doc_ids in self._keyword_table.items():
            if doc_id in doc_ids:
                doc_ids.discard(doc_id)
                if not doc_ids:
                    keywords_to_delete.add(keyword)

        for keyword in keywords_to_delete:
            del self._keyword_table[keyword]

    def remove_documents(self, doc_ids: list[str]) -> None:
        """
        Remove multiple documents from the keyword table.

        Args:
            doc_ids: List of document IDs to remove.
        """
        for doc_id in doc_ids:
            self.remove_document(doc_id)

    def search(self, query: str, top_k: int = 10) -> list[str]:
        """
        Search for documents matching the query keywords.

        Documents are ranked by the number of matching keywords.

        Args:
            query: The search query (text or keywords).
            top_k: Maximum number of documents to return.

        Returns:
            List of document IDs ranked by keyword match count.

        Example:
            >>> handler = KeywordTableHandler()
            >>> handler.add_document("doc1", keywords={"AI", "技术"})
            >>> handler.add_document("doc2", keywords={"AI", "应用"})
            >>> handler.search("AI 技术")
            ['doc1', 'doc2']  # doc1 matches 2 keywords, doc2 matches 1
        """
        query_keywords = self._extractor.extract(query)

        doc_match_count: dict[str, int] = defaultdict(int)

        for keyword in query_keywords:
            if keyword in self._keyword_table:
                for doc_id in self._keyword_table[keyword]:
                    doc_match_count[doc_id] += 1

        sorted_docs = sorted(
            doc_match_count.keys(),
            key=lambda x: doc_match_count[x],
            reverse=True,
        )

        return sorted_docs[:top_k]

    def search_by_keywords(self, keywords: set[str], top_k: int = 10) -> list[str]:
        """
        Search for documents by pre-defined keywords.

        Args:
            keywords: Set of keywords to search for.
            top_k: Maximum number of documents to return.

        Returns:
            List of document IDs ranked by keyword match count.

        Example:
            >>> handler = KeywordTableHandler()
            >>> handler.add_document("doc1", keywords={"AI", "技术"})
            >>> handler.search_by_keywords({"AI"})
            ['doc1']
        """
        doc_match_count: dict[str, int] = defaultdict(int)

        for keyword in keywords:
            if keyword in self._keyword_table:
                for doc_id in self._keyword_table[keyword]:
                    doc_match_count[doc_id] += 1

        sorted_docs = sorted(
            doc_match_count.keys(),
            key=lambda x: doc_match_count[x],
            reverse=True,
        )

        return sorted_docs[:top_k]

    def get_document_keywords(self, doc_id: str) -> set[str]:
        """
        Get all keywords associated with a document.

        Args:
            doc_id: The document ID.

        Returns:
            Set of keywords associated with the document.

        Example:
            >>> handler = KeywordTableHandler()
            >>> handler.add_document("doc1", keywords={"AI", "技术"})
            >>> handler.get_document_keywords("doc1")
            {'AI', '技术'}
        """
        keywords: set[str] = set()
        for keyword, doc_ids in self._keyword_table.items():
            if doc_id in doc_ids:
                keywords.add(keyword)
        return keywords

    def document_exists(self, doc_id: str) -> bool:
        """
        Check if a document exists in the keyword table.

        Args:
            doc_id: The document ID to check.

        Returns:
            True if the document exists, False otherwise.
        """
        for doc_ids in self._keyword_table.values():
            if doc_id in doc_ids:
                return True
        return False

    def clear(self) -> None:
        """Clear all entries from the keyword table."""
        self._keyword_table.clear()

    def get_stats(self) -> dict[str, int]:
        """
        Get statistics about the keyword table.

        Returns:
            Dictionary with statistics:
            - total_keywords: Total number of unique keywords
            - total_documents: Total number of unique documents
            - total_entries: Total keyword-document pairs

        Example:
            >>> handler = KeywordTableHandler()
            >>> handler.add_document("doc1", keywords={"AI", "技术"})
            >>> handler.get_stats()
            {'total_keywords': 2, 'total_documents': 1, 'total_entries': 2}
        """
        all_doc_ids: set[str] = set()
        total_entries = 0

        for doc_ids in self._keyword_table.values():
            all_doc_ids.update(doc_ids)
            total_entries += len(doc_ids)

        return {
            "total_keywords": len(self._keyword_table),
            "total_documents": len(all_doc_ids),
            "total_entries": total_entries,
        }

    def export_table(self) -> dict[str, list[str]]:
        """
        Export the keyword table as a serializable dictionary.

        Returns:
            Dictionary mapping keywords to lists of document IDs.

        Example:
            >>> handler = KeywordTableHandler()
            >>> handler.add_document("doc1", keywords={"AI"})
            >>> handler.export_table()
            {'AI': ['doc1']}
        """
        return {
            keyword: list(doc_ids) for keyword, doc_ids in self._keyword_table.items()
        }

    def import_table(self, table: dict[str, list[str]]) -> None:
        """
        Import a keyword table from a serialized dictionary.

        Args:
            table: Dictionary mapping keywords to lists of document IDs.

        Example:
            >>> handler = KeywordTableHandler()
            >>> handler.import_table({"AI": ["doc1", "doc2"]})
            >>> handler.search("AI")
            ['doc1', 'doc2']
        """
        self._keyword_table = {
            keyword: set(doc_ids) for keyword, doc_ids in table.items()
        }
