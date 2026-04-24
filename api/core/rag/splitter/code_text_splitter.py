from typing import List, Optional, Dict
from .base_splitter import BaseTextSplitter
from .splitter_types import SplitterConfig

LANGUAGE_SEPARATORS = {
    "python": ["\nclass ", "\ndef ", "\n\tdef ", "\nif __name__"],
    "javascript": ["\nfunction ", "\nconst ", "\nlet ", "\nclass "],
    "typescript": ["\nfunction ", "\nconst ", "\nclass ", "\ninterface "],
    "java": ["\npublic class ", "\nclass ", "\npublic void ", "\nprivate "],
    "go": ["\nfunc ", "\ntype ", "\nvar ", "\nconst "],
    "rust": ["\nfn ", "\nstruct ", "\nimpl ", "\nmod "],
    "default": ["\n\n", "\n", " ", ""],
}


class CodeAwareTextSplitter(BaseTextSplitter):
    def __init__(
        self,
        config: Optional[SplitterConfig] = None,
        language: Optional[str] = None,
        **kwargs,
    ):
        if config is None:
            config = SplitterConfig(**kwargs)
        super().__init__(config)

        self._language = language or config.language or "default"
        self._separators = LANGUAGE_SEPARATORS.get(
            self._language, LANGUAGE_SEPARATORS["default"]
        )

    def split_text(self, text: str) -> List[str]:
        if not text:
            return []
        return self._split_recursive(text, self._separators)

    def _split_recursive(self, text: str, separators: List[str]) -> List[str]:
        if not separators:
            return [text] if text else []

        separator = separators[0]
        remaining = separators[1:]

        if separator not in text:
            return self._split_recursive(text, remaining)

        splits = [s for s in text.split(separator) if s.strip()]
        chunks = []

        for split in splits:
            if len(split) <= self.config.chunk_size:
                chunks.append(split)
            else:
                if remaining:
                    chunks.extend(self._split_recursive(split, remaining))
                else:
                    for i in range(0, len(split), self.config.chunk_size):
                        chunks.append(split[i : i + self.config.chunk_size])

        return chunks

    @classmethod
    def from_config(cls, config: SplitterConfig) -> "CodeAwareTextSplitter":
        return cls(config=config, language=config.language)
