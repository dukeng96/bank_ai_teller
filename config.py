from __future__ import annotations
import os
from typing import Any, Dict

import yaml

_CFG: Dict[str, Any] | None = None


def load_config() -> Dict[str, Any]:
    global _CFG
    if _CFG is not None:
        return _CFG
    candidates = [
        os.getenv("CONFIG_PATH"),
        os.path.join(os.getcwd(), "config.yml"),
        os.path.join(os.path.dirname(__file__), "config.yml"),
    ]
    for path in [c for c in candidates if c]:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                _CFG = yaml.safe_load(f) or {}
                return _CFG
    _CFG = {}
    return _CFG


def cfg_path(*keys: str, default: Any = None) -> Any:
    cfg = load_config()
    cur: Any = cfg
    for key in keys:
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur
