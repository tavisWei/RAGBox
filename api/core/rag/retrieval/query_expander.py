from typing import List, Optional, Callable
from dataclasses import dataclass
from .retrieval_config import QueryExpansionMode


@dataclass
class ExpandedQuery:
    query: str
    original: str
    expansion_type: str
    score: float = 1.0


class QueryExpander:
    def __init__(
        self,
        mode: QueryExpansionMode = QueryExpansionMode.NONE,
        llm_function: Optional[Callable] = None,
        expansion_count: int = 3,
    ):
        self.mode = mode
        self.llm_function = llm_function
        self.expansion_count = expansion_count

    def expand(self, query: str) -> List[ExpandedQuery]:
        if self.mode == QueryExpansionMode.NONE:
            return [
                ExpandedQuery(query=query, original=query, expansion_type="original")
            ]
        elif self.mode == QueryExpansionMode.MULTI_QUERY:
            return self._expand_multi_query(query)
        elif self.mode == QueryExpansionMode.HYDE:
            return self._expand_hyde(query)
        else:
            return [
                ExpandedQuery(query=query, original=query, expansion_type="original")
            ]

    def _expand_multi_query(self, query: str) -> List[ExpandedQuery]:
        results = [
            ExpandedQuery(
                query=query, original=query, expansion_type="original", score=1.0
            )
        ]

        if not self.llm_function:
            return results

        prompt = f"""Generate {self.expansion_count} different search queries for: {query}
Return one per line, no numbering."""

        try:
            response = self.llm_function(prompt)
            lines = response.strip().split("\n")
            for i, line in enumerate(lines[: self.expansion_count]):
                line = line.strip()
                if line and line != query:
                    results.append(
                        ExpandedQuery(
                            query=line,
                            original=query,
                            expansion_type="multi_query",
                            score=0.8 - (i * 0.1),
                        )
                    )
        except Exception:
            pass

        return results

    def _expand_hyde(self, query: str) -> List[ExpandedQuery]:
        results = [
            ExpandedQuery(
                query=query, original=query, expansion_type="original", score=1.0
            )
        ]

        if not self.llm_function:
            return results

        prompt = f"""Write a hypothetical document that answers: {query}"""

        try:
            hypothetical_doc = self.llm_function(prompt)
            results.append(
                ExpandedQuery(
                    query=hypothetical_doc,
                    original=query,
                    expansion_type="hyde",
                    score=0.9,
                )
            )
        except Exception:
            pass

        return results
