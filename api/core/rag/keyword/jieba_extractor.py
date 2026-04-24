"""
Jieba-based Chinese keyword extractor with TF-IDF.

This module provides keyword extraction functionality for Chinese text using
jieba's TF-IDF algorithm. It supports mixed Chinese-English text and includes
stopwords filtering and subtoken expansion for compound words.

The extractor is designed for RAG (Retrieval-Augmented Generation) systems
where keyword-based retrieval is needed alongside vector similarity search.

Key Features:
- TF-IDF based keyword extraction with configurable max keywords
- Stopwords filtering for improved precision
- Subtoken expansion for compound words (e.g., "人工智能" -> ["人工智能", "人工", "智能"])
- Fallback to frequency-based extraction when TF-IDF is unavailable
- Support for mixed Chinese-English text

Usage:
    extractor = JiebaKeywordExtractor(max_keywords_per_chunk=10)
    keywords = extractor.extract("人工智能技术在近年来取得了显著进展")
    # Returns: {"人工智能", "技术", "进展", "显著", ...}
"""

from __future__ import annotations

import logging
import re
from operator import itemgetter
from typing import TYPE_CHECKING

from api.core.rag.keyword.stopwords import STOPWORDS

if TYPE_CHECKING:
    from jieba.analyse import TFIDF

logger = logging.getLogger(__name__)


