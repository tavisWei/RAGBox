from __future__ import annotations

import logging
from collections import defaultdict
from typing import Dict, List, Optional

from api.core.agent.entities import AgentMessage

logger = logging.getLogger(__name__)


class TokenBufferMemory:
    CHARS_PER_TOKEN = 4

    def __init__(self, max_tokens: int = 8000, max_messages: Optional[int] = None):
        self.max_tokens = max_tokens
        self.max_messages = max_messages
        self._buffers: Dict[str, List[AgentMessage]] = defaultdict(list)
        self._token_counts: Dict[str, int] = defaultdict(int)

    def add_message(self, conversation_id: str, message: AgentMessage) -> None:
        msg_tokens = self._estimate_tokens(message.content)

        while self._token_counts[conversation_id] + msg_tokens > self.max_tokens or (
            self.max_messages
            and len(self._buffers[conversation_id]) >= self.max_messages
        ):
            if not self._buffers[conversation_id]:
                break
            removed = self._buffers[conversation_id].pop(0)
            self._token_counts[conversation_id] -= self._estimate_tokens(
                removed.content
            )
            if self._token_counts[conversation_id] < 0:
                self._token_counts[conversation_id] = 0

        self._buffers[conversation_id].append(message)
        self._token_counts[conversation_id] += msg_tokens

        logger.debug(
            f"Memory[{conversation_id}]: {len(self._buffers[conversation_id])} messages, "
            f"~{self._token_counts[conversation_id]} tokens"
        )

    def get_messages(self, conversation_id: str) -> List[AgentMessage]:
        return list(self._buffers[conversation_id])

    def get_last_n_messages(self, conversation_id: str, n: int) -> List[AgentMessage]:
        return self._buffers[conversation_id][-n:]

    def clear(self, conversation_id: Optional[str] = None) -> None:
        if conversation_id:
            self._buffers.pop(conversation_id, None)
            self._token_counts.pop(conversation_id, None)
            logger.info(f"Cleared memory for conversation: {conversation_id}")
        else:
            self._buffers.clear()
            self._token_counts.clear()
            logger.info("Cleared all memory")

    def get_token_count(self, conversation_id: str) -> int:
        return self._token_counts.get(conversation_id, 0)

    def get_message_count(self, conversation_id: str) -> int:
        return len(self._buffers.get(conversation_id, []))

    def _estimate_tokens(self, text: str) -> int:
        if not text:
            return 0
        return max(1, len(text) // self.CHARS_PER_TOKEN)

    def summarize_and_compress(
        self, conversation_id: str, summarizer: Optional[callable] = None
    ) -> None:
        messages = self._buffers[conversation_id]
        if len(messages) <= 2:
            return

        recent = messages[-2:]
        to_summarize = messages[:-2]

        if summarizer:
            summary_text = f"[Summary of {len(to_summarize)} earlier messages]"
        else:
            summary_text = f"[Summary of {len(to_summarize)} earlier messages]"

        summary_msg = AgentMessage(role="system", content=summary_text)
        self._buffers[conversation_id] = [summary_msg] + recent

        self._token_counts[conversation_id] = sum(
            self._estimate_tokens(m.content) for m in self._buffers[conversation_id]
        )

        logger.info(
            f"Compressed memory[{conversation_id}]: {len(messages)} -> "
            f"{len(self._buffers[conversation_id])} messages"
        )
