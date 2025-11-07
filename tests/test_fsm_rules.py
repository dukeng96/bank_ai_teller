from __future__ import annotations
import os
from yaml import safe_load

def test_rules_loadable() -> None:
    path = os.path.join("src", "teller_ai", "fsm", "rules.yaml")
    with open(path, "r", encoding="utf-8") as f:
        rules = safe_load(f)
    assert "states" in rules
    assert "START" in rules["states"]
