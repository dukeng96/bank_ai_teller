from __future__ import annotations
from collections.abc import MutableMapping
from typing import Any, Dict


class _ContextProxy:
    """Provide attribute-style access to a mutable mapping."""

    def __init__(self, data: MutableMapping[str, Any]) -> None:
        object.__setattr__(self, "_data", data)

    def __getattr__(self, name: str) -> Any:
        try:
            return self._data[name]
        except KeyError as exc:  # pragma: no cover - defensive, matches AttributeError contract
            raise AttributeError(name) from exc

    def __setattr__(self, name: str, value: Any) -> None:
        self._data[name] = value

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self._data[key] = value


def _wrap_ctx(ctx: Dict[str, Any]) -> Any:
    if isinstance(ctx, MutableMapping):
        return _ContextProxy(ctx)
    return ctx

def eval_guard(expr: str, ctx: Dict[str, Any]) -> bool:
    if not expr:
        return True
    return bool(eval(expr, {}, {"ctx": _wrap_ctx(ctx)}))

def apply_after(expr: str, ctx: Dict[str, Any]) -> None:
    if not expr:
        return
    exec(expr, {}, {"ctx": _wrap_ctx(ctx)})
