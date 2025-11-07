from __future__ import annotations
from typing_extensions import TypedDict
from typing import Dict, Any, List

class OrchestratorState(TypedDict, total=False):
    state: str
    decision: Dict[str, Any]
    input: Dict[str, Any]
    actions: List[Dict[str, Any]]
    response: Dict[str, Any]
    ctx: Dict[str, Any]
    now: float
    session_id: str
