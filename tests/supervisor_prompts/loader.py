from __future__ import annotations

import asyncio
import importlib
import inspect
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class PromptSpec:
    name: str
    loader: str
    callable: bool
    parameters: list[dict[str, Any]]
    description: str | None = None
    evaluation: dict[str, Any] | None = None


def load_specs(path: Path) -> list[PromptSpec]:
    data = json.loads(path.read_text())
    specs: list[PromptSpec] = []
    for raw in data:
        specs.append(
            PromptSpec(
                name=raw["name"],
                loader=raw["loader"],
                callable=bool(raw.get("callable")),
                parameters=list(raw.get("parameters") or []),
                description=raw.get("description"),
                evaluation=raw.get("evaluation"),
            )
        )
    return specs


def load_prompt(spec: PromptSpec) -> str:
    module_name, attr_name = spec.loader.split(":", maxsplit=1)
    module = importlib.import_module(module_name)
    target = getattr(module, attr_name)
    if not spec.callable:
        return str(target)
    return _invoke_callable(target, spec.parameters)


def _invoke_callable(callable_obj: Any, params: Iterable[dict[str, Any]]) -> str:
    kwargs: dict[str, Any] = {}
    for param in params:
        name = param["name"]
        if "default" in param:
            kwargs[name] = param["default"]
        elif param.get("required", False):
            kwargs[name] = _default_value_for(param)

    if inspect.iscoroutinefunction(callable_obj):
        return asyncio.run(callable_obj(**kwargs))
    if inspect.iscoroutine(callable_obj):
        return asyncio.run(callable_obj)
    return str(callable_obj(**kwargs))


def _default_value_for(param: dict[str, Any]) -> Any:
    param_type = (param.get("type") or "str").lower()
    match param_type:
        case "uuid":
            return "00000000-0000-0000-0000-000000000000"
        case "str":
            return ""
        case "optional[str]":
            return None
        case "list[tuple[str, str]]":
            return [("user", "Placeholder question"), ("assistant", "Placeholder answer")]
        case "dict[str, any]" | "dict":
            return {}
        case _:
            return None
