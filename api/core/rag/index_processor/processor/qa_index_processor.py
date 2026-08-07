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
        # Sync callable (prompt: str) -> str used when llm_generate is on.
        self.llm_function = kwargs.get("llm_function")

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
        """Generate Q/A pairs with an LLM and parse them with the QA pattern.

        Returns an empty list when no llm_function is configured; the caller
        then falls back to plain chunk splitting.
        """
        if not self.llm_function:
            return []
        prompt = (
            "请根据以下文档内容生成问答对，用于构建问答检索索引。\n"
            "要求：覆盖文档的关键信息，问题简洁明确，答案忠实于原文。\n"
            "每对格式严格为两行：\nQ: <问题>\nA: <答案>\n\n"
            f"文档内容：\n{text[:4000]}"
        )
        try:
            response = self.llm_function(prompt)
        except Exception:
            return []
        return self._extract_qa_pairs(response or "")

    def load(self, dataset_id: str, documents: List[Document], **kwargs) -> None:
        data_store = kwargs.get("data_store")
        if data_store is None:
            raise ValueError("load requires a data_store")
        self._load_to_store(
            dataset_id, documents, data_store, kwargs.get("embeddings")
        )

    def clean(
        self, dataset_id: str, node_ids: Optional[List[str]] = None, **kwargs
    ) -> None:
        data_store = kwargs.get("data_store")
        if data_store is None:
            raise ValueError("clean requires a data_store")
        self._clean_from_store(dataset_id, data_store, node_ids)

    def retrieve(
        self, query: str, dataset_id: str, top_k: int, **kwargs
    ) -> List[Document]:
        data_store = kwargs.get("data_store")
        if data_store is None:
            raise ValueError("retrieve requires a data_store")
        return self._retrieve_from_store(
            query,
            dataset_id,
            top_k,
            data_store,
            query_vector=kwargs.get("query_vector"),
            search_method=kwargs.get("search_method", "hybrid"),
        )