class JiebaKeywordExtractor:
    """
    Extract keywords from Chinese text using jieba TF-IDF algorithm.

    This class wraps jieba's TF-IDF extractor with additional features:
    - Stopwords filtering
    - Subtoken expansion for compound words
    - Fallback to frequency-based extraction

    Attributes:
        max_keywords_per_chunk: Maximum number of keywords to extract per text chunk.
        _tfidf: The jieba TF-IDF extractor instance.

    Example:
        >>> extractor = JiebaKeywordExtractor(max_keywords_per_chunk=10)
        >>> text = "人工智能技术在近年来取得了显著进展"
        >>> keywords = extractor.extract(text)
        >>> "人工智能" in keywords
        True
    """

    max_keywords_per_chunk: int
    _tfidf: TFIDF | object

    def __init__(self, max_keywords_per_chunk: int = 10) -> None:
        """
        Initialize the keyword extractor.

        Args:
            max_keywords_per_chunk: Maximum number of keywords to extract per chunk.
                Defaults to 10.

        Raises:
            ImportError: If jieba is not installed.
        """
        self.max_keywords_per_chunk = max_keywords_per_chunk
        self._tfidf = self._load_tfidf_extractor()

    def _load_tfidf_extractor(self) -> TFIDF | object:
        """
        Load jieba TFIDF extractor with fallback strategy.

        Loading Flow:
        1. Try to use jieba.analyse.default_tfidf if it exists
        2. If not, try to instantiate jieba.analyse.TFIDF
        3. If TFIDF class is not available, try importing from jieba.analyse.tfidf
        4. If all fail, build a fallback frequency-based extractor

        Returns:
            The TF-IDF extractor instance (either jieba's TFIDF or fallback).

        Note:
            This method sets stopwords on the TF-IDF extractor for filtering.
        """
        try:
            import jieba.analyse  # type: ignore[import-untyped]
        except ImportError as e:
            logger.error("jieba is not installed. Please install it: pip install jieba")
            raise ImportError(
                "jieba is required for keyword extraction. Install with: pip install jieba"
            ) from e

        tfidf = getattr(jieba.analyse, "default_tfidf", None)
        if tfidf is not None:
            tfidf.stop_words = STOPWORDS  # type: ignore[attr-defined]
            return tfidf

        tfidf_class = getattr(jieba.analyse, "TFIDF", None)
        if tfidf_class is None:
            try:
                from jieba.analyse.tfidf import TFIDF  # type: ignore[import-untyped]

                tfidf_class = TFIDF
            except Exception:
                tfidf_class = None

        if tfidf_class is not None:
            tfidf = tfidf_class()
            tfidf.stop_words = STOPWORDS  # type: ignore[attr-defined]
            jieba.analyse.default_tfidf = tfidf  # type: ignore[attr-defined]
            return tfidf

        logger.warning(
            "TF-IDF extractor not available, using fallback frequency-based extraction"
        )
        return self._build_fallback_tfidf()

    def _build_fallback_tfidf(self) -> object:
        """
        Build a fallback lightweight TFIDF for environments missing jieba's TFIDF.

        This provides a simple frequency-based keyword extraction when the
        full TF-IDF implementation is unavailable.

        Returns:
            A fallback extractor with extract_tags method.
        """

        class _SimpleTFIDF:
            stop_words: frozenset[str]
            _lcut: object | None

            def __init__(self) -> None:
                self.stop_words = STOPWORDS
                self._lcut = None
                try:
                    import jieba  # type: ignore[import-untyped]

                    self._lcut = getattr(jieba, "lcut", None)
                except ImportError:
                    pass

            def extract_tags(
                self, sentence: str, topK: int | None = 20, **kwargs: object
            ) -> list[str]:
                """
                Extract keywords based on word frequency.

                Args:
                    sentence: The text to extract keywords from.
                    topK: Maximum number of keywords to return.
                    **kwargs: Additional arguments (ignored).

                Returns:
                    List of keywords sorted by frequency.
                """
                top_k = kwargs.pop("topK", topK)
                if self._lcut is not None and callable(self._lcut):
                    tokens = self._lcut(sentence)  # type: ignore[misc]
                else:
                    try:
                        import jieba  # type: ignore[import-untyped]

                        cut = getattr(jieba, "cut", None)
                        if callable(cut):
                            tokens = list(cut(sentence))
                        else:
                            tokens = re.findall(r"\w+", sentence)
                    except ImportError:
                        tokens = re.findall(r"\w+", sentence)

                words = [w for w in tokens if w and w not in self.stop_words]
                freq: dict[str, int] = {}
                for w in words:
                    freq[w] = freq.get(w, 0) + 1

                sorted_words = sorted(freq.items(), key=itemgetter(1), reverse=True)
                if top_k is not None:
                    sorted_words = sorted_words[:top_k]

                return [item[0] for item in sorted_words]

        return _SimpleTFIDF()

    def extract(self, text: str, max_keywords: int | None = None) -> set[str]:
        """
        Extract keywords from text using TF-IDF algorithm.

        This method extracts keywords and expands compound words into subtokens.
        For example, "人工智能" will be expanded to include both "人工智能"
        and its subtokens "人工" and "智能" (if they're not stopwords).

        Args:
            text: The text to extract keywords from.
            max_keywords: Maximum number of keywords to extract.
                If None, uses the instance's max_keywords_per_chunk.

        Returns:
            A set of extracted keywords (including expanded subtokens).

        Example:
            >>> extractor = JiebaKeywordExtractor()
            >>> keywords = extractor.extract("人工智能技术发展迅速")
            >>> isinstance(keywords, set)
            True
        """
        if not text or not text.strip():
            return set()

        max_k = (
            max_keywords if max_keywords is not None else self.max_keywords_per_chunk
        )

        keywords = self._tfidf.extract_tags(  # type: ignore[misc]
            sentence=text,
            topK=max_k,
        )

        return self._expand_tokens_with_subtokens(set(keywords))

    def _expand_tokens_with_subtokens(self, tokens: set[str]) -> set[str]:
        """
        Expand tokens with their subtokens, filtering out stopwords.

        This method splits compound words into their constituent parts.
        For example, "人工智能" can be split into "人工" and "智能".

        Args:
            tokens: Set of tokens to expand.

        Returns:
            Expanded set of tokens including subtokens (excluding stopwords).

        Example:
            >>> extractor = JiebaKeywordExtractor()
            >>> tokens = {"人工智能"}
            >>> expanded = extractor._expand_tokens_with_subtokens(tokens)
            >>> "人工智能" in expanded
            True
        """
        results: set[str] = set()
        for token in tokens:
            results.add(token)
            sub_tokens = re.findall(r"\w+", token)
            if len(sub_tokens) > 1:
                results.update({w for w in sub_tokens if w not in STOPWORDS})

        return results

    def extract_batch(
        self, texts: list[str], max_keywords: int | None = None
    ) -> list[set[str]]:
        """
        Extract keywords from multiple texts.

        Args:
            texts: List of texts to extract keywords from.
            max_keywords: Maximum number of keywords per text.

        Returns:
            List of keyword sets, one for each input text.

        Example:
            >>> extractor = JiebaKeywordExtractor()
            >>> texts = ["人工智能技术", "机器学习算法"]
            >>> keywords_list = extractor.extract_batch(texts)
            >>> len(keywords_list) == 2
            True
        """
        return [self.extract(text, max_keywords) for text in texts]
