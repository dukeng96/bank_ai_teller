from __future__ import annotations
import json
import os
import time
from typing import Any, Dict, List

from langgraph.graph import StateGraph, START, END
from yaml import safe_load

from orchestrator.state import OrchestratorState
from llm_client.HttpDecider import LLMDecider
from actions.livebank import run_action
from fsm.guards import eval_guard, apply_after
from orchestrator.timeouts import set_timer, clear_timer, check_expired

# Load rules
RULES_PATH = os.path.join(os.path.dirname(__file__), "..", "fsm", "rules.yaml")
with open(RULES_PATH, "r", encoding="utf-8") as f:
    RULES = safe_load(f)

# Load prompts per state (optional)
PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "fsm", "prompts")
PROMPTS: Dict[str, Dict[str, Any]] = {}
for fname in os.listdir(PROMPTS_DIR):
    if fname.endswith(".json"):
        st = fname.replace(".json", "")
        with open(os.path.join(PROMPTS_DIR, fname), "r", encoding="utf-8") as pf:
            try:
                PROMPTS[st] = json.load(pf)
            except Exception:
                PROMPTS[st] = {}

# Single decider instance (HTTP LLM)
decider = LLMDecider()

def _allowed_intents(state: str) -> List[str]:
    st_rules: Dict[str, Any] = RULES.get("states", {}).get(state, {})
    return [k for k in st_rules.keys() if not k.startswith("_")]

# --- Node 0: check timeouts ---
def check_timeouts_node(s: OrchestratorState) -> OrchestratorState:
    now = s.get("now") or time.time()
    s["now"] = now
    ctx = s.setdefault("ctx", {})

    if s.get("state") == "OTP":
        timers = ctx.get("timers", {})
        if "OTP_no_input" not in timers:
            idle_secs = RULES.get("timeouts", {}).get("OTP_no_input")
            if idle_secs:
                set_timer(ctx, "OTP_no_input", int(idle_secs), now)
    else:
        if ctx.get("timers", {}).get("OTP_no_input"):
            clear_timer(ctx, "OTP_no_input")

    expired = check_expired(ctx, now)
    if not expired:
        return s

    if expired == "PRINTING":
        s["input"] = {"channel": "system", "signal": "_timeout_PRINTING"}
    elif expired == "CARD_PICKUP":
        s["input"] = {"channel": "system", "signal": "_timeout_CARD_PICKUP"}
    elif expired == "OTP_no_input":
        s["input"] = {"channel": "system", "signal": "_timeout_no_input"}
    clear_timer(ctx, expired)
    return s

# --- Node 1: think (LLM inference) ---
def think_node(s: OrchestratorState) -> OrchestratorState:
    st = s["state"]
    allowed = _allowed_intents(st)
    prompt_cfg = PROMPTS.get(st, {})
    decision = decider.decide(st, allowed, s.get("input", {}), prompt_cfg)
    s["decision"] = decision
    s["response"] = decision.get("response", {"type": "none", "content": ""})
    return s

# --- Node 2: decide (FSM) ---
def decide_node(s: OrchestratorState) -> OrchestratorState:
    st = s["state"]
    ctx = s.setdefault("ctx", {})
    state_rules: Dict[str, Any] = RULES.get("states", {}).get(st, {})
    signal = s.get("input", {}).get("signal")

    trans: Dict[str, Any] | None = None

    if signal and signal in state_rules:
        trans = state_rules.get(signal)
    if trans is None:
        intent = s.get("decision", {}).get("intent")
        trans = state_rules.get(intent)
    if trans is None:
        trans = state_rules.get("_auto")
    if trans is None:
        s["actions"] = [{"type": "ui", "name": "back_home", "args": {}}]
        s["state"] = "FAILED"
        return s

    guard = trans.get("guard")
    if guard and not eval_guard(guard, ctx):
        fallback = trans.get("fallback")
        if fallback:
            s["actions"] = fallback.get("actions", [])
            s["state"] = fallback.get("to", st)
            return s
        s["actions"] = trans.get("actions", [])
        s["state"] = st
        return s

    after = trans.get("after")
    if after:
        apply_after(after, ctx)

    s["actions"] = trans.get("actions", [])
    next_state = trans.get("to", st)

    if st != next_state and next_state == "OTP":
        idle_secs = RULES.get("timeouts", {}).get("OTP_no_input")
        if idle_secs:
            set_timer(ctx, "OTP_no_input", int(idle_secs), s.get("now"))
    elif st == "OTP" and next_state != "OTP":
        if ctx.get("timers", {}).get("OTP_no_input"):
            clear_timer(ctx, "OTP_no_input")

    s["state"] = next_state
    return s

# --- Node 3: run actions ---
def run_actions_node(s: OrchestratorState) -> OrchestratorState:
    ctx = s.setdefault("ctx", {})
    now = s.get("now") or time.time()
    signals: List[str] = []

    for a in s.get("actions", []):
        if a.get("type") == "clock" and a.get("name") == "start_timer":
            args = a.get("args", {})
            st_name = args.get("state")
            secs = int(args.get("secs", 0))
            if st_name and secs > 0:
                set_timer(ctx, st_name, secs, now)
            continue
        out = run_action(a, ctx)
        if out.get("signal"):
            signals.append(out["signal"])  # keep last

    if signals:
        s["input"] = {"channel": "system", "signal": signals[-1]}
    else:
        if s.get("state") == "OTP" and s.get("input", {}).get("channel") == "voice":
            idle_secs = RULES.get("timeouts", {}).get("OTP_no_input")
            if idle_secs:
                set_timer(ctx, "OTP_no_input", int(idle_secs), now)
        s["input"] = {}

    return s

# Build graph
_graph = StateGraph(OrchestratorState)
_graph.add_node("check_timeouts", check_timeouts_node)
_graph.add_node("think", think_node)
_graph.add_node("decide", decide_node)
_graph.add_node("run_actions", run_actions_node)

_graph.add_edge(START, "check_timeouts")
_graph.add_edge("check_timeouts", "think")
_graph.add_edge("think", "decide")
_graph.add_edge("decide", "run_actions")

def router(s: OrchestratorState) -> str:
    st = s.get("state")
    return "END" if st in ("DONE", "FAILED", "RETRACTED") else "check_timeouts"

_graph.add_conditional_edges("run_actions", router, {"check_timeouts": "check_timeouts", "END": END})
app = _graph.compile()
