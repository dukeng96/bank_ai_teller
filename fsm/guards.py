from __future__ import annotations
from typing import Any, Dict


class _AttrCtx:
    """Wraps a dict to provide attribute-style access that mutates the source."""

    def __init__(self, data: Dict[str, Any]):
        object.__setattr__(self, "_data", data)

    def __getattr__(self, name: str) -> Any:
        data = object.__getattribute__(self, "_data")
        if name in data:
            return data[name]
        raise AttributeError(name)

    def __setattr__(self, name: str, value: Any) -> None:
        data = object.__getattribute__(self, "_data")
        data[name] = value


def _ctx_proxy(ctx: Dict[str, Any]) -> _AttrCtx:
    return _AttrCtx(ctx)

def eval_guard(expr: str, ctx: Dict[str, Any]) -> bool:
    if not expr:
        return True
    return bool(eval(expr, {}, {"ctx": _ctx_proxy(ctx)}))

def apply_after(expr: str, ctx: Dict[str, Any]) -> None:
    if not expr:
        return
    exec(expr, {}, {"ctx": _ctx_proxy(ctx)})
