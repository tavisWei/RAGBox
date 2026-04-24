from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


class PromptTemplateParser:
    VAR_PATTERN = re.compile(
        r"\{\{\s*(\w+(?:\.\w+)*)\s*(?:\|\s*(\w+)(?:\('([^']*)'\))?)?\s*\}\}"
    )
    IF_PATTERN = re.compile(
        r"\{%\s*if\s+(\w+(?:\.\w+)*)\s*%\}"
        r"(.*?)"
        r"\{%\s*endif\s*%\}",
        re.DOTALL,
    )
    FOR_PATTERN = re.compile(
        r"\{%\s*for\s+(\w+)\s+in\s+(\w+(?:\.\w+)*)\s*%\}"
        r"(.*?)"
        r"\{%\s*endfor\s*%\}",
        re.DOTALL,
    )

    def __init__(self, template: str):
        self.template = template

    def render(self, variables: Optional[Dict[str, Any]] = None) -> str:
        variables = variables or {}
        result = self.template

        result = self._process_loops(result, variables)
        result = self._process_conditionals(result, variables)
        result = self._process_variables(result, variables)

        return result

    def _process_variables(self, text: str, variables: Dict[str, Any]) -> str:
        def replace_var(match: re.Match) -> str:
            var_path = match.group(1)
            filter_name = match.group(2)
            filter_arg = match.group(3)

            value = self._resolve_variable(var_path, variables)

            if value is None:
                if filter_name == "default" and filter_arg is not None:
                    return filter_arg
                return ""

            str_value = str(value)

            if filter_name == "upper":
                return str_value.upper()
            elif filter_name == "lower":
                return str_value.lower()
            elif filter_name == "title":
                return str_value.title()
            elif filter_name == "strip":
                return str_value.strip()

            return str_value

        return self.VAR_PATTERN.sub(replace_var, text)

    def _process_conditionals(self, text: str, variables: Dict[str, Any]) -> str:
        def replace_if(match: re.Match) -> str:
            var_path = match.group(1)
            content = match.group(2)

            value = self._resolve_variable(var_path, variables)

            if value:
                return self._process_variables(content, variables)
            else:
                return ""

        return self.IF_PATTERN.sub(replace_if, text)

    def _process_loops(self, text: str, variables: Dict[str, Any]) -> str:
        def replace_for(match: re.Match) -> str:
            item_name = match.group(1)
            collection_path = match.group(2)
            content = match.group(3)

            collection = self._resolve_variable(collection_path, variables)

            if not collection or not isinstance(collection, (list, tuple)):
                return ""

            results = []
            for item in collection:
                loop_vars = dict(variables)
                loop_vars[item_name] = item
                rendered = self._process_variables(content, loop_vars)
                rendered = self._process_conditionals(rendered, loop_vars)
                results.append(rendered)

            return "".join(results)

        return self.FOR_PATTERN.sub(replace_for, text)

    def _resolve_variable(self, path: str, variables: Dict[str, Any]) -> Any:
        parts = path.split(".")
        value = variables

        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            elif hasattr(value, part):
                value = getattr(value, part)
            else:
                return None

            if value is None:
                return None

        return value

    @classmethod
    def from_file(cls, filepath: str) -> "PromptTemplateParser":
        with open(filepath, "r", encoding="utf-8") as f:
            return cls(f.read())

    def get_variables(self) -> List[str]:
        variables = set()

        for match in self.VAR_PATTERN.finditer(self.template):
            variables.add(match.group(1).split(".")[0])

        for match in self.IF_PATTERN.finditer(self.template):
            variables.add(match.group(1).split(".")[0])

        for match in self.FOR_PATTERN.finditer(self.template):
            variables.add(match.group(2).split(".")[0])

        return sorted(variables)

    def validate(self, variables: Optional[Dict[str, Any]] = None) -> List[str]:
        required = self.get_variables()
        provided = set(variables.keys()) if variables else set()
        return [v for v in required if v not in provided]


def render_prompt(template: str, **kwargs: Any) -> str:
    return PromptTemplateParser(template).render(kwargs)
