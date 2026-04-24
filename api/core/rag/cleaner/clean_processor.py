from __future__ import annotations

import re
from typing import Any, Optional


class CleanProcessor:
    @classmethod
    def clean(cls, text: str, process_rule: Optional[dict[str, Any]] = None) -> str:
        text = re.sub(r"<\|", "<", text)
        text = re.sub(r"\|>", ">", text)
        text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F\xEF\xBF\xBE]", "", text)
        text = re.sub("\ufffe", "", text)

        if process_rule and "rules" in process_rule:
            rules = process_rule["rules"]
            if "pre_processing_rules" in rules:
                for rule in rules["pre_processing_rules"]:
                    if rule["id"] == "remove_extra_spaces" and rule.get("enabled"):
                        text = re.sub(r"\n{3,}", "\n\n", text)
                        pattern = r"[\t\f\r\x20\u00a0\u1680\u180e\u2000-\u200a\u202f\u205f\u3000]{2,}"
                        text = re.sub(pattern, " ", text)
                    elif rule["id"] == "remove_urls_emails" and rule.get("enabled"):
                        pattern = r"([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)"
                        text = re.sub(pattern, "", text)
                        url_pattern = r"https?://\S+"
                        text = re.sub(url_pattern, "", text)
        return text
