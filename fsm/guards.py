from __future__ import annotations
from typing import Dict, Any

def eval_guard(expr: str, ctx: Dict[str, Any]) -> bool:
    if not expr:
        return True
    return bool(eval(expr, {}, {"ctx": ctx}))

def apply_after(expr: str, ctx: Dict[str, Any]) -> None:
    if not expr:
        return
    exec(expr, {}, {"ctx": ctx})
