import re
from typing import List, Optional, Tuple
from .base_splitter import BaseTextSplitter
from .splitter_types import SplitterConfig


class MarkdownTextSplitter(BaseTextSplitter):
    def __init__(
        self,
        config: Optional[SplitterConfig] = None,
        headers_to_split_on: Optional[List[Tuple[str, str]]] = None,
        **kwargs,
    ):
        if config is None:
            config = SplitterConfig(**kwargs)
        super().__init__(config)

        self._headers_to_split_on = headers_to_split_on or [
            ("#", "header1"),
            ("##", "header2"),
            ("###", "header3"),
        ]

    def split_text(self, text: str) -> List[str]:
        if not text:
            return []

        header_pattern = "|".join(re.escape(h[0]) for h in self._headers_to_split_on)
        pattern = rf"^({header_pattern})\s+(.+)$"

        sections = []
        current_section = []
        current_header = None

        for line in text.split("\n"):
            match = re.match(pattern, line)
            if match:
                if current_section:
                    sections.append((current_header, "\n".join(current_section)))
                current_header = line
                current_section = [line]
            else:
                current_section.append(line)

        if current_section:
            sections.append((current_header, "\n".join(current_section)))

        chunks = []
        for header, content in sections:
            if len(content) <= self.config.chunk_size:
                chunks.append(content)
            else:
                paragraphs = content.split("\n\n")
                current_chunk = []
                current_length = 0

                for para in paragraphs:
                    if current_length + len(para) + 2 <= self.config.chunk_size:
                        current_chunk.append(para)
                        current_length += len(para) + 2
                    else:
                        if current_chunk:
                            chunks.append("\n\n".join(current_chunk))
                        current_chunk = [para]
                        current_length = len(para)

                if current_chunk:
                    chunks.append("\n\n".join(current_chunk))

        return chunks

    @classmethod
    def from_config(cls, config: SplitterConfig) -> "MarkdownTextSplitter":
        return cls(config=config)
