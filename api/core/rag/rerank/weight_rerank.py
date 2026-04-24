import math
import re
from collections import Counter
from typing import List, Optional

from api.core.rag.models.document import Document
from api.core.rag.rerank.rerank_base import BaseRerankRunner


class WeightRerankRunner(BaseRerankRunner):
    def __init__(
        self,
        vector_weight: float = 0.7,
        keyword_weight: float = 0.3,
        **kwargs,
    ):
        self.vector_weight = vector_weight
        self.keyword_weight = keyword_weight

    def run(
        self,
        query: str,
        documents: List[Document],
        score_threshold: Optional[float] = None,
        top_n: Optional[int] = None,
    ) -> List[Document]:
        if not documents:
            return []

        query_tokens = self._tokenize(query)
        doc_texts = [doc.page_content for doc in documents]
        keyword_scores = self._compute_tfidf_scores(query_tokens, doc_texts)

        reranked = []
        for i, doc in enumerate(documents):
            vector_score = (
                doc.metadata.get("vector_score", 0.0) if doc.metadata else 0.0
            )
            keyword_score = keyword_scores[i]

            combined_score = (
                self.vector_weight * vector_score + self.keyword_weight * keyword_score
            )

            doc.metadata = {
                **(doc.metadata or {}),
                "combined_score": combined_score,
                "vector_score": vector_score,
                "keyword_score": keyword_score,
            }
            reranked.append(doc)

        reranked.sort(key=lambda d: d.metadata.get("combined_score", 0.0), reverse=True)

        if score_threshold is not None:
            reranked = [
                d
                for d in reranked
                if d.metadata.get("combined_score", 0.0) >= score_threshold
            ]

        if top_n is not None:
            reranked = reranked[:top_n]

        return reranked

    def _tokenize(self, text: str) -> List[str]:
        text = text.lower()
        tokens = re.findall(r"\b\w+\b", text)
        return tokens

    def _compute_tfidf_scores(
        self, query_tokens: List[str], documents: List[str]
    ) -> List[float]:
        if not documents:
            return []

        tokenized_docs = [self._tokenize(doc) for doc in documents]
        doc_freq = Counter()
        for tokens in tokenized_docs:
            unique_tokens = set(tokens)
            for token in unique_tokens:
                doc_freq[token] += 1

        num_docs = len(documents)
        scores = []

        for tokens in tokenized_docs:
            doc_counter = Counter(tokens)
            score = 0.0
            for token in query_tokens:
                tf = doc_counter.get(token, 0)
                if tf > 0:
                    idf = math.log((num_docs + 1) / (doc_freq.get(token, 0) + 1)) + 1
                    score += tf * idf
            scores.append(score)

        max_score = max(scores) if scores else 1.0
        if max_score > 0:
            scores = [s / max_score for s in scores]

        return scores
