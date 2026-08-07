"""LangGraph state schema for the workflow engine."""

import operator
from typing import Annotated, Any, Dict, List, TypedDict

# Internal context key used to propagate node failure to the edge routers.
# Stripped from any user-visible context before persisting or returning.
FAILED_CONTEXT_KEY = "__workflow_failed_node_id__"

# LangGraph treats a falsy resume payload (e.g. an empty dict) as "no resume
# value" and re-raises the interrupt, so an empty resume is wrapped with this
# sentinel key; approval nodes strip it before merging into the context.
EMPTY_RESUME_KEY = "__workflow_empty_resume__"


def _merge_dict(left: Dict[str, Any], right: Dict[str, Any]) -> Dict[str, Any]:
    return {**left, **right}


class WorkflowState(TypedDict, total=False):
    # Flat workflow context. Nodes return only the keys they changed and the
    # merge reducer folds them in, so parallel branches cannot clobber each
    # other (the legacy engine shared one mutable dict).
    context: Annotated[Dict[str, Any], _merge_dict]
    # One trace per executed node, appended in completion order.
    traces: Annotated[List[Dict[str, Any]], operator.add]
