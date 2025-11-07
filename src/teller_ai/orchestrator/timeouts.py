from __future__ import annotations

import time
from typing import Any, Dict

from teller_ai.config import cfg_path

TIMER_KEY = "timers"
TRACE_ENABLED = bool(cfg_path("trace", "enabled", default=False))

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
    if TRACE_ENABLED:
        print(f"[TRACE timer] set {name} in {secs}s -> {timers[name]:.3f}")

def clear_timer(ctx: Dict[str, Any], name: str) -> None:
    timers = ensure_timer_ctx(ctx)
    timers.pop(name, None)
    if TRACE_ENABLED:
        print(f"[TRACE timer] clear {name}")

def check_expired(ctx: Dict[str, Any], now: float | None = None) -> str | None:
    timers = ensure_timer_ctx(ctx)
    if now is None:
        now = time.time()
    expired = [k for k, v in timers.items() if v and now >= v]
    if expired and TRACE_ENABLED:
        print(f"[TRACE timer] expired -> {expired[-1]}")
    return expired[-1] if expired else None
