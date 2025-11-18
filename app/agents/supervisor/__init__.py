from __future__ import annotations

from typing import Any

__all__ = ["compile_supervisor_graph"]


def compile_supervisor_graph(*args: Any, **kwargs: Any):
    from .agent import compile_supervisor_graph as _compile_supervisor_graph

    return _compile_supervisor_graph(*args, **kwargs)
