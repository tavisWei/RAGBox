import re
from typing import Any, List, Optional, Tuple

from api.core.rag.cleaner.clean_processor import CleanProcessor
from api.core.rag.extractor.entity.extract_setting import ExtractSetting
from api.core.rag.index_processor.index_processor_base import BaseIndexProcessor
from api.core.rag.models.document import Document
from api.core.rag.splitter.splitter_factory import SplitterFactory
from api.core.rag.splitter.splitter_types import SplitterConfig, SplitterType


class QAIndexProcessor(BaseIndexProcessor):
    def __init__(self, **kwargs):
        self.qa_pattern = kwargs.get(
            "qa_pattern",
            re.compile(
                r"(?:Q:|Question:|问题:|\d+\.)\s*(.+?)\s*\n"
                r"(?:A:|Answer:|答案:|\n)\s*(.+?)(?=\n(?:Q:|Question:|问题:|\d+\.)|$)",
                re.DOTALL | re.IGNORECASE,
            ),
        )
        self.llm_generate = kwargs.get("llm_generate", False)

    def extract(self, extract_setting: ExtractSetting, **kwargs) -> List[Document]:
        content = kwargs.get("content", "")
        if not content:
            return []
        return [Document(page_content=content)]

    def transform(self, documents: List[Document], **kwargs) -> List[Document]:
        process_rule = kwargs.get("process_rule")
        result = []

        for doc in documents:
            cleaned_text = CleanProcessor.clean(doc.page_content, process_rule)
            qa_pairs = self._extract_qa_pairs(cleaned_text)

            if not qa_pairs and self.llm_generate:
                qa_pairs = self._generate_qa_pairs(cleaned_text)

            for i, (question, answer) in enumerate(qa_pairs):
                qa_doc = Document(
                    page_content=f"Q: {question}\nA: {answer}",
                    metadata={
                        **(doc.metadata or {}),
                        "question": question,
                        "answer": answer,
                        "qa_index": i,
                        "total_qa": len(qa_pairs),
                    },
                )
                result.append(qa_doc)

        if not result:
            config = SplitterConfig(
                chunk_size=kwargs.get("chunk_size", 512),
                chunk_overlap=kwargs.get("chunk_overlap", 64),
            )
            splitter = SplitterFactory.create(SplitterType.RECURSIVE, config)
            for doc in documents:
                cleaned_text = CleanProcessor.clean(doc.page_content, process_rule)
                chunks = splitter.split_text(cleaned_text)
                for i, chunk in enumerate(chunks):
                    result.append(
                        Document(
                            page_content=chunk,
                            metadata={
                                **(doc.metadata or {}),
                                "chunk_index": i,
                                "total_chunks": len(chunks),
                            },
                        )
                    )

        return result

    def _extract_qa_pairs(self, text: str) -> List[Tuple[str, str]]:
        matches = self.qa_pattern.findall(text)
        return [(q.strip(), a.strip()) for q, a in matches]

    def _generate_qa_pairs(self, text: str) -> List[Tuple[str, str]]:
        return [("What is this document about?", text[:500])]

    def load(self, dataset_id: str, documents: List[Document], **kwargs) -> None:
        pass

    def clean(
        self, dataset_id: str, node_ids: Optional[List[str]] = None, **kwargs
    ) -> None:
        pass

    def retrieve(
        self, query: str, dataset_id: str, top_k: int, **kwargs
    ) -> List[Document]:
        return []
