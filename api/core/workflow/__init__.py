"""LangGraph-based workflow engine.

Compiles the existing workflow DSL (see api/api/workflows.py) into a
LangGraph StateGraph so graph scheduling, interruption and checkpointing
are handled by LangGraph instead of the hand-rolled polling loop.
"""
