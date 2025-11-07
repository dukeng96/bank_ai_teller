from __future__ import annotations
import time
from typing import Dict, Any

TIMER_KEY = "timers"

def ensure_timer_ctx(ctx: Dict[str, Any]) -> Dict[str, float]:
    timers = ctx.get(TIMER_KEY)
    if timers is None:
        timers = {}
        ctx[TIMER_KEY] = timers
    return timers

def set_timer(ctx: Dict[str, Any], name: str, secs: int, now: float | None = None) -> None:
    timers = ensure_timer_ctx(ctx)
    if now is None:
        now = time.time()
    timers[name] = now + secs

def clear_timer(ctx: Dict[str, Any], name: str) -> None:
    timers = ensure_timer_ctx(ctx)
    timers.pop(name, None)

def check_expired(ctx: Dict[str, Any], now: float | None = None) -> str | None:
    timers = ensure_timer_ctx(ctx)
    if now is None:
        now = time.time()
    expired = [k for k, v in timers.items() if v and now >= v]
    return expired[-1] if expired else None
